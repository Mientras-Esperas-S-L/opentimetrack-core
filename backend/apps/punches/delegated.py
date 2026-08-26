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
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessRuleError, IncompleteRequest
from apps.common.permissions import HasApplicationScope
from apps.punches.models import DelegatedPunchReceipt, PunchSource, PunchTrigger
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
            "Requires the `punch:delegated` permission.\n\n"
            "**`Idempotency-Key` is required.** Pick a value that identifies the "
            "operation, not the moment: the gate plus the employee plus the shift, for "
            "instance. Repeating a call with the same key returns the event already "
            "recorded, with `200` instead of `201`, and records nothing new. Without "
            "one the call is refused with `400 idempotency_key_required`, because a "
            "retry would not repeat the entry --- it would record an **exit**, since "
            "the type is inferred from the current state, and the working day would "
            "be lost."
        ),
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description=(
                    "Identifies the operation so a retry is not recorded twice. "
                    "Up to 200 characters, scoped to the calling application."
                ),
            )
        ],
        request=DelegatedPunchSerializer,
        responses={201: PunchSerializer, 200: PunchSerializer},
    )
    def post(self, request):
        serializer = DelegatedPunchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = request.user.application
        company = application.tenant

        # Required, not offered. See `DelegatedPunchReceipt` for what goes wrong
        # without it. A connector that cannot be bothered to name its operation
        # is one lost answer away from turning somebody's nine-hour day into
        # thirty seconds --- and it would find that out in production, on a
        # record that then needs the art. 4.b procedure to put right. Refusing
        # here moves the discovery to the first call in development.
        key = (request.headers.get("Idempotency-Key") or "").strip()[:200]
        if not key:
            raise IncompleteRequest(
                code="idempotency_key_required",
                message=_(
                    "Send an Idempotency-Key header naming this operation, so a retry "
                    "is not recorded as a second event."
                ),
                details={"header": "Idempotency-Key"},
            )

        # The retry, answered before anything is written: a connector whose
        # answer got lost sends the same key again, and gets the event it
        # already recorded rather than an exit it never meant.
        done = DelegatedPunchReceipt.objects.filter(application=application, key=key).first()
        if done is not None:
            if done.punch is None:
                # Reserved, not finished: the first request is still in flight
                # or died before committing. Saying "in progress" sends the
                # connector back later; answering 201 with nothing would be a
                # lie.
                raise BusinessRuleError(
                    code="in_progress",
                    message=_("That operation is still being recorded. Try again shortly."),
                )
            return self._answer(done.punch, status.HTTP_200_OK)

        employee = resolve_employee(serializer.validated_data["employee_ref"], company)
        if employee is None:
            raise BusinessRuleError(
                code="employee_not_found",
                message=_("No active person matches that reference."),
                details={"employee_ref": serializer.validated_data["employee_ref"]},
            )

        # Claim the key **before** recording, so two simultaneous retries cannot
        # both get past the check above.
        try:
            with transaction.atomic():
                receipt = DelegatedPunchReceipt.objects.create(
                    tenant=company, application=application, key=key
                )
        except IntegrityError:
            done = DelegatedPunchReceipt.objects.filter(application=application, key=key).first()
            if done is not None and done.punch is not None:
                return self._answer(done.punch, status.HTTP_200_OK)
            raise BusinessRuleError(
                code="in_progress",
                message=_("That operation is still being recorded. Try again shortly."),
            ) from None

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

        receipt.punch = punch
        receipt.save(update_fields=["punch", "updated_at"])

        return self._answer(punch, status.HTTP_201_CREATED)

    def _answer(self, punch, code: int) -> Response:
        data = PunchSerializer(punch).data
        data["day_status"] = build_day_status(punch.employee, punch.tenant).as_dict()
        return Response(data, status=code)
