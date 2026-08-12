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

from apps import legal
from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import (
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.common.scope import visible_people
from apps.shifts.models import Shift, ShiftPattern, validate_segments
from apps.shifts.services import (
    assign_pattern,
    clear_shifts,
    expected_vs_worked,
    paint_cells,
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


class PaintCellSerializer(serializers.Serializer):
    """One square of the grid, and what it becomes."""

    employee = serializers.UUIDField()
    day = serializers.DateField()
    #: A pattern, or bare spans, or neither --- in which case the day is rubbed
    #: out. Both together is a contradiction rather than a preference, so it is
    #: refused instead of one quietly winning.
    pattern = serializers.UUIDField(required=False, allow_null=True)
    segments = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        if attrs.get("pattern") and attrs.get("segments"):
            raise serializers.ValidationError(
                _("Give a shift or its hours, not both: they would disagree.")
            )
        if attrs.get("segments"):
            validate_segments(attrs["segments"])
        return attrs


class PaintSerializer(serializers.Serializer):
    """A stroke on the roster: some cells, each set to something of its own.

    Capped, and the cap is not a formality --- a whole workforce across a year
    would be six figures of rows behind one click. A month of a hundred people
    is three thousand, so the ceiling sits above any stroke a hand can draw and
    well below anything that would hold the database open.
    """

    cells = serializers.ListField(child=PaintCellSerializer(), allow_empty=False, max_length=4000)


class ClearSerializer(AssignSerializer):
    """Rubbing days out takes everything assigning does, minus the pattern.

    It was sharing `AssignSerializer`, which made the pattern required and then
    ignored it --- so a caller had to invent one, and a company with no patterns
    defined could not clear a roster at all. A required field nobody reads is a
    trap for whoever writes the next client.
    """

    pattern = serializers.UUIDField(required=False, allow_null=True)


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
        # Their own if they are not a manager; the departments they answer for
        # if they are. `visible_people` returns None for "no restriction", so an
        # administrator adds no join.
        scope = visible_people(self.request.user)
        if scope is not None:
            qs = qs.filter(employee__in=scope)
        return qs

    #: Everything that writes a roster. Kept as a constant next to the actions
    #: it names: adding one and forgetting to list it here hands the whole
    #: company's calendar to anybody with a login, and the omission looks like
    #: nothing on the screen.
    WRITES = {"create", "update", "partial_update", "destroy", "assign", "clear", "paint"}

    def get_permissions(self):
        if self.action in self.WRITES:
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

    @extend_schema(request=PaintSerializer, responses={200: dict})
    @action(detail=False, methods=["post"])
    def paint(self, request):
        """A stroke drawn straight onto the grid.

        Separate from `assign` because it answers a different question. Assign
        takes a pattern and a rectangle of the calendar, which is how a roster
        gets built. This takes a list of squares, each with its own answer,
        which is how one gets corrected --- and it is what lets undo put back a
        stroke that crossed four different shifts and two blanks.
        """
        form = PaintSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        cells = form.validated_data["cells"]

        result = paint_cells(company=request.user.tenant, cells=cells)

        days = [cell["day"] for cell in cells]
        findings = review_roster(company=request.user.tenant, first=min(days), last=max(days))
        return Response({**result, "findings": [f.as_dict() for f in findings]})

    @extend_schema(request=ClearSerializer, responses={200: dict})
    @action(detail=False, methods=["post"])
    def clear(self, request):
        form = ClearSerializer(data=request.data)
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
        return Response({"findings": _grouped(findings)})

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        """Expected against recorded, for the caller, today."""
        return Response(
            expected_vs_worked(
                employee=request.user,
                company=request.user.tenant,
                # Their today: date.today() is the container's UTC date, which
                # is yesterday for all of Spain between midnight and 01:00.
                day=local_today(request.user),
            )
        )


def _grouped(findings):
    """One row per person and kind, not one per day.

    A month of real data produced a hundred and fifty-six warnings, and a
    hundred and thirty of them were the same sentence about the same person on
    consecutive days: somebody whose shift pattern is nine hours continuous is
    owed a break every one of them.

    Each of those is true and the list of them is useless --- a wall nobody
    reads is the same as no warning at all, and it buries the three that were
    about something else. So they are folded: the count, the first day, and the
    days themselves for anybody who wants them.

    Folded here rather than in `review_roster` because the per-day findings are
    the accurate answer and the tests check them. This is presentation.
    """
    grouped: dict = {}
    for finding in findings:
        row = finding.as_dict()
        key = (row["employee"], row["code"])
        if key not in grouped:
            grouped[key] = {**row, "days": [], "count": 0}
        grouped[key]["days"].append(row["day"])
        grouped[key]["count"] += 1

    out = []
    for row in grouped.values():
        row["days"].sort()
        # The earliest, so the list still sorts by when the problem starts.
        row["day"] = row["days"][0]
        out.append(row)
    return sorted(out, key=lambda r: (r["day"], r["code"]))


def _describe(part, as_time: tuple[str, ...] = ()) -> dict | None:
    """A frozen dataclass from the legal layer, as JSON.

    Written once here rather than a serializer per dataclass: these carry no
    behaviour and no validation --- they are the country's numbers, read-only,
    and a country that has none returns null so the screen can leave the section
    out instead of rendering an empty one.
    """
    if part is None:
        return None
    body = {name: getattr(part, name) for name in part.__dataclass_fields__ if name != "citations"}
    for name in as_time:
        body[name] = body[name].isoformat(timespec="minutes")
    body["citations"] = {
        key: {"basis": c.basis, "note": c.note} for key, c in part.citations.items()
    }
    return body


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

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(self._body(WorkingTimeRules.for_company(request.user.tenant), request))

    @staticmethod
    def _body(rules, request):
        """The figures, and where each one comes from.

        The citations used to be written twice: in the model's `help_text`,
        which nothing read, and by hand into the settings screen, which is the
        copy people actually saw --- untranslatable, unable to vary by country,
        and free to drift from the backend.

        Serving them is what removes both problems at once. The screen renders
        what it is given, and a company in another country is given that
        country's articles.
        """
        framework = legal.for_company(request.user.tenant)
        data = RulesSerializer(rules).data
        return {
            **data,
            "country": framework.country,
            "framework": framework.name,
            "citations": {
                key: {"basis": c.basis, "note": c.note} for key, c in framework.citations.items()
            },
            # Not settings and never will be: no agreement may lower them, so a
            # field to edit them would be a field whose only use is breaking the
            # law. Served so the screen can say what they are.
            "minors": {
                "max_daily_hours": framework.minors.max_daily_hours,
                "break_after_hours": framework.minors.break_after_hours,
                "break_minutes": framework.minors.break_minutes,
                "weekly_rest_hours": framework.minors.weekly_rest_hours,
                "night_work_forbidden": framework.minors.night_work_forbidden,
                "overtime_forbidden": framework.minors.overtime_forbidden,
                "citations": {
                    key: {"basis": c.basis, "note": c.note}
                    for key, c in framework.minors.citations.items()
                },
            },
            # Also not settings, and for a different reason: the night window is
            # one --- a company can move it --- but what the status *means* is
            # not. The figures are served so the screen can explain why somebody
            # on nights is checked differently, without writing the article into
            # the frontend again.
            "night": _describe(framework.night, ("window_starts_at", "window_ends_at")),
            "shifts": _describe(framework.shifts),
            # The subdivisions that set their own public holidays. Served here
            # so the workplace form offers the country's own list instead of
            # carrying a copy of Spain's --- which is the mistake the citations
            # made before this endpoint existed.
            "regions": framework.regions,
        }

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
        return Response(self._body(rules, request))
