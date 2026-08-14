"""Leave: requesting it, resolving it, and counting what is left.

Leave is not HR bookkeeping here. An approved absence blocks clocking in, so it
belongs to the same record the labour inspector reads, and the rules that govern
it have to be as explicit as the ones governing a clock event.

Two decisions worth stating up front:

- **The reference period is configurable.** Holiday entitlement is not tied to
  the calendar year by law: the collective agreement may set another period.
  Hardcoding January-December would quietly produce a wrong balance for
  everybody on a different one. See `leave_period_for`.
- **Entitlement is a parameter, not a truth.** The number of days comes from the
  agreement. The system holds a figure the company can change, and does not
  pretend to know better.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.absences.models import REDUCES_THE_DAY, Absence, AbsenceStatus, AbsenceType
from apps.common.clock import local_date_of
from apps.common.transitions import claim
from apps.common.exceptions import BusinessRuleError
from apps.common.four_eyes import refuse_self_decision

# ------------------------------------------------------------------- the period


def leave_period_for(company, day: date | None = None) -> tuple[date, date]:
    """The reference period containing `day`, as [start, end].

    Starts on `company.leave_year_start_month`. With the default (January) this
    is the calendar year; with any other month it is the twelve months from
    there, which is what an agreement running April-March needs.
    """
    day = day or timezone.localdate()
    start_month = company.leave_year_start_month

    start_year = day.year if day.month >= start_month else day.year - 1
    start = date(start_year, start_month, 1)

    end_year = start_year + 1 if start_month > 1 else start_year
    end_month = start_month - 1 if start_month > 1 else 12
    last_day = _last_day_of(end_year, end_month)

    return start, date(end_year, end_month, last_day)


def _last_day_of(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timezone.timedelta(days=1)).day


# ------------------------------------------------------------------ the balance


@dataclass(frozen=True)
class LeaveBalance:
    """What somebody is entitled to, has taken, and has left."""

    period_start: date
    period_end: date
    entitled: int
    taken: int
    pending: int
    #: Lo que daría el periodo completo, cuando la persona no lo ha trabajado
    #: entero. `None` cuando sí. La pantalla lo necesita para poder explicar de
    #: dónde sale la cifra: «19 de 23, por haber entrado el 9 de marzo».
    full_year: int | None = None
    #: El tramo del periodo que la persona tiene contrato, cuando no es todo.
    accrued_from: date | None = None
    accrued_to: date | None = None
    #: Which unit all three figures are in. Served rather than assumed: "quedan
    #: 9" means something different in working days than in calendar days, and
    #: the screen showing it has no other way to know which.
    working_days: bool = True

    @property
    def remaining(self) -> int:
        """Pending requests count against it. Showing them as available is how
        two people end up booking the same last day."""
        return self.entitled - self.taken - self.pending

    @property
    def prorated(self) -> bool:
        return self.full_year is not None and self.full_year != self.entitled

    def as_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "entitled": self.entitled,
            "taken": self.taken,
            "pending": self.pending,
            "remaining": self.remaining,
            "working_days": self.working_days,
            # Enseñar solo «19» sin decir por qué son diecinueve y no
            # veintitrés es la clase de cifra que acaba en una discusión.
            "prorated": self.prorated,
            "full_year": self.full_year,
            "accrued_from": self.accrued_from.isoformat() if self.accrued_from else None,
            "accrued_to": self.accrued_to.isoformat() if self.accrued_to else None,
        }


def vacation_balance(employee, company, day: date | None = None) -> LeaveBalance:
    start, end = leave_period_for(company, day)

    full_year = employee.annual_leave_days
    if full_year is None:
        full_year = company.annual_leave_days

    entitled, accrued_from, accrued_to = _accrued(employee, full_year, start, end)

    inside = Absence.objects.filter(
        employee=employee,
        absence_type=AbsenceType.VACATION,
        start_date__lte=end,
        end_date__gte=start,
    ).filter(start_time__isnull=True)

    # The unit belongs to the company, alongside the figure. Counting in one
    # unit against an entitlement expressed in the other is how this went wrong.
    unit = company.leave_days_are_working_days
    taken = sum(
        _days_within(a, start, end, working_days=unit)
        for a in inside.filter(status=AbsenceStatus.APPROVED)
    )
    pending = sum(
        _days_within(a, start, end, working_days=unit)
        for a in inside.filter(status=AbsenceStatus.PENDING)
    )

    # Los días que una baja se comió no se han disfrutado (art. 38.3), así que
    # dejan de contar como gastados en cuanto un responsable lo confirma.
    from apps.absences.recovery import recovered_days

    taken = max(0, taken - recovered_days(employee=employee, company=company, start=start, end=end))

    return LeaveBalance(
        start,
        end,
        entitled,
        taken,
        pending,
        working_days=unit,
        full_year=full_year,
        accrued_from=accrued_from,
        accrued_to=accrued_to,
    )


def _accrued(
    employee, full_year: int, start: date, end: date
) -> tuple[int, date | None, date | None]:
    """Lo que le corresponde de vacaciones si no ha trabajado el periodo entero.

    Las vacaciones se **devengan**: se ganan según se trabaja. Quien entra el 9
    de marzo no ha ganado el año entero en marzo, y quien tiene contrato de tres
    meses no gana doce. El art. 38.1 ET fija el suelo de treinta días naturales
    *al año*; para un periodo incompleto ese suelo va en proporción, y es
    doctrina pacífica --- no una interpretación de este producto.

    Esto lo hacía mal hasta el 13/08/2026: daba el año completo a todo el mundo
    desde el primer día. En una empresa con temporeros eso no es un redondeo,
    es regalar semanas que luego se liquidan en la nómina.

    La proporción va por días naturales de contrato dentro del periodo, que es
    como se calcula en la práctica y como lo hace cualquier finiquito.

    **Se redondea hacia arriba.** El resultado casi nunca es entero, y redondear
    hacia abajo quita días sobre un mínimo legal. Al alza el peor caso es dar
    medio día de más; a la baja el peor caso es incumplir. El convenio puede
    mejorarlo, y entonces se pone el número a mano en la ficha.
    """
    import math

    begins = employee.contract_start
    finishes = employee.contract_end

    # Sin fechas de contrato no hay nada que prorratear: es alguien de siempre.
    if not begins and not finishes:
        return full_year, None, None

    first = max(begins, start) if begins else start
    last = min(finishes, end) if finishes else end

    if first > last:
        # El contrato no toca este periodo: ni un día devengado.
        return 0, first, last

    covered = (last - first).days + 1
    whole = (end - start).days + 1
    if covered >= whole:
        return full_year, None, None

    return math.ceil(full_year * covered / whole), first, last


def _days_within(absence: Absence, start: date, end: date, *, working_days: bool) -> int:
    """Only the part of the absence that falls inside the period.

    Leave straddling the period boundary counts on each side for the days it
    actually occupies there.

    **In the same unit the entitlement is expressed in**, which is the part that
    was wrong: the figure meant working days and this counted calendar days, so
    a fortnight off cost fourteen of twenty-two and everybody ran out of holiday
    around October.

    A working day is a day that person was **due to work**, read from the
    roster. Not Monday to Friday: a rotating team works Saturdays, a part-timer
    may only work Tuesdays and Thursdays, and deducting the days they were never
    going to work is the same mistake in a smaller size. Monday to Friday is the
    fallback for somebody with no roster at all, which is what a flexible
    arrangement looks like here.

    Public holidays come off too, for the same reason the weekend does: a day
    the person was never going to work is not a day of holiday spent. Which ones
    are holidays depends on their **workplace** --- two of the fourteen are the
    town hall's --- so it is asked of the person, not of the company.

    A holiday that lands on a rostered day still comes off. Being rostered on a
    public holiday is lawful and the roster reports it separately; what it is
    not is a reason to charge somebody a day of their own leave.
    """
    first = max(absence.start_date, start)
    last = min(absence.end_date, end)
    if last < first:
        return 0
    if not working_days:
        return (last - first).days + 1

    from django.db.models import Max

    from apps.shifts.models import Shift
    from apps.tenants.holidays import holidays_for

    rostered = set(
        Shift.objects.filter(
            employee_id=absence.employee_id, day__gte=first, day__lte=last
        ).values_list("day", flat=True)
    )
    # The roster only speaks for the days it reaches. Holiday is booked months
    # ahead and rosters are published weeks ahead, so the ordinary case is a
    # request the roster half-covers --- and "any shift in the range means
    # count only shift days" was undercounting the uncovered half: a fortnight
    # off with one week published cost five days instead of ten. Beyond the
    # last day this person has ever been rostered, the ordinary week answers.
    horizon = Shift.objects.filter(employee_id=absence.employee_id).aggregate(Max("day"))[
        "day__max"
    ]
    off = holidays_for(absence.employee, first, last)

    def counts(day) -> bool:
        if day in off:
            return False
        if horizon is not None and day <= horizon:
            return day in rostered
        return day.weekday() < 5

    span = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    return sum(1 for day in span if counts(day))


# ------------------------------------------------------------------- requesting


def request_absence(
    *,
    employee,
    company,
    absence_type: str = "",
    leave_type=None,
    start_date: date,
    end_date: date,
    start_time=None,
    end_time=None,
    reduction_share=None,
    reason: str = "",
    justification=None,
    requested_by=None,
) -> Absence:
    """Records the request. Nothing is blocked until somebody approves it.

    The family comes from the leave type when there is one, so the two cannot
    disagree. `absence_type` on its own is still accepted: it is what every
    caller passed before there was a catalogue, and breaking them to add a
    field would be charging for the improvement.
    """
    if leave_type is not None:
        absence_type = leave_type.family
    if not absence_type:
        raise BusinessRuleError(code="no_type", message=_("Say what kind of leave it is."))

    if end_date < start_date:
        raise BusinessRuleError(
            code="ends_before_it_starts",
            message=_("The end date cannot precede the start date."),
        )

    if absence_type == AbsenceType.SICK_LEAVE and justification:
        raise BusinessRuleError(
            code="no_medical_certificate",
            message=_(
                "The medical certificate is not stored. Recording the absence, its dates "
                "and its status is enough, and since RD 1060/2022 the worker does not "
                "hand the certificate to the employer."
            ),
        )

    clash = _overlapping(
        employee,
        start_date,
        end_date,
        start_time=start_time,
        end_time=end_time,
        reduction_share=reduction_share,
    ).first()
    if clash is not None and not _may_overlap_holiday(leave_type, clash):
        raise BusinessRuleError(
            code="overlapping_absence",
            message=_("There is already leave recorded between %(from)s and %(to)s.")
            % {"from": clash.start_date, "to": clash.end_date},
        )

    # Holiday is counted in days against a balance in days. Half a day of it
    # would either round --- giving away or eating a day nobody decided --- or
    # turn the balance into a decimal that the law does not use. The permits are
    # where part-days belong, and that is where they are allowed.
    # Reducing a day only means something while the contract is suspended.
    # Anywhere else it would look like a setting and do nothing, which is the
    # worst kind of field.
    # A suspension has to say WHICH of the fifteen it is. A raw one carries no
    # article, no name for the report, and --- the audit probe that forced this
    # --- no `initiated_by`, so anybody could file themselves a nameless
    # "suspension" with a reduction attached and walk straight around the rule
    # that an ERTE is the company's act to record.
    if absence_type == AbsenceType.SUSPENSION and leave_type is None:
        raise BusinessRuleError(
            code="suspension_needs_its_kind",
            message=_(
                "Say which suspension it is: they carry different articles and "
                "different consequences, and the record has to name one."
            ),
        )

    if reduction_share is not None and (start_time or end_time):
        raise BusinessRuleError(
            code="reduction_takes_no_hours",
            message=_(
                "A reduction covers whole days at a smaller share. For hours away on "
                "one day, leave the reduction empty."
            ),
        )

    if reduction_share is not None and absence_type != AbsenceType.SUSPENSION:
        raise BusinessRuleError(
            code="reduction_needs_a_suspension",
            message=_(
                "Only a suspension can reduce the working day. For fewer hours by "
                "agreement, change the contracted figure on the person."
            ),
        )

    # And only the suspensions the company records. A voluntary excedencia "at
    # 40 %" does not exist in law, and if one slipped through and got approved
    # on a busy afternoon, the roster would quietly start measuring that person
    # against a reduced contract nobody lawfully reduced.
    if (
        reduction_share is not None
        and leave_type is not None
        and leave_type.initiated_by != "COMPANY"
    ):
        raise BusinessRuleError(
            code="reduction_is_company_recorded",
            message=_(
                "Only a suspension the company records --- an ERTE, the RED "
                "mechanism --- can reduce the working day."
            ),
        )

    if (start_time or end_time) and absence_type == AbsenceType.VACATION:
        raise BusinessRuleError(
            code="holiday_is_whole_days",
            message=_(
                "Holiday is taken in whole days. For part of a day, use the leave type "
                "that fits: a medical appointment, family emergency, an exam."
            ),
        )

    absence = Absence(
        tenant=company,
        employee=employee,
        absence_type=absence_type,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        reduction_share=reduction_share,
        reason=reason.strip(),
        # Quién la mete, que no siempre es de quién es. Por omisión, la propia
        # persona: es lo que hacía todo el que llamaba a esto antes de que el
        # campo existiera, y es lo que pasa en la mayoría de las veces.
        requested_by=requested_by or employee,
    )
    if justification:
        absence.justification = justification
    absence.full_clean()
    absence.save()
    return absence


def _overlapping(
    employee,
    start_date: date,
    end_date: date,
    exclude_pk=None,
    start_time=None,
    end_time=None,
    reduction_share=None,
):
    """Anything already there for those dates, approved or still waiting.

    Pending requests count: letting two overlapping requests sit in the queue
    means whoever approves them second creates a contradiction nobody catches.

    **Two part-days on the same date do not clash unless the hours do.** Two
    hours at the doctor in the morning and one looking for work in the afternoon
    are two absences on one Tuesday and no contradiction at all --- and art.
    53.2's six hours a week is a permit somebody is *expected* to split.

    **A suspension that reduces the day runs in its own lane.** Somebody on an
    ERTE at 40 % works the other 60 % for months: they still fall ill, still
    sit exams, still take their booked holiday. Treating the reduction as "the
    day is claimed" made every other absence impossible for its whole duration
    --- the product refused a medical appointment because of an ERTE. So a
    reduction only clashes with another reduction, which *is* a contradiction:
    nobody's day can be reduced twice at once.
    """
    qs = Absence.objects.filter(
        Q(status=AbsenceStatus.APPROVED) | Q(status=AbsenceStatus.PENDING),
        employee=employee,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    if reduction_share is not None and reduction_share < 100:
        return qs.filter(REDUCES_THE_DAY)

    # Existing reductions never claim the day for anybody else.
    qs = qs.exclude(REDUCES_THE_DAY)

    if start_time is None or end_time is None:
        # A whole-day request clashes with anything left on those dates,
        # part-day included: the day is claimed entirely.
        return qs

    # A part-day one clashes with whole-day absences, and with part-days whose
    # hours actually cross. Half-open on purpose: leaving at eleven and starting
    # again at eleven is one thing after another, not two at once.
    return qs.filter(
        Q(start_time__isnull=True) | Q(start_time__lt=end_time, end_time__gt=start_time)
    )


# -------------------------------------------------------------------- resolving


def leave_over_the_limit(absence) -> dict | None:
    """Whether approving this would go past what its leave type grants.

    Reported, never refused. Every allowance in the catalogue is the statutory
    floor and the collective agreement improves any of them; a company that has
    not updated its copy would find the product refusing days its people are
    entitled to, which is worse than the warning it replaced.

    Read at the moment of deciding rather than stored on the absence: the
    allowance can change between asking and answering, and the figure that
    matters is the one in force when somebody says yes.
    """
    from apps.absences.usage import event_request_amount, leave_usage

    kind = absence.leave_type
    if kind is None or kind.amount is None:
        return None

    usage = leave_usage(absence.employee, kind, absence.tenant, absence.start_date)
    if usage.remaining is not None:
        return None if usage.remaining >= 0 else usage.as_dict()

    # Per-event permits accumulate nothing, so "what is left" is undefined ---
    # which used to mean the approver saw no warning at all while the requester
    # did, and the person deciding was the one flying blind. The comparison
    # that exists is this request against the grant, with the travelling extra
    # included: four days of bereavement with a journey is lawful, and warning
    # about it would teach people to ignore the warning.
    asked = event_request_amount(absence, kind)
    if asked is None:
        return None
    ceiling = float(kind.amount) + float(kind.extra_when_travelling or 0)
    if asked <= ceiling:
        return None
    return {
        "leave_type": str(kind.pk),
        "name": kind.name,
        "unit": kind.unit,
        "period": kind.period,
        "period_start": None,
        "period_end": None,
        "used": round(asked, 2),
        "requests": 1,
        "allowance": float(kind.amount),
        "travel_extra": float(kind.extra_when_travelling or 0),
        "remaining": round(float(kind.amount) - asked, 2),
        "over": True,
        "estimated": False,
    }


def _may_overlap_holiday(leave_type, other: Absence) -> bool:
    """Si esta baja puede pisar esas vacaciones en vez de chocar con ellas.

    Caer de baja durante las vacaciones es **el caso que contempla el art.
    38.3**, no un error de quien lo registra. Hasta el 13/08/2026 el producto lo
    trataba como un solapamiento y se negaba a registrar la baja: la persona se
    quedaba sin poder acreditar que estuvo enferma, y de paso sin los días.

    Solo con vacaciones, y solo para los permisos a los que el marco legal del
    país reconoce ese derecho. Dos bajas que se pisan siguen siendo un choque, y
    unas vacaciones sobre otras también.
    """
    if other.absence_type != AbsenceType.VACATION:
        return False
    return bool(getattr(leave_type, "vacation_recovery", ""))


def approve_absence(absence: Absence, *, resolved_by) -> Absence:
    absence = _must_be_open(absence)

    # Less grave than the working-time record --- leave is the company's to grant
    # --- but the same principle, and an auditor asks the same question.
    refuse_self_decision(
        subject=absence.employee,
        decider=resolved_by,
        company=absence.tenant,
        what=_("leave"),
    )

    # Re-checked at approval, not only at request: something else may have been
    # approved for those dates in between.
    clash = _overlapping(absence.employee, absence.start_date, absence.end_date, absence.pk)
    aprobadas = list(clash.filter(status=AbsenceStatus.APPROVED))
    if aprobadas and not all(_may_overlap_holiday(absence.leave_type, otra) for otra in aprobadas):
        raise BusinessRuleError(
            code="overlapping_absence",
            message=_("Leave has since been approved for those dates."),
        )

    absence.status = AbsenceStatus.APPROVED
    absence.approved_by = resolved_by
    absence.resolved_at = timezone.now()
    absence.save(update_fields=["status", "approved_by", "resolved_at", "updated_at"])

    # Art. 38.3: si esta baja pisa unas vacaciones ya aprobadas, esos días no se
    # han disfrutado. Se anotan para que un responsable lo confirme; no vuelven
    # al saldo solos.
    from apps.absences.recovery import detect_recoveries

    detect_recoveries(absence=absence, company=absence.tenant)
    return absence


def reject_absence(absence: Absence, *, resolved_by) -> Absence:
    """Turned down requests are kept: a refused claim is history too."""
    absence = _must_be_open(absence)

    # Refusing your own is harmless in itself, but allowing it would leave the
    # rule half applied and invite somebody to wonder which half.
    refuse_self_decision(
        subject=absence.employee,
        decider=resolved_by,
        company=absence.tenant,
        what=_("leave"),
    )

    absence.status = AbsenceStatus.REJECTED
    absence.approved_by = resolved_by
    absence.resolved_at = timezone.now()
    absence.save(update_fields=["status", "approved_by", "resolved_at", "updated_at"])
    return absence


def cancel_absence(absence: Absence, *, cancelled_by) -> None:
    """Withdraws a request that has not been resolved yet.

    Only the person concerned, and only while it is pending: once approved it
    has blocked days and possibly other people's plans, so undoing it is a
    decision for whoever approved it.
    """
    absence = _must_be_open(absence)
    if absence.employee_id != cancelled_by.id and not cancelled_by.can_manage:
        raise BusinessRuleError(
            code="not_your_request",
            message=_("That request belongs to somebody else."),
        )
    absence.delete()


def _must_be_open(absence: Absence) -> Absence:
    """Bloquea la solicitud y exige que siga sin resolver. Devuelve la fila fresca.

    Antes solo miraba `absence.status` de la instancia que traía quien llama, y
    esa la cargó la petición **antes** de que ninguna otra escribiera. Con dos
    responsables pulsando a la vez, las dos veían `PENDING`, las dos pasaban y
    las dos escribían: la ausencia acababa en `REJECTED` con `approved_by`
    puesto, y el rastro con una aprobación y un rechazo de la misma solicitud.

    El porqué del `select_for_update`, en `apps.common.transitions`.
    """
    return claim(Absence, absence.pk, desde=AbsenceStatus.PENDING)


#: Los dos meses del art. 38.3, en días. No es un ajuste de empresa: el plazo lo
#: fija la ley y el convenio solo puede mejorarlo, así que una empresa que lo
#: bajara estaría configurando un incumplimiento.
HOLIDAY_NOTICE_DAYS = 60


def short_holiday_notice(absence) -> dict | None:
    """Vacaciones puestas por la empresa con menos de dos meses de aviso.

    «El trabajador conocerá las fechas que le correspondan dos meses antes, al
    menos, del comienzo del disfrute» (art. 38.3 ET). El plazo existe para que
    a nadie le fijen las vacaciones encima: es lo que permite reservar un vuelo,
    cuadrar con la pareja o apuntar a un crío a un campamento.

    Se avisa, no se impide, como con el resto de los mínimos: acortarlo de mutuo
    acuerdo es corriente y legítimo, y negarse a registrarlo dejaría fuera del
    sistema unas vacaciones que la gente va a disfrutar igual --- que es peor
    que registrarlas con una nota.

    **Solo cuando las pone otro.** Si las pide la persona, conoce las fechas por
    definición: no hay plazo que incumplir y el aviso sería ruido. Esa
    distinción es la razón de que `requested_by` exista; sin él, este aviso
    saltaría en la mitad de las solicitudes normales y en dos semanas nadie lo
    miraría, que es como se estropea un aviso.
    """
    if absence.absence_type != AbsenceType.VACATION:
        return None
    if absence.requested_by_id is None or absence.requested_by_id == absence.employee_id:
        return None

    # Desde que se metió, no desde hoy: el plazo se mide contra el momento en
    # que la persona pudo conocer las fechas. Mirarlo contra hoy haría que unas
    # vacaciones avisadas con tiempo se volvieran «con poco aviso» solas, según
    # se acercara la fecha.
    conocidas = local_date_of(absence.created_at or timezone.now(), absence.tenant)
    dias = (absence.start_date - conocidas).days
    if dias >= HOLIDAY_NOTICE_DAYS:
        return None

    return {
        "days": dias,
        "required": HOLIDAY_NOTICE_DAYS,
        "citation": "Art. 38.3 ET",
    }
