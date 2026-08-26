"""Clock-in business rules.

Kept out of the views on purpose: the same rules have to hold whether the event
arrives from the web panel, the mobile app, an external application or a data
import. A rule living in a view is a rule that only applies to one door.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps import legal
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.transitions import hold
from apps.punches.models import (
    HoursNature,
    Punch,
    PunchInterval,
    PunchSource,
    PunchTrigger,
    PunchType,
)


@dataclass(frozen=True)
class DaySegment:
    """A stretch of time: an opening event and, if it has happened, its close.

    Not necessarily work. Art. 3 of the pending decree asks for four kinds of
    span, and only one of them counts towards the hours: a break or a stretch
    of waiting time is recorded precisely **because** it does not.
    """

    start: datetime
    end: datetime | None
    interval: str = PunchInterval.WORK
    work_mode: str = ""
    hours_nature: str = HoursNature.ORDINARY
    overtime_settlement: str = ""
    force_majeure: bool = False
    flexibility_measure: str = ""

    @property
    def seconds(self) -> int:
        finish = self.end or timezone.now()
        return int((finish - self.start).total_seconds())

    @property
    def is_open(self) -> bool:
        return self.end is None

    @property
    def counts_as_work(self) -> bool:
        """Only the working day does.

        Whether the fifteen-minute break counts is a matter for the collective
        agreement (art. 34.4 ET), and `WorkingTimeRules.break_counts_as_work`
        holds that answer --- but a span recorded as BREAK was recorded as time
        that is not working time. Deciding otherwise here would overrule what
        the entry itself says.
        """
        return self.interval == PunchInterval.WORK

    def as_dict(self) -> dict:
        return {
            "in": self.start.isoformat(),
            "out": self.end.isoformat() if self.end else None,
            "seconds": self.seconds,
            "interval": self.interval,
            "work_mode": self.work_mode,
            "hours_nature": self.hours_nature,
            "overtime_settlement": self.overtime_settlement,
            "force_majeure": self.force_majeure,
            "flexibility_measure": self.flexibility_measure,
            "counts_as_work": self.counts_as_work,
        }


@dataclass(frozen=True)
class DayStatus:
    state: str  # WORKING | ON_BREAK | OFF | NOT_STARTED
    segments: list[DaySegment]
    worked_seconds: int

    @property
    def break_seconds(self) -> int:
        return sum(s.seconds for s in self.segments if s.interval == PunchInterval.BREAK)

    @property
    def standby_seconds(self) -> int:
        return sum(s.seconds for s in self.segments if s.interval == PunchInterval.STANDBY)

    @property
    def overtime_seconds(self) -> int:
        return sum(
            s.seconds
            for s in self.segments
            if s.counts_as_work and s.hours_nature == HoursNature.OVERTIME
        )

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "segments": [s.as_dict() for s in self.segments],
            "worked_seconds": self.worked_seconds,
            # Art. 3.d and 3.g: recorded, and reported apart from the hours,
            # because the point of recording them is that they do not count.
            "break_seconds": self.break_seconds,
            "standby_seconds": self.standby_seconds,
            "overtime_seconds": self.overtime_seconds,
        }


def local_day_bounds(where, moment: datetime | None = None) -> tuple[datetime, datetime]:
    """Start and end of the working day **in the right local zone**.

    Not a trivial detail: the boundary of a day is a local matter. Slicing by UTC
    would split the day wrongly for anyone east or west of Greenwich, and it was
    already wrong within Spain --- this docstring said so about the Canary
    Islands for months before there was anywhere to record the answer.

    `where` is anything that knows its zone: a company, a workplace, or a
    person. A person answers with their workplace's, falling back to the
    company's, which is the whole point --- an office in Madrid and another in
    Las Palmas are one hour apart, and one hour is the difference between a
    punch landing on Monday and on Sunday.
    """
    moment = moment or timezone.now()
    local = moment.astimezone(where.tzinfo)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local, start_local + timedelta(days=1)


def punches_of_the_day(employee, company, day: date | None = None, *, rules=None):
    """Los fichajes de la jornada de ese día.

    De la **jornada**, no del día natural: quien entra el martes a las 22:00 y
    sale el miércoles a las 06:00 ha hecho ocho horas del martes, y el miércoles
    no ha trabajado. El porqué, con los artículos, está en `apps.punches.workday`.

    Sin día se entiende «la jornada de ahora»: la que esté abierta si la hay, y
    si no la de hoy. No es lo mismo que «hoy», y esa diferencia es la que hacía
    que a las tres de la mañana un turno de noche viera «sin empezar» en su
    propia pantalla mientras estaba trabajando.
    """
    from apps.punches.workday import current_workday, punches_of_the_workday

    tope = max_open_hours(employee, company, rules)
    if day is None:
        day = current_workday(employee, max_open_hours=tope)
    return punches_of_the_workday(employee, day, max_open_hours=tope)


#: Cuánto puede seguir abierto un intervalo y que el siguiente fichaje lo cierre.
#:
#: Existe por el turno de noche. Mirando solo «hoy», quien entra a las 22:00 y
#: sale a las 06:00 recibía **dos entradas y ninguna salida**: al salir, su día
#: local no tenía ningún fichaje y la deducción decía «entrada». La jornada no
#: se cerraba nunca, el día quedaba en cero horas y la persona figuraba
#: trabajando indefinidamente. En una empresa de vigilancia, de limpieza o de
#: residencias, eso es el registro entero mal.
#:
#: Y un tope hace falta: sin él, quien se olvidó de fichar la salida el lunes
#: vería su entrada del martes leída como el cierre del lunes, que es otro error
#: distinto y peor de deshacer. Para eso está el mecanismo de correcciones.
#:
#: Dieciséis horas es el **suelo por defecto**, no la regla: la frontera entre
#: «cerró tarde» y «se olvidó» no la fija ningún artículo, así que la pone cada
#: empresa en `WorkingTimeRules.max_open_hours`. Dieciséis cubre la jornada
#: partida más larga que se ve ---de 8:00 a 20:00 son doce horas de reloj--- y
#: se queda por debajo de veinticuatro para que un día de silencio se cace.
#:
#: Quien tiene guardias de veinticuatro horas ---bomberos, residencias,
#: vigilancia--- necesita subirlo, o dieciséis le parte la guardia en dos.
DEFAULT_MAX_OPEN_HOURS = 16


def max_open_hours(employee, company=None, rules=None) -> int:
    """Cuánto aguanta abierta una jornada en esta empresa.

    **Público, y hay una razón.** Lo usa también el informe: si cada uno resuelve
    el tope por su cuenta, la pantalla y el documento dejan de decir lo mismo.
    Pasó con un cero ---aquí caía al valor por defecto y allí se quedaba en
    cero--- y una jornada de noche bien fichada salía como «entrada sin salida».

    `rules` se puede pasar hecho: quien recorre a mucha gente ya lo trae, y
    resolverlo por persona sería una consulta por cabeza. `for_company` lo
    memoriza en la empresa, así que las llamadas sueltas tampoco duelen.
    """
    if rules is None:
        from apps.tenants.rules import WorkingTimeRules

        company = company or getattr(employee, "tenant", None)
        if company is None:
            return DEFAULT_MAX_OPEN_HOURS
        rules = WorkingTimeRules.for_company(company)
    return getattr(rules, "max_open_hours", None) or DEFAULT_MAX_OPEN_HOURS


def _last_open(employee, interval: str, *, rules=None):
    """El último evento de ese intervalo que aún puede pertenecer a la jornada
    en curso, sea de hoy o de anoche. Devuelve `None` si no hay ninguno."""
    frontera = timezone.now() - timedelta(hours=max_open_hours(employee, rules=rules))
    return (
        Punch.objects.filter(
            employee=employee,
            is_active=True,
            interval=interval,
            timestamp__gte=frontera,
        )
        .order_by("timestamp")
        .last()
    )


def work_is_open(employee, *, rules=None) -> bool:
    """Si la jornada está abierta ahora mismo, cruce o no la medianoche.

    `build_day_status` responde por **días locales**, y para un turno de noche
    eso no vale: pasada la medianoche el día nuevo no tiene ningún fichaje y la
    jornada abierta parece cerrada. Con esa lectura, quien entró a las diez no
    podía empezar una pausa a las tres --- el producto le respondía que su
    jornada tenía que estar abierta primero.
    """
    ultimo = _last_open(employee, PunchInterval.WORK, rules=rules)
    return ultimo is not None and ultimo.punch_type == PunchType.IN


def infer_type(employee, company, interval: str = PunchInterval.WORK, *, rules=None) -> str:
    """Opens or closes, worked out from the last event **of that interval**.

    The person is not asked which one it is: one tap, no choices, no chance of
    picking the wrong one.

    Per interval, because they nest. Starting a break while the working day is
    open must not be read as closing the day, and it would be if the last event
    of any kind decided.

    Y **no por días**, que es lo que estaba mal: un turno de noche cruza la
    medianoche y su salida cae en otro día local que el de su entrada. Lo que
    decide es el último evento de ese intervalo, esté en el día que esté,
    siempre que siga abierto y no haya pasado tanto tiempo que ya no pueda ser
    la misma jornada (el tope de la empresa).
    """
    last = _last_open(employee, interval, rules=rules)
    if last is None or last.punch_type == PunchType.OUT:
        return PunchType.IN
    return PunchType.OUT


def build_day_status(
    employee, company, day: date | None = None, *, events=None, rules=None
) -> DayStatus:
    """The day, as the record holds it.

    Whether a break comes off the hours is **the company's rule, not ours**.
    Art. 34.4 ET makes the fifteen-minute break working time only when the
    agreement or the contract says so --- and a good many agreements do. Always
    deducting it would take roughly fifty-five hours a year off every worker in
    those companies, quietly and in the direction that favours the employer.

    `events` y `rules` se pueden pasar hechos. Por sí sola esta función cuesta
    dos consultas, y en un bucle sobre la plantilla eso son dos por persona ---
    la asistencia de una empresa de doscientas eran seiscientas consultas para
    responder una pregunta. Quien recorre a mucha gente los trae de una vez; el
    resto llama igual que siempre y no se entera.
    """
    from apps.tenants.rules import WorkingTimeRules

    if rules is None:
        rules = WorkingTimeRules.for_company(company)
    if events is None:
        events = list(punches_of_the_day(employee, company, day, rules=rules))

    segments: list[DaySegment] = []
    # One open span per kind of interval. A break happens *inside* the working
    # day, so the day stays open while the break runs; pairing them in a single
    # stack would close the day at the first break and reopen it after, which
    # is a different fact.
    open_events: dict[str, Punch] = {}

    for event in events:
        kind = event.interval
        if event.punch_type == PunchType.IN:
            # Two openings in a row should not happen, but if they do the first
            # one wins rather than being silently dropped.
            open_events.setdefault(kind, event)
        elif kind in open_events:
            opening = open_events.pop(kind)
            segments.append(_span(opening, event.timestamp))

    for opening in open_events.values():
        segments.append(_span(opening, None))

    segments.sort(key=lambda s: s.start)

    worked = sum(s.seconds for s in segments if s.counts_as_work)
    if not rules.break_counts_as_work:
        worked -= sum(s.seconds for s in segments if s.interval == PunchInterval.BREAK)
    worked = max(worked, 0)

    if not events:
        state = "NOT_STARTED"
    elif PunchInterval.BREAK in open_events:
        state = "ON_BREAK"
    elif PunchInterval.WORK in open_events:
        state = "WORKING"
    else:
        state = "OFF"

    return DayStatus(state=state, segments=segments, worked_seconds=worked)


def _span(opening: Punch, end) -> DaySegment:
    """Builds the span from its opening event.

    Everything descriptive travels on the opening: it is the event that says
    what this stretch of time is, and the closing one only says when it ended.
    """
    return DaySegment(
        start=opening.timestamp,
        end=end,
        interval=opening.interval,
        work_mode=opening.work_mode,
        hours_nature=opening.hours_nature,
        overtime_settlement=opening.overtime_settlement,
        force_majeure=opening.force_majeure,
        flexibility_measure=opening.flexibility_measure,
    )


#: Cuánto tiene que pasar entre dos eventos de la misma persona para que el
#: segundo se crea. Ver `_refuse_a_double_tap`.
DOUBLE_TAP_SECONDS = 5


def _refuse_a_double_tap(employee, company, interval: str) -> None:
    """Dos eventos seguidos de la misma persona son un dedo, no dos hechos.

    El tipo se deduce del estado, así que dos peticiones seguidas no crean dos
    entradas: crean **una entrada y una salida**. Medido el 13/08/2026 con
    milisegundo y medio entre ellas, el día quedaba en cero segundos trabajados
    y en estado «fuera». Quien había pulsado se iba convencido de haber fichado.

    Y no hace falta mala suerte: un doble toque en un móvil, una pantalla que
    tarda en responder y se vuelve a pulsar, o un reintento del cliente cuando
    la petición ya había llegado. En una obra, con guantes, es un martes.

    El sitio es este y no la pantalla. El botón ya se desactiva mientras la
    petición viaja, pero eso no cubre el toque más rápido que el repintado, ni
    dos pestañas, ni un terminal, ni un conector --- y todos escriben aquí.

    **Se rechaza, no se ignora.** Tragarse el segundo dejaría el registro bien y
    a la persona sin saber qué pasó; el error dice que ya se fichó hace un
    momento, que es la verdad y lo que evita el tercer intento.

    Cinco segundos: de sobra para el dedo y el reintento, poco para estorbar a
    quien sale y vuelve a entrar porque se lo ha pensado mejor.
    """
    from django.utils import timezone

    # El último de ese intervalo, **sin acotar por día**. Miraba «los de hoy», y
    # a caballo de la medianoche eso deja de proteger: pulsar a las 23:59:58 y
    # otra vez a las 00:00:01 daba dos fichajes, porque el día nuevo estaba
    # vacío. Un turno que empieza a las 00:00 no es raro en una empresa que
    # trabaja de noche, y es justo el fallo que esta guarda existe para evitar.
    last = _last_open(employee, interval)
    if last is None:
        return

    elapsed = (timezone.now() - last.timestamp).total_seconds()
    if 0 <= elapsed < DOUBLE_TAP_SECONDS:
        raise BusinessRuleError(
            code="punch_too_soon",
            message=_("You clocked a moment ago. Check the screen before clocking again."),
        )


@transaction.atomic
def register_punch(
    *,
    employee,
    company,
    source: str = PunchSource.WEB,
    source_application: str = "",
    recorded_by=None,
    ip_address: str | None = None,
    device_id: str = "",
    user_agent: str = "",
    interval: str = PunchInterval.WORK,
    work_mode: str = "",
    hours_nature: str = HoursNature.ORDINARY,
    overtime_settlement: str = "",
    force_majeure: bool = False,
    flexibility_measure: str = "",
    trigger: str = PunchTrigger.MANUAL,
    evidence: dict | None = None,
) -> Punch:
    """Record a clock event. The only supported way to create one.

    Everything that must be true of every event happens here: server timestamp,
    inferred type, business checks and integrity hash.
    """
    if not employee.is_active:
        raise BusinessRuleError(
            code="employee_inactive",
            message=_("This person is deactivated and cannot clock in or out."),
        )

    # Antes de leer el último fichaje, y esto es lo que hace que la comprobación
    # de abajo sirva de algo: sin el bloqueo, dos peticiones simultáneas de la
    # misma persona leen el mismo «último» y las dos pasan. Medido con dos hilos,
    # catorce de quince rondas dejaban **dos fichajes en el registro**.
    #
    # Se bloquea a la persona porque no hay fila de estado que bloquear: un
    # fichaje no modifica al anterior. Serializa solo sus propias pulsaciones.
    hold(type(employee), employee.pk)

    _refuse_a_double_tap(employee, company, interval)

    punch_type = infer_type(employee, company, interval)

    # Only when starting a working day. Somebody on an approved holiday is not
    # blocked from closing a day they had already opened, and blocking the end
    # of a break would strand them mid-shift.
    if interval == PunchInterval.WORK and punch_type == PunchType.IN:
        _check_no_approved_absence(employee, company)

    # A break can only start inside a working day. Otherwise the record ends up
    # with a break floating in the middle of nothing, which no reader can
    # interpret and no inspector should have to.
    if interval != PunchInterval.WORK and punch_type == PunchType.IN:
        # Por el intervalo abierto y no por el día local: un turno de noche cruza
        # la medianoche y su jornada sigue abierta aunque el día nuevo esté
        # vacío. Con la lectura por días, quien entró a las diez no podía
        # empezar una pausa a las tres.
        if not work_is_open(employee):
            raise BusinessRuleError(
                code="not_working",
                message=_("The working day has to be open first."),
            )

    # Art. 12.4.c ET, literal: «Los trabajadores a tiempo parcial no podrán
    # realizar horas extraordinarias, salvo en los supuestos a los que se
    # refiere el artículo 35.3» --- las de fuerza mayor. What part-time work has
    # instead is complementary hours (art. 12.5), counted separately, which is
    # why HoursNature keeps them apart.
    # Art. 6.3 ET: «Se prohíbe realizar horas extraordinarias a los menores de
    # dieciocho años.» Flat, with none of the force majeure exception that
    # art. 12.4.c grants part-time work --- so this check comes first and has no
    # way out.
    framework = legal.for_company(company)

    if (
        hours_nature == HoursNature.OVERTIME
        and framework.minors.overtime_forbidden
        and employee.is_minor_on(timezone.localdate())
    ):
        raise BusinessRuleError(
            code="overtime_forbidden_for_minors",
            message=_("%(basis)s: workers under eighteen may not work overtime.")
            % {"basis": framework.minors.citations["overtime"].basis},
        )

    if hours_nature == HoursNature.OVERTIME and employee.part_time and not force_majeure:
        raise BusinessRuleError(
            code="overtime_not_available_part_time",
            message=_(
                "Art. 12.4.c ET: part-time work admits no overtime, only complementary "
                "hours --- except hours to prevent or repair urgent damage."
            ),
        )

    if hours_nature == HoursNature.OVERTIME and not overtime_settlement:
        # Art. 3.f asks how it settles. Recording overtime without saying is
        # recording half the fact.
        raise BusinessRuleError(
            code="overtime_settlement_required",
            message=_("Say whether the overtime is paid or compensated with rest."),
        )

    punch = Punch(
        tenant=company,
        employee=employee,
        punch_type=punch_type,
        # Server time. Never from the client, ever.
        timestamp=timezone.now(),
        # Y el huso en el que se vive esa hora, congelado con ella: leerla más
        # tarde con el huso de hoy convierte un cambio de organización en un
        # cambio del registro.
        time_zone=str(employee.tzinfo),
        source=source,
        source_application=source_application,
        recorded_by=recorded_by,
        ip_address=ip_address,
        device_id=device_id,
        user_agent=user_agent,
        interval=interval,
        work_mode=work_mode or employee.default_work_mode,
        hours_nature=hours_nature,
        overtime_settlement=overtime_settlement,
        force_majeure=force_majeure,
        flexibility_measure=flexibility_measure,
        trigger=trigger,
        evidence=evidence or {},
    )
    punch.save()
    return punch


def _check_no_approved_absence(employee, company) -> None:
    """Approved leave blocks clocking in.

    Imported lazily because `punches` must not depend on `absences` at module
    level: the dependency graph in the component view only allows it the other
    way round.
    """
    from apps.absences.models import STOPS_THE_WHOLE_DAY, Absence, AbsenceStatus

    # The person's today, not the company's: the Canary delegation is an hour
    # behind Madrid, and between 23:00 and midnight there the two dates differ
    # --- which decides whether tomorrow's approved leave already blocks.
    today = local_today(employee)

    # Only what stops the whole day. Two things do not, and both are ordinary:
    # somebody who left at eleven with a fever worked the morning --- blocking
    # their clock-out would leave the day open, the one thing a record must
    # never do --- and somebody on an ERTE that reduces their day by forty per
    # cent still comes in for the other sixty.
    absence = (
        Absence.objects.filter(
            employee=employee,
            status=AbsenceStatus.APPROVED,
            start_date__lte=today,
            end_date__gte=today,
        )
        .filter(STOPS_THE_WHOLE_DAY)
        .first()
    )

    if absence is not None:
        raise BusinessRuleError(
            code="punch_blocked_by_absence",
            message=_("You cannot clock in: you have approved leave for today."),
            details={"absence_id": str(absence.id), "date": today.isoformat()},
        )
