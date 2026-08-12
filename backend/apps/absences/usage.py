"""How much of each leave somebody has already used.

The catalogue says what each permit grants. This says what is left of it, which
is the question anybody actually asks --- a gestoría rings up and wants to know
how many days of family emergency somebody has taken this year, not what art.
37.9 says.

Three things decide the arithmetic, and all three come off the leave type:

**What resets it.** Fifteen days *per wedding* and four days *per year* are both
a number in a field that does not say which. `EVENT` never accumulates: each
request stands on its own and there is nothing to add up, so what gets reported
is how many times it has been asked for. The rest accumulate inside a period.

**Which period.** Calendar year, month, ISO week, or the day. Deliberately
**not** the company's holiday reference period: that one belongs to art. 38 and
using it here would quietly apply an April-to-March year to a permit whose
article says "al año" and nothing else.

**In what unit.** Calendar days count every day; working days count the ones the
person was due to work, weekends and public holidays excluded, exactly as
holiday does; hours add up the part-days.

An hours-based permit taken as a whole day is the one case with no exact answer:
how long that person's day is depends on the roster. The roster is used when
there is one, and the company's ordinary day when there is not --- an
approximation, said out loud in `estimated` rather than hidden in a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from apps.absences.models import Absence, AbsenceStatus, LeavePeriod, LeaveUnit
from apps.common.clock import local_today


@dataclass(frozen=True)
class LeaveUsage:
    """What one person has used of one kind of leave."""

    leave_type_id: str
    name: str
    unit: str
    period: str

    #: None on an EVENT permit, where nothing accumulates.
    period_start: date | None
    period_end: date | None

    used: float
    requests: int
    allowance: float | None
    #: True when an hours-based permit was taken as a whole day and the length
    #: of that day had to be assumed.
    estimated: bool = False

    @property
    def remaining(self) -> float | None:
        if self.allowance is None or self.period == LeavePeriod.EVENT:
            return None
        return round(self.allowance - self.used, 2)

    @property
    def over(self) -> bool:
        remaining = self.remaining
        return remaining is not None and remaining < 0

    def as_dict(self) -> dict:
        return {
            "leave_type": str(self.leave_type_id),
            "name": self.name,
            "unit": self.unit,
            "period": self.period,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "used": self.used,
            "requests": self.requests,
            "allowance": float(self.allowance) if self.allowance is not None else None,
            "remaining": self.remaining,
            "over": self.over,
            "estimated": self.estimated,
        }


def period_for(leave_type, day: date) -> tuple[date | None, date | None]:
    """The window the allowance resets over, containing `day`.

    The calendar year and not the company's holiday period, on purpose: art. 38
    lets an agreement move the holiday year and says nothing about the rest, so
    borrowing that setting here would apply somebody's April-to-March holiday
    year to their family emergencies.
    """
    if leave_type.period == LeavePeriod.YEAR:
        return date(day.year, 1, 1), date(day.year, 12, 31)
    if leave_type.period == LeavePeriod.MONTH:
        first = day.replace(day=1)
        following = (first + timedelta(days=32)).replace(day=1)
        return first, following - timedelta(days=1)
    if leave_type.period == LeavePeriod.WEEK:
        monday = day - timedelta(days=day.weekday())
        return monday, monday + timedelta(days=6)
    if leave_type.period == LeavePeriod.DAY:
        return day, day
    return None, None  # EVENT


def leave_usage(employee, leave_type, company, on: date | None = None) -> LeaveUsage:
    """What this person has used of this leave, in its own unit and period."""
    from apps.absences.services import _days_within

    on = on or local_today(employee)
    first, last = period_for(leave_type, on)

    rows = Absence.objects.filter(
        employee=employee,
        leave_type=leave_type,
        status__in=[AbsenceStatus.APPROVED, AbsenceStatus.PENDING],
    )
    if first is not None:
        rows = rows.filter(start_date__lte=last, end_date__gte=first)

    used, estimated = 0.0, False
    for absence in rows:
        if leave_type.unit == LeaveUnit.HOURS:
            if absence.is_partial:
                used += absence.hours
            else:
                hours, guessed = _whole_day_hours(absence, company)
                used += hours
                estimated = estimated or guessed
        elif absence.is_partial:
            # Part of a day against an allowance in days. Counting it as a whole
            # one would charge somebody a day for two hours; counting it as zero
            # would make the allowance unlimited by the back door. A fraction is
            # the only answer that is neither.
            hours, guessed = _whole_day_hours(absence, company)
            used += round(absence.hours / hours, 2) if hours else 0
            estimated = estimated or guessed
        else:
            used += _days_within(
                absence,
                first or absence.start_date,
                last or absence.end_date,
                working_days=leave_type.unit == LeaveUnit.DAYS_WORKING,
            )

    return LeaveUsage(
        leave_type_id=leave_type.pk,
        name=leave_type.name,
        unit=leave_type.unit,
        period=leave_type.period,
        period_start=first,
        period_end=last,
        used=round(used, 2),
        requests=rows.count(),
        allowance=float(leave_type.amount) if leave_type.amount is not None else None,
        estimated=estimated,
    )


def _whole_day_hours(absence, company) -> tuple[float, bool]:
    """How long that person's day was, and whether it had to be assumed.

    The roster knows exactly when there is one. When there is not --- which is
    what a flexible arrangement looks like here --- the company's ordinary week
    over five days is the best available guess, and the caller is told it is one.
    """
    from apps.shifts.models import Shift
    from apps.tenants.rules import WorkingTimeRules

    shift = Shift.objects.filter(employee=absence.employee, day=absence.start_date).first()
    if shift is not None:
        return shift.minutes / 60, False
    return float(WorkingTimeRules.for_company(company).weekly_hours) / 5, True


def event_request_amount(absence, leave_type) -> float | None:
    """How much one request asks for, in the permit's own unit.

    For the per-event permits, where nothing accumulates and the only
    comparison that means anything is this request against the grant. The unit
    conversion is the whole point: fifteen *calendar days* for a wedding, eight
    *weeks* of parental leave --- comparing either against a plain count of
    days is how a form ends up warning anybody who asks for more than eight
    days of an eight-week permit.

    None means there is nothing meaningful to compare: an hours permit taken
    as whole days, or a part-day slice of a days permit, neither of which can
    overshoot a whole-unit grant in a way worth warning about.
    """
    if leave_type.unit == LeaveUnit.HOURS:
        return absence.hours if absence.is_partial else None
    if absence.is_partial:
        return None

    days = (absence.end_date - absence.start_date).days + 1
    if leave_type.unit == LeaveUnit.WEEKS:
        return round(days / 7, 2)
    if leave_type.unit == LeaveUnit.DAYS_WORKING:
        from apps.absences.services import _days_within

        return float(_days_within(absence, absence.start_date, absence.end_date, working_days=True))
    return float(days)


def usage_summary(employee, company, on: date | None = None) -> list[dict]:
    """Every leave with a limit, and what is left of it.

    Only the ones with a limit: a permit granting "el tiempo indispensable" has
    nothing to be left of, and a row saying so on every screen would be noise
    around the four that matter.
    """
    from apps.absences.models import LeaveType

    rows = LeaveType.objects.filter(is_active=True, amount__isnull=False).exclude(
        period=LeavePeriod.EVENT
    )
    return [leave_usage(employee, kind, company, on).as_dict() for kind in rows]
