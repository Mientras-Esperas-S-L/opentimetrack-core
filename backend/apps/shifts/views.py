"""Roster endpoints.

A worker reads their own shifts and nothing else. Managers read the company's
and draw them.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import (
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.shifts.models import Shift, ShiftPattern, validate_segments
from apps.shifts.services import (
    assign_pattern,
    clear_shifts,
    expected_vs_worked,
    review_roster,
    weekdays_in,
)
from apps.tenants.rules import WorkingTimeRules


class ShiftPatternSerializer(serializers.ModelSerializer):
    minutes = serializers.IntegerField(read_only=True)
    #: How many published days use it. Deleting one is SET_NULL, so nothing is
    #: lost, but the days it was painted on quietly stop naming a shift --- and
    #: the screen offering the delete had no way to say how many.
    shifts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ShiftPattern
        fields = ["id", "name", "segments", "colour", "is_active", "minutes", "shifts_count"]
        read_only_fields = ["id", "minutes", "shifts_count"]

    def validate_segments(self, value):
        validate_segments(value)
        return value


class ShiftSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    pattern_name = serializers.CharField(source="pattern.name", read_only=True, default="")
    colour = serializers.CharField(source="pattern.colour", read_only=True, default="#1b5e4a")
    minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Shift
        fields = [
            "id",
            "employee",
            "employee_name",
            "day",
            "pattern",
            "pattern_name",
            "colour",
            "segments",
            "minutes",
            "note",
        ]
        read_only_fields = ["id", "employee_name", "pattern_name", "colour", "minutes"]


class AssignSerializer(serializers.Serializer):
    employees = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    pattern = serializers.UUIDField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    # Monday = 0. Empty means every day in the range.
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6), required=False, default=list
    )


@extend_schema(tags=["shifts"])
class ShiftPatternViewSet(viewsets.ModelViewSet):
    """The shapes of a working day. Anyone reads; an administrator draws."""

    queryset = ShiftPattern.objects.none()
    serializer_class = ShiftPatternSerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["is_active"]

    def get_queryset(self):
        return ShiftPattern.objects.annotate(shifts_count=Count("shifts"))

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


@extend_schema(tags=["shifts"])
class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.none()
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["employee", "day"]

    def get_queryset(self):
        qs = Shift.objects.select_related("employee", "pattern")
        if not self.request.user.can_manage:
            qs = qs.filter(employee=self.request.user)
        return qs

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "assign", "clear"}:
            return [IsManagerOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def _window(self, request):
        try:
            return (
                date.fromisoformat(request.query_params["from"]),
                date.fromisoformat(request.query_params["to"]),
            )
        except (KeyError, ValueError) as exc:
            raise BusinessRuleError(
                code="bad_window",
                message=_("Give 'from' and 'to' as YYYY-MM-DD."),
            ) from exc

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
        ],
        responses={200: ShiftSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def roster(self, request):
        """The grid: every shift in a window."""
        first, last = self._window(request)
        rows = self.get_queryset().filter(day__gte=first, day__lte=last).order_by("day")
        return Response(ShiftSerializer(rows, many=True).data)

    @extend_schema(request=AssignSerializer, responses={201: dict})
    @action(detail=False, methods=["post"])
    def assign(self, request):
        """Paints a pattern over a range for several people at once."""
        form = AssignSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        if data["date_to"] < data["date_from"]:
            raise BusinessRuleError(
                code="ends_before_it_starts",
                message=_("The end date cannot precede the start date."),
            )

        pattern = ShiftPattern.objects.filter(pk=data["pattern"]).first()
        if pattern is None:
            raise BusinessRuleError(
                code="unknown_pattern", message=_("That shift pattern does not exist.")
            )

        wanted = data["weekdays"] or list(range(7))
        days = weekdays_in(data["date_from"], data["date_to"], wanted)

        from apps.users.models import User

        people = User.objects.filter(tenant=request.user.tenant, pk__in=data["employees"])
        if people.count() != len(set(data["employees"])):
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("Somebody in that list is not in this company."),
            )

        created = 0
        for person in people:
            created += len(
                assign_pattern(
                    employee=person, company=request.user.tenant, pattern=pattern, days=days
                )
            )

        # Reviewed straight away: a roster that breaks a rest rule is worth
        # knowing about now, not the day somebody notices on the calendar.
        findings = review_roster(
            company=request.user.tenant, first=data["date_from"], last=data["date_to"]
        )
        return Response(
            {"created": created, "findings": [f.as_dict() for f in findings]}, status=201
        )

    @extend_schema(request=AssignSerializer, responses={200: dict})
    @action(detail=False, methods=["post"])
    def clear(self, request):
        form = AssignSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        wanted = data["weekdays"] or list(range(7))
        days = weekdays_in(data["date_from"], data["date_to"], wanted)

        from apps.users.models import User

        removed = 0
        for person in User.objects.filter(tenant=request.user.tenant, pk__in=data["employees"]):
            removed += clear_shifts(employee=person, days=days)
        return Response({"removed": removed})

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
        ],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def review(self, request):
        """What the roster departs from, and on what basis. Never a refusal."""
        first, last = self._window(request)
        employee = None if request.user.can_manage else request.user
        findings = review_roster(
            company=request.user.tenant, first=first, last=last, employee=employee
        )
        return Response({"findings": [f.as_dict() for f in findings]})

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        """Expected against recorded, for the caller, today."""
        return Response(
            expected_vs_worked(employee=request.user, company=request.user.tenant, day=date.today())
        )


class RulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingTimeRules
        exclude = ["tenant", "created_at", "updated_at"]
        read_only_fields = ["id"]


@extend_schema(tags=["organisation"])
class WorkingTimeRulesView(APIView):
    """The figures the roster is checked against.

    Read for anyone: a worker is entitled to know which rules their employer has
    configured, and a warning nobody can trace to a number is not a warning.
    """

    def get_permissions(self):
        from apps.common.permissions import IsAdmin

        return [IsAdmin()] if self.request.method == "PATCH" else [IsAuthenticatedInTenant()]

    @extend_schema(responses={200: RulesSerializer})
    def get(self, request):
        return Response(RulesSerializer(WorkingTimeRules.for_company(request.user.tenant)).data)

    @extend_schema(request=RulesSerializer, responses={200: RulesSerializer})
    def patch(self, request):
        rules = WorkingTimeRules.for_company(request.user.tenant)
        before = RulesSerializer(rules).data
        serializer = RulesSerializer(rules, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # These decide what the roster is measured against, so a change to them
        # changes what "compliant" means. Only what moved is recorded.
        changed = {
            field: [before[field], value]
            for field, value in serializer.data.items()
            if before.get(field) != value
        }
        if changed:
            record(
                action=AuditAction.RULES_CHANGED,
                actor=request.user,
                target=request.user.tenant,
                target_type="company",
                target_label=request.user.tenant.name,
                changes=changed,
                request=request,
            )
        return Response(serializer.data)
