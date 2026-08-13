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


def punches_of_the_day(employee, company, day: date | None = None):
    # The person's zone, not the company's: `employee.tzinfo` is their
    # workplace's and falls back to the company's when they have none.
    reference = timezone.now()
    if day is not None:
        reference = datetime.combine(day, datetime.min.time(), tzinfo=employee.tzinfo)

    start, end = local_day_bounds(employee, reference)
    return Punch.objects.filter(
        employee=employee,
        is_active=True,
        timestamp__gte=start,
        timestamp__lt=end,
    ).order_by("timestamp")


def infer_type(employee, company, interval: str = PunchInterval.WORK) -> str:
    """Opens or closes, worked out from the last event **of that interval**.

    The person is not asked which one it is: one tap, no choices, no chance of
    picking the wrong one.

    Per interval, because they nest. Starting a break while the working day is
    open must not be read as closing the day, and it would be if the last event
    of any kind decided.
    """
    last = punches_of_the_day(employee, company).filter(interval=interval).last()
    if last is None or last.punch_type == PunchType.OUT:
        return PunchType.IN
    return PunchType.OUT


def build_day_status(employee, company, day: date | None = None) -> DayStatus:
    """The day, as the record holds it.

    Whether a break comes off the hours is **the company's rule, not ours**.
    Art. 34.4 ET makes the fifteen-minute break working time only when the
    agreement or the contract says so --- and a good many agreements do. Always
    deducting it would take roughly fifty-five hours a year off every worker in
    those companies, quietly and in the direction that favours the employer.
    """
    from apps.tenants.rules import WorkingTimeRules

    events = list(punches_of_the_day(employee, company, day))
    rules = WorkingTimeRules.for_company(company)

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
        status = build_day_status(employee, company)
        if status.state not in {"WORKING", "ON_BREAK"}:
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
