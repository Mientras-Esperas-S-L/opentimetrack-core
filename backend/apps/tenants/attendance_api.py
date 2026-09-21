"""La asistencia, para la aplicación que la va a pintar en su pantalla.

`read:attendance` estaba declarado y no tenía endpoint, así que una herramienta
podía fichar en nombre de alguien y luego no podía enseñar el resultado. Para
Geosian esto es lo que sustituye a sus widgets de asistencia: la misma
información, pero desde el sistema que sabe defenderla ante una inspección.

Solo lectura, y a propósito. Todo lo que **cambia** el registro pasa por su
puerta: fichar por el fichaje delegado, corregir por el flujo del art. 4.b. Una
aplicación integrada no puede escribir en el registro por un atajo, porque
entonces las garantías serían opcionales.
"""

from __future__ import annotations

from datetime import date

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import HasApplicationScope
from apps.punches.delegated import resolve_employee
from apps.punches.services import build_day_status
from apps.tenants.applications import ApplicationScope


class TramoSerializer(serializers.Serializer):
    """Un tramo del día. Solo las horas: la IP y el dispositivo no salen."""

    in_ = serializers.DateTimeField(
        help_text="Cuándo empezó. En el JSON el campo se llama `in`.", source="in"
    )
    out = serializers.DateTimeField(
        allow_null=True, help_text="Cuándo terminó, o `null` si sigue abierto."
    )


class AsistenciaDeUnaPersonaSerializer(serializers.Serializer):
    employee = serializers.UUIDField()
    employee_id = serializers.CharField(help_text="Su número de empleado, si lo tiene.")
    name = serializers.CharField()
    state = serializers.ChoiceField(
        choices=["NOT_STARTED", "WORKING", "ON_BREAK", "OFF"],
        help_text="Cómo está ahora mismo.",
    )
    worked_seconds = serializers.IntegerField(help_text="Lo trabajado hoy, en segundos.")
    segments = TramoSerializer(many=True)


class AsistenciaDelDiaSerializer(serializers.Serializer):
    """Lo que responde la consulta de asistencia.

    Declarado de verdad y no como objeto libre: quien escribe un conector lee el
    esquema, y un `dict` a secas le obliga a deducir la forma probando ---o a
    descubrirla el día que cambia.
    """

    time_zone = serializers.CharField(help_text="La de la empresa.")
    day = serializers.DateField(help_text="El día en curso **en su zona**, no en UTC.")
    people = AsistenciaDeUnaPersonaSerializer(many=True)


@extend_schema(tags=["applications"])
class ApplicationAttendanceView(APIView):
    """El día en curso de una persona, o el de toda la plantilla."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_ATTENDANCE

    @extend_schema(
        summary="Today's attendance",
        description=(
            "Who is working right now and how long each person has worked today. "
            "With `employee_ref`, just that person. Requires `read:attendance`."
        ),
        parameters=[OpenApiParameter("employee_ref", str, description="Referencia externa")],
        responses={200: AsistenciaDelDiaSerializer},
    )
    def get(self, request):
        company = request.user.application.tenant
        wanted = request.query_params.get("employee_ref")

        if wanted:
            person = resolve_employee(wanted, company)
            if person is None:
                raise BusinessRuleError(
                    code="employee_not_found",
                    message=_("No active person matches that reference."),
                    details={"employee_ref": wanted},
                )
            people = [person]
        else:
            from apps.users.models import User

            # `person.tzinfo` mira el centro, y **el centro sin zona propia
            # cae en su empresa**: la cadena tiene un eslabón más de los que
            # parece. Con `workplace` a secas seguía habiendo una consulta por
            # persona, y era la de la empresa del centro. Se ve contando el SQL,
            # no leyendo el código.
            people = list(
                User.objects.filter(tenant=company, is_active=True).select_related(
                    "workplace__tenant", "tenant"
                )
            )

        return Response(
            {
                "time_zone": company.time_zone,
                # De la zona de la empresa, no del reloj del contenedor.
                #
                # `date.today()` da la fecha UTC del servidor, que entre
                # medianoche y las dos de la madrugada (en verano) no es la de
                # nadie en España: a las 00:30 de Madrid decía que era ayer
                # mientras los tramos ya eran de hoy. La aplicación que pinta
                # esto ponía la fecha de un día y los fichajes de otro, y quien
                # más lo sufre es el turno de noche, que es justo el que cruza
                # esa frontera todos los días.
                #
                # `apps/common/clock.py` existe por esto y avisa de que ya se
                # había colado cuatro veces. Esta era la quinta, y el único
                # `date.today()` que quedaba en todo el código.
                "day": local_today(company).isoformat(),
                "people": _attendance_of(people, company),
            }
        )


def _attendance_of(people, company) -> list[dict]:
    """La asistencia de toda esa gente, sin una consulta por cabeza.

    `build_day_status` cuesta dos consultas ---los fichajes y las reglas--- y
    `person.tzinfo` una tercera si el centro no viene traído. En una plantilla
    de doscientas eso eran seiscientas consultas para responder una pregunta, y
    esto lo llama un conector que puede preguntarlo a menudo.

    Ahora: los centros vienen con la gente, las reglas se leen una vez, y los
    fichajes del día salen en **una** consulta para todo el mundo.

    La ventana se coge con un día de margen a cada lado a propósito. El día de
    cada persona es el de **su** centro ---una oficina en Madrid y otra en Las
    Palmas van una hora aparte--- así que una sola ventana no puede ser exacta
    para todas a la vez: se pide de sobra y se recorta por persona en memoria,
    con sus propios límites. Recortar por la zona de la empresa habría movido el
    día de quien no está en ella, que es el fallo que este mismo fichero ya tuvo
    con `date.today()`.
    """
    from datetime import timedelta

    from apps.punches.models import Punch
    from apps.punches.services import local_day_bounds
    from apps.tenants.rules import WorkingTimeRules

    if not people:
        return []

    reglas = WorkingTimeRules.for_company(company)
    inicio, fin = local_day_bounds(company)
    eventos = Punch.objects.filter(
        employee__in=people,
        is_active=True,
        timestamp__gte=inicio - timedelta(days=1),
        timestamp__lt=fin + timedelta(days=1),
    ).order_by("timestamp")

    por_persona: dict = {}
    for evento in eventos:
        por_persona.setdefault(evento.employee_id, []).append(evento)

    salida = []
    for persona in people:
        propios, propio_fin = local_day_bounds(persona)
        suyos = [e for e in por_persona.get(persona.id, []) if propios <= e.timestamp < propio_fin]
        salida.append(_day_of(persona, company, events=suyos, rules=reglas))
    return salida


def _day_of(person, company, *, events=None, rules=None) -> dict:
    estado = build_day_status(person, company, events=events, rules=rules)
    return {
        "employee": str(person.id),
        "employee_id": person.employee_id,
        "name": person.get_full_name(),
        "state": estado.state,
        "worked_seconds": estado.worked_seconds,
        # Los tramos, sin la metadata de captura: la IP y el dispositivo son
        # datos de seguridad de esta empresa y no salen hacia otra aplicación
        # por el hecho de que pueda leer la asistencia.
        "segments": [
            {"in": s.start.isoformat(), "out": s.end.isoformat() if s.end else None}
            for s in estado.segments
        ],
    }


# ------------------------------------------------------------------ the range
#
# A month at a time, for the application that draws a calendar. `read:attendance`
# used to answer only "today", so a human resources screen had to call thirty
# times and still knew nothing about absences or holidays. This is one call per
# person-page with everything a day needs to be painted: what was worked, whether
# the roster expected work, whether it was a holiday at their workplace, and the
# absence that explains a gap. Still read-only, still without capture metadata.

#: Two months. Longer ranges are what reports are for, and a calendar never shows more.
MAX_RANGE_DAYS = 62
#: People per page. The cost is per person-day, so the page keeps the answer bounded.
PEOPLE_PER_PAGE = 100


class AbsenceInTheRangeSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="The leave type's code, or the absence type when there is none."
    )
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=["PENDING", "APPROVED"])
    partial = serializers.BooleanField(
        help_text="True when the absence covers hours, not the whole day."
    )


class DayInTheRangeSerializer(serializers.Serializer):
    day = serializers.DateField(help_text="In the person's zone.")
    state = serializers.ChoiceField(choices=["NOT_STARTED", "WORKING", "ON_BREAK", "OFF"])
    worked_seconds = serializers.IntegerField()
    segments = TramoSerializer(many=True)
    scheduled = serializers.BooleanField(
        allow_null=True,
        help_text="Whether the roster expected work; `null` if they have no roster in the range.",
    )
    holiday = serializers.CharField(
        allow_null=True, help_text="The holiday's name at their workplace, or `null`."
    )
    absence = AbsenceInTheRangeSerializer(allow_null=True)


class PersonInTheRangeSerializer(serializers.Serializer):
    employee = serializers.UUIDField()
    employee_id = serializers.CharField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()
    days = DayInTheRangeSerializer(many=True)


class AttendanceRangeSerializer(serializers.Serializer):
    time_zone = serializers.CharField(help_text="The company's.")
    from_day = serializers.DateField(
        help_text="In the JSON the field is called `from`.", source="from"
    )
    to = serializers.DateField()
    count = serializers.IntegerField(help_text="How many people match, in total.")
    page = serializers.IntegerField()
    has_more = serializers.BooleanField()
    people = PersonInTheRangeSerializer(many=True)


def _parse_range(params) -> tuple[date, date, int]:
    """`from`, `to` (both included) and `page`, or a 400 that names the field."""
    from django.utils.dateparse import parse_date

    errors = {}
    first = parse_date(params.get("from") or "")
    last = parse_date(params.get("to") or "")
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
    try:
        page = max(1, int(params.get("page", 1)))
    except TypeError, ValueError:
        raise serializers.ValidationError({"page": [_("Must be a whole number.")]}) from None
    return first, last, page


def _absence_as_dict(absence) -> dict | None:
    if absence is None:
        return None
    leave_type = absence.leave_type if absence.leave_type_id else None
    return {
        "code": (leave_type.code if leave_type and leave_type.code else absence.absence_type),
        "name": leave_type.name if leave_type else absence.get_absence_type_display(),
        "status": absence.status,
        "partial": bool(absence.start_time or absence.end_time),
    }


@extend_schema(tags=["applications"])
class ApplicationAttendanceRangeView(APIView):
    """A range of days, per person, with what a calendar needs to paint each one."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_ATTENDANCE

    @extend_schema(
        summary="Attendance over a range of days",
        description=(
            "For every person and every day between `from` and `to` (both included, at most "
            "62 days): state, worked seconds, segments, whether the roster expected work, the "
            "holiday at their workplace and the absence covering the day. Paged by person. "
            "With `employee_ref`, just that person, active or not. Requires `read:attendance`."
        ),
        parameters=[
            OpenApiParameter("from", str, required=True, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, required=True, description="YYYY-MM-DD, included"),
            OpenApiParameter("employee_ref", str, description="External reference of one person"),
            OpenApiParameter("page", int, description="Page of people, from 1"),
        ],
        responses={200: AttendanceRangeSerializer},
    )
    def get(self, request):
        from datetime import datetime, time, timedelta

        from apps.absences.models import Absence, AbsenceStatus
        from apps.punches.models import Punch
        from apps.punches.services import local_day_bounds
        from apps.shifts.models import Shift, working_days_between
        from apps.tenants.holidays import PublicHoliday
        from apps.tenants.people_api import _resolve
        from apps.tenants.rules import WorkingTimeRules
        from apps.users.models import User

        company = request.user.application.tenant
        first, last, page = _parse_range(request.query_params)
        wanted = request.query_params.get("employee_ref")

        if wanted:
            # Active or not: the calendar of somebody who left mid-month is still theirs.
            person = _resolve(wanted, company)
            if person is None:
                raise BusinessRuleError(
                    code="employee_not_found",
                    message=_("No person matches that reference."),
                    details={"employee_ref": wanted},
                )
            people, count, has_more = [person], 1, False
        else:
            everybody = (
                User.objects.filter(tenant=company, is_active=True)
                .select_related("workplace__tenant", "tenant")
                .order_by("last_name", "first_name", "id")
            )
            count = everybody.count()
            people = list(everybody[(page - 1) * PEOPLE_PER_PAGE : page * PEOPLE_PER_PAGE])
            has_more = page * PEOPLE_PER_PAGE < count

        rules = WorkingTimeRules.for_company(company)
        # The window in the company's zone with a day of margin each side, then cut
        # per person in memory: two workplaces an hour apart do not share a midnight.
        noon = time(12)
        start, _ignored = local_day_bounds(
            company, datetime.combine(first, noon, tzinfo=company.tzinfo)
        )
        _ignored, end = local_day_bounds(
            company, datetime.combine(last, noon, tzinfo=company.tzinfo)
        )
        events = Punch.objects.filter(
            employee__in=people,
            is_active=True,
            timestamp__gte=start - timedelta(days=1),
            timestamp__lt=end + timedelta(days=1),
        ).order_by("timestamp")
        by_person = {person.id: person for person in people}
        by_person_day: dict = {}
        for event in events:
            owner = by_person[event.employee_id]
            day = event.timestamp.astimezone(owner.tzinfo).date()
            by_person_day.setdefault((owner.id, day), []).append(event)

        absences: dict = {}
        for absence in (
            Absence.objects.filter(employee__in=people, start_date__lte=last, end_date__gte=first)
            .exclude(status=AbsenceStatus.REJECTED)
            .select_related("leave_type")
            .order_by("start_date")
        ):
            absences.setdefault(absence.employee_id, []).append(absence)

        rostered: dict = {}
        for employee_id, day in Shift.objects.filter(
            employee__in=people, day__gte=first, day__lte=last
        ).values_list("employee_id", "day"):
            rostered.setdefault(employee_id, set()).add(day)

        holiday_names: dict = {}
        for workplace_id, day, name in PublicHoliday.objects.filter(
            day__gte=first, day__lte=last
        ).values_list("workplace_id", "day", "name"):
            holiday_names[(workplace_id, day)] = name

        answer = []
        for person in people:
            roster = rostered.get(person.id)
            days = []
            for day in working_days_between(first, last):
                status = build_day_status(
                    person, company, events=by_person_day.get((person.id, day), []), rules=rules
                )
                covering = next(
                    (a for a in absences.get(person.id, []) if a.start_date <= day <= a.end_date),
                    None,
                )
                days.append(
                    {
                        "day": day.isoformat(),
                        "state": status.state,
                        "worked_seconds": status.worked_seconds,
                        "segments": [
                            {"in": s.start.isoformat(), "out": s.end.isoformat() if s.end else None}
                            for s in status.segments
                        ],
                        "scheduled": (day in roster) if roster is not None else None,
                        "holiday": holiday_names.get((person.workplace_id, day))
                        or holiday_names.get((None, day)),
                        "absence": _absence_as_dict(covering),
                    }
                )
            answer.append(
                {
                    "employee": str(person.id),
                    "employee_id": person.employee_id,
                    "name": person.get_full_name(),
                    "is_active": person.is_active,
                    "days": days,
                }
            )

        return Response(
            {
                "time_zone": company.time_zone,
                "from": first.isoformat(),
                "to": last.isoformat(),
                "count": count,
                "page": page,
                "has_more": has_more,
                "people": answer,
            }
        )
