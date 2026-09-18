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


class LeaveTypeOutSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    family = serializers.CharField(help_text="What it behaves like: VACATION, SICK_LEAVE, …")
    basis = serializers.CharField(help_text="The article it comes from, when it has one.")


class LeaveTypesAnswerSerializer(serializers.Serializer):
    leave_types = LeaveTypeOutSerializer(many=True)


@extend_schema(tags=["applications"])
class ApplicationLeaveTypesView(APIView):
    """This company's catalogue of leave, so the other side can name one.

    Requesting leave needs a code, and the catalogue is the company's: seeded from the
    country's law and then grown by whatever its agreement adds. Without this, whoever
    configures the other application is mapping their own states onto codes they cannot
    see, and finds out they guessed wrong the first time somebody asks for a day off.
    """

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_ABSENCES

    @extend_schema(
        summary="The company's leave catalogue",
        description=(
            "Every leave type this company recognises, with the code that "
            "`POST /api/app/absences/` expects. Requires `read:absences`."
        ),
        responses={200: LeaveTypesAnswerSerializer},
    )
    def get(self, request):
        from apps.absences.models import LeaveType

        company = request.user.application.tenant
        rows = LeaveType.objects.filter(tenant=company, is_active=True).order_by("name")
        return Response(
            {
                "leave_types": [
                    {
                        "code": row.code,
                        "name": row.name,
                        "family": row.family,
                        "basis": row.basis,
                    }
                    for row in rows
                    # Sin código no hay nada que pedir desde fuera: son los que la
                    # empresa se inventó y solo existen dentro de su propia pantalla.
                    if row.code
                ]
            }
        )


# --------------------------------------------------------------- availability


class DayAvailabilitySerializer(serializers.Serializer):
    day = serializers.DateField()
    available = serializers.BooleanField(help_text="Whether they can be given work that day.")
    rostered_minutes = serializers.IntegerField(help_text="0 when nothing was planned.")
    holiday = serializers.CharField(
        allow_null=True, help_text="The name of the public holiday at their site, or null."
    )
    absence = serializers.CharField(
        allow_null=True,
        help_text=(
            "Why they are off, when saying so is proportionate. Sick leave answers "
            "`unavailable` without naming anything."
        ),
    )


class PersonAvailabilitySerializer(serializers.Serializer):
    employee = serializers.UUIDField()
    employee_id = serializers.CharField()
    days = DayAvailabilitySerializer(many=True)


class AvailabilityAnswerSerializer(serializers.Serializer):
    people = PersonAvailabilitySerializer(many=True)


@extend_schema(tags=["applications"])
class ApplicationAvailabilityView(APIView):
    """Who can be given work on a given day, and who cannot.

    The question an application asks **before** assigning, and the reason it can drop
    its own planning module without losing the planning. This system says when somebody
    can work; the application says what they do with that time.

    It answers the three things that make a day unavailable and it answers them
    together, because separately they are three calls and a join at the other end: the
    shift that was planned, the leave that covers the day, and whether the day is a
    public holiday **at their site** --- at the site they were assigned to *that day*,
    which is not the same as today's once somebody has been transferred.

    **It does not say why somebody is off when the reason is medical.** A planner needs
    to know that Tuesday is not available; they do not need the diagnosis, and health
    data is special category under art. 9 GDPR. Everything else names its leave type,
    which is what lets a planner tell a holiday they could ask to move from a legal
    permit they cannot.

    It does not block clocking in. Somebody who turns up and works gets their day
    recorded whatever this said --- the record is of what happened, not of what was
    foreseen.
    """

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_AVAILABILITY

    @extend_schema(
        summary="Who can work over a range",
        description=(
            "Per person and day: whether they are available, the minutes rostered, the "
            "public holiday at their workplace, and the leave that covers the day. Sick "
            "leave is reported as unavailable **without naming it**. Requires "
            "`read:availability`."
        ),
        parameters=[
            OpenApiParameter("from", str, required=True),
            OpenApiParameter("to", str, required=True),
            OpenApiParameter("employee_ref", str),
        ],
        responses={200: AvailabilityAnswerSerializer},
    )
    def get(self, request):
        from datetime import timedelta

        from apps.absences.models import STOPS_THE_WHOLE_DAY, Absence, AbsenceStatus, AbsenceType
        from apps.shifts.models import Shift
        from apps.tenants.holidays import PublicHoliday
        from apps.users.workplace_history import workplaces_by_person

        company = request.user.application.tenant
        first, last = _range(request.query_params)
        people = _people_of(request, company)

        # Todo de una vez: por persona y día serían tres consultas por celda, y el mes
        # de una plantilla de cien son nueve mil.
        turnos: dict = {}
        for shift in Shift.objects.filter(employee__in=people, day__gte=first, day__lte=last):
            turnos[(shift.employee_id, shift.day)] = shift.minutes

        ausencias: dict = {}
        for row in (
            Absence.objects.filter(employee__in=people, start_date__lte=last, end_date__gte=first)
            .filter(STOPS_THE_WHOLE_DAY)
            .filter(status=AbsenceStatus.APPROVED)
            .select_related("leave_type")
        ):
            dia = max(row.start_date, first)
            while dia <= min(row.end_date, last):
                ausencias.setdefault((row.employee_id, dia), row)
                dia += timedelta(days=1)

        festivos: dict = {}
        for centro_id, dia, nombre in PublicHoliday.objects.filter(
            tenant=company, day__gte=first, day__lte=last
        ).values_list("workplace_id", "day", "name"):
            festivos[(centro_id, dia)] = nombre

        # El centro **de cada día**: a quien se trasladó en abril, los festivos de marzo
        # le tocan por su centro de entonces. Ver apps/users/workplace_history.py.
        centros = workplaces_by_person(people, first, last)

        return Response(
            {
                "people": [
                    {
                        "employee": str(person.id),
                        "employee_id": person.employee_id,
                        "days": [
                            self._day(
                                person, dia, turnos, ausencias, festivos, centros, AbsenceType
                            )
                            for dia in _every_day(first, last)
                        ],
                    }
                    for person in people
                ]
            }
        )

    @staticmethod
    def _day(person, dia, turnos, ausencias, festivos, centros, AbsenceType) -> dict:
        centro = centros.get(person.id, {}).get(dia) or person.workplace
        festivo = festivos.get((None, dia)) or (festivos.get((centro.id, dia)) if centro else None)
        ausencia = ausencias.get((person.id, dia))

        # La baja médica se dice como «no disponible» y nada más: quien planifica no
        # necesita el diagnóstico, y es dato de salud (art. 9 RGPD).
        motivo = None
        if ausencia is not None and ausencia.absence_type != AbsenceType.SICK_LEAVE:
            motivo = (
                ausencia.leave_type.name
                if ausencia.leave_type_id
                else ausencia.get_absence_type_display()
            )

        return {
            "day": dia.isoformat(),
            "available": ausencia is None and festivo is None,
            "rostered_minutes": turnos.get((person.id, dia), 0),
            "holiday": festivo,
            "absence": motivo,
        }


def _every_day(first: date, last: date):
    from datetime import timedelta

    dia = first
    while dia <= last:
        yield dia
        dia += timedelta(days=1)
