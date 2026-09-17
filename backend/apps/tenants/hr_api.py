"""Leave, roster and holidays, for the application that draws the calendar.

`read:attendance` answers what was **worked**. These three answer what explains the
rest of the grid: the leave that covers a gap, the shifts that were expected, and the
days the workplace was closed. They are separate permissions on purpose — an
integration that paints hours has no business reading why somebody is off unless its
owner granted exactly that.

Writing is one-sided and deliberate. Leave can be **requested** through here, because
a request is somebody asking, not a measurement, and whoever asks is usually in the
other application. Nothing here approves anything, and nothing here writes hours: what
changes the record goes through the door it already has.
"""

from __future__ import annotations

from datetime import date

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import HasApplicationScope
from apps.tenants.applications import ApplicationScope

#: The same ceiling as the attendance range: a calendar never shows more, and the cost
#: of these answers grows with the days asked for.
MAX_RANGE_DAYS = 62


def _range(params) -> tuple[date, date]:
    from django.utils.dateparse import parse_date

    first = parse_date(params.get("from") or "")
    last = parse_date(params.get("to") or "")
    errors = {}
    if first is None:
        errors["from"] = [_("A date is required, as YYYY-MM-DD.")]
    if last is None:
        errors["to"] = [_("A date is required, as YYYY-MM-DD.")]
    if errors:
        raise serializers.ValidationError(errors)
    if last < first:
        raise serializers.ValidationError({"to": [_("Must not be before `from`.")]})
    if (last - first).days + 1 > MAX_RANGE_DAYS:
        raise serializers.ValidationError(
            {"to": [_("At most %(days)d days per call.") % {"days": MAX_RANGE_DAYS}]}
        )
    return first, last


def _person(reference: str, company):
    """The person that reference names, or a refusal that says which one failed."""
    from apps.punches.delegated import resolve_employee

    person = resolve_employee(reference, company)
    if person is None:
        raise BusinessRuleError(
            code="employee_not_found",
            message=_("No active person matches that reference."),
            details={"employee_ref": reference},
        )
    return person


def _people_of(request, company):
    """Everybody, or the one person the caller named."""
    from apps.users.models import User

    wanted = request.query_params.get("employee_ref")
    if not wanted:
        return list(User.objects.filter(tenant=company, is_active=True))
    return [_person(wanted, company)]


# ------------------------------------------------------------------- absences


class AbsenceOutSerializer(serializers.Serializer):
    employee = serializers.UUIDField()
    employee_id = serializers.CharField()
    code = serializers.CharField(help_text="The leave type's code, or the absence type.")
    name = serializers.CharField()
    # El estado sale de `AbsenceStatus` menos el rechazado, que aquí no se devuelve.
    # Declarado con nombre propio para que el esquema no invente uno al chocar con
    # los otros `status` de la API.
    status = serializers.ChoiceField(
        choices=["PENDING", "APPROVED"], help_text="Pedido o concedido."
    )
    from_day = serializers.DateField(source="from")
    to = serializers.DateField()
    start_time = serializers.TimeField(
        allow_null=True, help_text="Set when the leave covers hours."
    )
    end_time = serializers.TimeField(allow_null=True)


class AbsencesAnswerSerializer(serializers.Serializer):
    absences = AbsenceOutSerializer(many=True)


@extend_schema(tags=["applications"])
class ApplicationAbsencesView(APIView):
    """The leave that explains the gaps in a range."""

    permission_classes = [HasApplicationScope]

    def required_scope_for(self, request):
        # Reading and asking are different powers: an application that only paints a
        # calendar should not be able to book somebody's holiday.
        return (
            ApplicationScope.WRITE_ABSENCES
            if request.method == "POST"
            else ApplicationScope.READ_ABSENCES
        )

    @extend_schema(
        summary="Leave over a range",
        description=(
            "Approved and pending leave overlapping the range, with the type from the legal "
            "catalogue. Rejected requests are not included: they explain nothing. "
            "Requires `read:absences`."
        ),
        parameters=[
            OpenApiParameter("from", str, required=True),
            OpenApiParameter("to", str, required=True),
            OpenApiParameter("employee_ref", str),
        ],
        responses={200: AbsencesAnswerSerializer},
    )
    def get(self, request):
        from apps.absences.models import Absence, AbsenceStatus

        company = request.user.application.tenant
        first, last = _range(request.query_params)
        people = _people_of(request, company)

        rows = (
            Absence.objects.filter(employee__in=people, start_date__lte=last, end_date__gte=first)
            .exclude(status=AbsenceStatus.REJECTED)
            .select_related("leave_type", "employee")
            .order_by("start_date")
        )
        return Response(
            {
                "absences": [
                    {
                        "employee": str(row.employee_id),
                        "employee_id": row.employee.employee_id,
                        "code": (
                            row.leave_type.code
                            if row.leave_type_id and row.leave_type.code
                            else row.absence_type
                        ),
                        "name": (
                            row.leave_type.name
                            if row.leave_type_id
                            else row.get_absence_type_display()
                        ),
                        "status": row.status,
                        "from": row.start_date.isoformat(),
                        "to": row.end_date.isoformat(),
                        "start_time": row.start_time.isoformat() if row.start_time else None,
                        "end_time": row.end_time.isoformat() if row.end_time else None,
                    }
                    for row in rows
                ]
            }
        )

    class AskSerializer(serializers.Serializer):
        employee_ref = serializers.CharField(max_length=254)
        code = serializers.CharField(
            max_length=40,
            help_text="A leave type code from this company's catalogue.",
        )
        start_date = serializers.DateField()
        end_date = serializers.DateField()
        start_time = serializers.TimeField(required=False, allow_null=True)
        end_time = serializers.TimeField(required=False, allow_null=True)
        reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    @extend_schema(
        summary="Request leave for somebody",
        description=(
            "Records the request; **nothing is approved here**. It goes through the same "
            "rules and limits as a request made in this system. Requires `write:absences`."
        ),
        request=AskSerializer,
        responses={201: AbsenceOutSerializer},
    )
    def post(self, request):
        from apps.absences.models import LeaveType
        from apps.absences.services import request_absence
        from apps.audit.models import AuditAction
        from apps.audit.services import record

        company = request.user.application.tenant
        form = self.AskSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        person = _person(data["employee_ref"], company)

        leave_type = LeaveType.objects.filter(tenant=company, code__iexact=data["code"]).first()
        if leave_type is None:
            raise BusinessRuleError(
                code="leave_type_unknown",
                message=_("This company has no leave type with that code."),
                details={"code": data["code"]},
            )

        absence = request_absence(
            employee=person,
            company=company,
            leave_type=leave_type,
            start_date=data["start_date"],
            end_date=data["end_date"],
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            reason=data.get("reason", ""),
        )
        # Una aplicación pidiendo un permiso en nombre de alguien es algo que hay que
        # poder responder después: quién lo pidió, por quién y de qué tipo. Sin esto,
        # la solicitud aparecería como si la hubiera hecho la propia persona.
        record(
            action=AuditAction.ABSENCE_REQUESTED,
            actor=None,
            actor_label=f"aplicación · {request.user.application.name}",
            company=company,
            target=absence,
            target_type="absence",
            target_label=f"{leave_type.name} · {person.get_full_name() or person.email}",
            changes={
                "from": absence.start_date.isoformat(),
                "to": absence.end_date.isoformat(),
                "code": leave_type.code,
            },
        )
        return Response(
            {
                "employee": str(person.id),
                "employee_id": person.employee_id,
                "code": leave_type.code,
                "name": leave_type.name,
                "status": absence.status,
                "from": absence.start_date.isoformat(),
                "to": absence.end_date.isoformat(),
                "start_time": absence.start_time.isoformat() if absence.start_time else None,
                "end_time": absence.end_time.isoformat() if absence.end_time else None,
            },
            status=status.HTTP_201_CREATED,
        )


# --------------------------------------------------------------------- roster


class ShiftOutSerializer(serializers.Serializer):
    employee = serializers.UUIDField()
    employee_id = serializers.CharField()
    day = serializers.DateField()
    segments = serializers.ListField(child=serializers.DictField())
    minutes = serializers.IntegerField()


@extend_schema(tags=["applications"])
class ApplicationRosterView(APIView):
    """What the roster expected, which is what tells an empty day from a day off."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_ROSTER

    @extend_schema(
        summary="Planned shifts over a range",
        parameters=[
            OpenApiParameter("from", str, required=True),
            OpenApiParameter("to", str, required=True),
            OpenApiParameter("employee_ref", str),
        ],
        responses={200: ShiftOutSerializer(many=True)},
    )
    def get(self, request):
        from apps.shifts.models import Shift

        company = request.user.application.tenant
        first, last = _range(request.query_params)
        people = _people_of(request, company)

        rows = (
            Shift.objects.filter(employee__in=people, day__gte=first, day__lte=last)
            .select_related("employee")
            .order_by("day")
        )
        return Response(
            {
                "shifts": [
                    {
                        "employee": str(row.employee_id),
                        "employee_id": row.employee.employee_id,
                        "day": row.day.isoformat(),
                        "segments": row.segments,
                        "minutes": row.minutes,
                    }
                    for row in rows
                ]
            }
        )


# ------------------------------------------------------------------- calendar


@extend_schema(tags=["applications"])
class ApplicationCalendarView(APIView):
    """Public holidays, which belong to a workplace and not to the company."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_CALENDAR

    @extend_schema(
        summary="Public holidays over a range",
        description=(
            "Company-wide holidays and the local ones of each workplace. A holiday with no "
            "workplace applies to everybody. Requires `read:calendar`."
        ),
        parameters=[
            OpenApiParameter("from", str, required=True),
            OpenApiParameter("to", str, required=True),
        ],
        responses={200: None},
    )
    def get(self, request):
        from apps.tenants.holidays import PublicHoliday

        company = request.user.application.tenant
        first, last = _range(request.query_params)

        rows = (
            PublicHoliday.objects.filter(tenant=company, day__gte=first, day__lte=last)
            .select_related("workplace")
            .order_by("day")
        )
        return Response(
            {
                "holidays": [
                    {
                        "day": row.day.isoformat(),
                        "name": row.name,
                        # `null` means the whole company, which is not the same as a
                        # holiday that happens to be at one site.
                        "workplace": row.workplace.name if row.workplace_id else None,
                    }
                    for row in rows
                ]
            }
        )
