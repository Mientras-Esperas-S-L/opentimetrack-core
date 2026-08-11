"""Endpoints for record corrections."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsAuthenticatedInTenant, IsManagerOrAdmin
from apps.punches.corrections import (
    CorrectionKind,
    PunchCorrection,
    approve_correction,
    reject_correction,
    request_correction,
)
from apps.punches.models import Punch
from apps.punches.serializers import PunchSerializer


class CorrectionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    result_detail = PunchSerializer(source="result", read_only=True)

    class Meta:
        model = PunchCorrection
        fields = [
            "id",
            "employee",
            "employee_name",
            "kind",
            "kind_display",
            "target",
            "proposed_type",
            "proposed_timestamp",
            "reason",
            "status",
            "status_display",
            "requested_by",
            "resolved_by",
            "resolved_at",
            "resolution_note",
            "result",
            "result_detail",
            "created_at",
        ]
        read_only_fields = fields


class CorrectionRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=CorrectionKind.choices)
    # Only a manager may name somebody else; anyone else corrects their own.
    employee = serializers.UUIDField(required=False, allow_null=True)
    target = serializers.UUIDField(required=False, allow_null=True)
    proposed_type = serializers.CharField(required=False, allow_blank=True)
    proposed_timestamp = serializers.DateTimeField(required=False, allow_null=True)

    # Mandatory, and not merely required by the form: a correction with no
    # stated reason is indistinguishable from tampering.
    reason = serializers.CharField(min_length=5, max_length=500)


class ResolutionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


@extend_schema(tags=["corrections"])
class CorrectionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Requests to put the record right.

    A worker may raise one about their own record and see how it ends. Managers
    and administrators see the whole company's and decide.
    """

    queryset = PunchCorrection.objects.none()
    serializer_class = CorrectionSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["status", "kind", "employee"]

    def get_queryset(self):
        qs = PunchCorrection.objects.select_related("employee", "target", "result").all()
        if not self.request.user.can_manage:
            qs = qs.filter(employee=self.request.user)
        return qs

    @extend_schema(
        summary="Request a correction",
        description=(
            "Records what the person says actually happened. Changes nothing until "
            "somebody approves it. The reason is mandatory."
        ),
        request=CorrectionRequestSerializer,
        responses={201: CorrectionSerializer},
    )
    def create(self, request):
        form = CorrectionRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        target = None
        if data.get("target"):
            target = Punch.objects.filter(pk=data["target"]).first()
            if target is None:
                raise BusinessRuleError(
                    code="event_not_found",
                    message=_("That event does not exist."),
                )

        employee = self._subject(request, data.get("employee"))

        correction = request_correction(
            employee=employee,
            company=request.user.tenant,
            requested_by=request.user,
            kind=data["kind"],
            reason=data["reason"],
            target=target,
            proposed_type=data.get("proposed_type", ""),
            proposed_timestamp=data.get("proposed_timestamp"),
        )
        return Response(CorrectionSerializer(correction).data, status=status.HTTP_201_CREATED)

    def _subject(self, request, employee_id):
        """Whose record the correction is about.

        ADR-0014: a manager may correct without a prior request, but through the
        same procedure and with the same mandatory reason. Nobody touches a time
        without leaving why --- and the request records both the person it
        concerns and the person who filed it, which are not the same field.
        """
        if not employee_id or str(employee_id) == str(request.user.id):
            return request.user

        if not request.user.can_manage:
            raise BusinessRuleError(
                code="not_your_record",
                message=_("You can only ask for corrections to your own record."),
            )

        from apps.users.models import User

        # Scoped to the company: an id from elsewhere is simply not found.
        employee = User.objects.filter(tenant=request.user.tenant, pk=employee_id).first()
        if employee is None:
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("That person is not in this company."),
            )
        return employee

    @extend_schema(
        summary="Approve a correction",
        description="Applies it. The previous version stays readable and points to the new one.",
        request=ResolutionSerializer,
        responses={200: CorrectionSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        correction = self.get_object()
        form = ResolutionSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        approve_correction(
            correction, resolved_by=request.user, note=form.validated_data.get("note", "")
        )
        correction.refresh_from_db()
        return Response(CorrectionSerializer(correction).data)

    @extend_schema(
        summary="Reject a correction",
        description="Turns it down. The request stays: a refused claim is history too.",
        request=ResolutionSerializer,
        responses={200: CorrectionSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def reject(self, request, pk=None):
        correction = self.get_object()
        form = ResolutionSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        reject_correction(
            correction, resolved_by=request.user, note=form.validated_data.get("note", "")
        )
        correction.refresh_from_db()
        return Response(CorrectionSerializer(correction).data)
