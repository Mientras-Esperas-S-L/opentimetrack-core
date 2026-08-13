"""Clocking in on behalf of an employee.

The door an external application uses when the person cannot act with their own
identity: a shared tablet on site, an NFC reader at the gate, a shift terminal.

Everything recorded through here is marked `DELEGATED` and that mark reaches the
inspection report. It is not an implementation detail: an application saying
"Marta arrived at 08:00" is a different kind of evidence from Marta saying it,
and whoever reads the record is entitled to tell them apart.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import HasApplicationScope
from apps.punches.models import PunchSource, PunchTrigger
from apps.punches.serializers import PunchSerializer, validate_evidence
from apps.punches.services import build_day_status, register_punch
from apps.tenants.applications import ApplicationScope

User = get_user_model()


class DelegatedPunchSerializer(serializers.Serializer):
    """What an application may send.

    Still no timestamp and no type: delegating who presses the button does not
    delegate who owns the clock.
    """

    employee_ref = serializers.CharField(
        max_length=254,
        help_text="Staff number, email address or identifier of the employee.",
    )
    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    terminal = serializers.BooleanField(
        required=False,
        default=False,
        help_text="True when a shared terminal was used rather than the application itself.",
    )
    # The whole point of the integration seam: a sensor (a geofence in Geosian,
    # a badge reader) says what it detected and attaches the proof. OTT records
    # it with the origin marked, visible in the inspection report.
    trigger = serializers.ChoiceField(
        choices=PunchTrigger.choices, required=False, default=PunchTrigger.MANUAL
    )
    evidence = serializers.JSONField(required=False, default=dict, validators=[validate_evidence])


def resolve_employee(reference: str, company):
    """Finds the person from the reference the application knows them by.

    Tried in order of how stable each identifier is: the staff number is set by
    the managing application and does not change, the email does. The lookup is
    scoped to the company, so a reference from elsewhere simply does not exist.
    """
    reference = reference.strip()

    matches = list(
        User.objects.filter(
            Q(employee_id__iexact=reference) | Q(email__iexact=reference),
            tenant=company,
            is_active=True,
        )[:2]
    )

    if not matches:
        # Also accept the internal identifier, for an application that stored it.
        # ValidationError belongs in the list: Django raises it, not ValueError,
        # when the text is not a UUID, and every unknown reference lands here.
        # Without it an unknown staff number is a 500 instead of a clean refusal.
        try:
            return User.objects.get(pk=reference, tenant=company, is_active=True)
        except User.DoesNotExist, ValidationError, ValueError, TypeError:
            return None

    if len(matches) > 1:
        # Two people matching one reference: refusing is the only safe answer.
        # Recording the wrong person's working day is worse than not recording.
        raise BusinessRuleError(
            code="ambiguous_employee_reference",
            message=_("The reference matches more than one person."),
            details={"employee_ref": reference},
        )

    return matches[0]


@extend_schema(tags=["punches"])
class DelegatedPunchView(APIView):
    """Records a clock event on behalf of an employee."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.PUNCH_DELEGATED

    @extend_schema(
        summary="Clock in on behalf of an employee",
        description=(
            "For an application acting for somebody who cannot use their own identity: "
            "a shared terminal, an NFC reader, a device without a personal session. "
            "The event is marked as delegated and that mark appears in the report. "
            "Requires the `punch:delegated` permission."
        ),
        request=DelegatedPunchSerializer,
        responses={201: PunchSerializer},
    )
    def post(self, request):
        serializer = DelegatedPunchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = request.user.application
        company = application.tenant

        employee = resolve_employee(serializer.validated_data["employee_ref"], company)
        if employee is None:
            raise BusinessRuleError(
                code="employee_not_found",
                message=_("No active person matches that reference."),
                details={"employee_ref": serializer.validated_data["employee_ref"]},
            )

        punch = register_punch(
            employee=employee,
            company=company,
            source=(
                PunchSource.TERMINAL
                if serializer.validated_data.get("terminal")
                else PunchSource.DELEGATED
            ),
            source_application=application.name,
            device_id=serializer.validated_data.get("device_id", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            trigger=serializer.validated_data.get("trigger") or "MANUAL",
            evidence=serializer.validated_data.get("evidence") or {},
        )

        data = PunchSerializer(punch).data
        data["day_status"] = build_day_status(employee, company).as_dict()
        return Response(data, status=status.HTTP_201_CREATED)
