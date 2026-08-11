"""Endpoints for leave.

Who sees what follows the same rule as clock events: a person is entitled to
their own history and not to a colleague's; managers and administrators see the
company.
"""

from __future__ import annotations

from datetime import date

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.absences.services import (
    approve_absence,
    cancel_absence,
    reject_absence,
    request_absence,
    vacation_balance,
)
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsAuthenticatedInTenant, IsManagerOrAdmin


class AbsenceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    type_display = serializers.CharField(source="get_absence_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    resolved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True, default=""
    )
    days = serializers.IntegerField(read_only=True)

    class Meta:
        model = Absence
        fields = [
            "id",
            "employee",
            "employee_name",
            "absence_type",
            "type_display",
            "start_date",
            "end_date",
            "days",
            "reason",
            "status",
            "status_display",
            "approved_by",
            "resolved_by_name",
            "resolved_at",
            "justification",
            "created_at",
        ]
        read_only_fields = fields


class AbsenceRequestSerializer(serializers.Serializer):
    absence_type = serializers.ChoiceField(choices=AbsenceType.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    justification = serializers.FileField(required=False, allow_null=True)
    # Managers may file leave on somebody's behalf; an employee may not.
    employee = serializers.UUIDField(required=False, allow_null=True)


class AbsenceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AbsenceSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["status", "absence_type", "employee"]
    ordering_fields = ["start_date", "created_at"]
    ordering = ["-start_date"]

    def get_queryset(self):
        qs = Absence.objects.select_related("employee", "approved_by")
        if not self.request.user.can_manage:
            qs = qs.filter(employee=self.request.user)
        return qs

    @extend_schema(request=AbsenceRequestSerializer, responses={201: AbsenceSerializer})
    def create(self, request):
        form = AbsenceRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        employee = request.user
        if data.get("employee") and data["employee"] != request.user.id:
            if not request.user.can_manage:
                raise BusinessRuleError(
                    code="not_your_request",
                    message=_("Leave can only be requested for yourself."),
                )
            employee = self._employee_in_company(data["employee"])

        absence = request_absence(
            employee=employee,
            company=request.user.tenant,
            absence_type=data["absence_type"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            reason=data.get("reason", ""),
            justification=data.get("justification"),
        )
        return Response(AbsenceSerializer(absence).data, status=status.HTTP_201_CREATED)

    def _employee_in_company(self, employee_id):
        from apps.users.models import User

        # Tenant-scoped manager: an id from another company simply is not found.
        try:
            return User.objects.get(pk=employee_id)
        except (User.DoesNotExist, ValueError, TypeError) as exc:
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("That person is not in this company."),
            ) from exc

    @extend_schema(request=None, responses={200: AbsenceSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        absence = approve_absence(self.get_object(), resolved_by=request.user)
        return Response(AbsenceSerializer(absence).data)

    @extend_schema(request=None, responses={200: AbsenceSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def reject(self, request, pk=None):
        absence = reject_absence(self.get_object(), resolved_by=request.user)
        return Response(AbsenceSerializer(absence).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        cancel_absence(self.get_object(), cancelled_by=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"])
    def balance(self, request):
        """Holiday left. Defaults to the caller; managers may ask for anybody."""
        employee = request.user
        wanted = request.query_params.get("employee")
        if wanted and wanted != str(request.user.id):
            if not request.user.can_manage:
                raise BusinessRuleError(
                    code="not_your_balance",
                    message=_("You can only see your own balance."),
                )
            employee = self._employee_in_company(wanted)

        balance = vacation_balance(employee, request.user.tenant)
        return Response({"employee": str(employee.id), **balance.as_dict()})

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
        ],
        responses={200: AbsenceSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def calendar(self, request):
        """Everything overlapping a window, for the team calendar.

        Overlap, not containment: leave running from June to July has to appear
        when looking at July, and a filter on `start_date` alone would drop it.
        That off-by-one is invisible until somebody books over a colleague's
        holiday because the calendar did not show it.

        A worker sees their own; a manager sees the company. Pending requests
        come too, drawn differently: deciding whether to approve August needs to
        show what else is already asked for.
        """
        try:
            first = date.fromisoformat(request.query_params["from"])
            last = date.fromisoformat(request.query_params["to"])
        except (KeyError, ValueError) as exc:
            raise BusinessRuleError(
                code="bad_window",
                message=_("Give 'from' and 'to' as YYYY-MM-DD."),
            ) from exc

        window = (
            self.get_queryset()
            .filter(start_date__lte=last, end_date__gte=first)
            .exclude(status=AbsenceStatus.REJECTED)
            .order_by("start_date")
        )
        return Response(AbsenceSerializer(window, many=True).data)

    @extend_schema(responses={200: AbsenceSerializer(many=True)})
    @action(detail=False, methods=["get"])
    def pending(self, request):
        """The approval queue. What a manager opens the panel to deal with."""
        if not request.user.can_manage:
            return Response([])
        queue = (
            Absence.objects.filter(status=AbsenceStatus.PENDING)
            .select_related("employee")
            .order_by("start_date")
        )
        return Response(AbsenceSerializer(queue, many=True).data)
