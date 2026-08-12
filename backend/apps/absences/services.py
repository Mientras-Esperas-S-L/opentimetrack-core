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

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
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
    #: Which unit all three figures are in. Served rather than assumed: "quedan
    #: 9" means something different in working days than in calendar days, and
    #: the screen showing it has no other way to know which.
    working_days: bool = True

    @property
    def remaining(self) -> int:
        """Pending requests count against it. Showing them as available is how
        two people end up booking the same last day."""
        return self.entitled - self.taken - self.pending

    def as_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "entitled": self.entitled,
            "taken": self.taken,
            "pending": self.pending,
            "remaining": self.remaining,
            "working_days": self.working_days,
        }


def vacation_balance(employee, company, day: date | None = None) -> LeaveBalance:
    start, end = leave_period_for(company, day)

    entitled = employee.annual_leave_days
    if entitled is None:
        entitled = company.annual_leave_days

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

    return LeaveBalance(start, end, entitled, taken, pending, working_days=unit)


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

    from apps.shifts.models import Shift
    from apps.tenants.holidays import holidays_for

    rostered = set(
        Shift.objects.filter(
            employee_id=absence.employee_id, day__gte=first, day__lte=last
        ).values_list("day", flat=True)
    )
    off = holidays_for(absence.employee, first, last)
    span = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    if rostered:
        return sum(1 for day in span if day in rostered and day not in off)
    return sum(1 for day in span if day.weekday() < 5 and day not in off)


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
    reason: str = "",
    justification=None,
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
        employee, start_date, end_date, start_time=start_time, end_time=end_time
    ).first()
    if clash is not None:
        raise BusinessRuleError(
            code="overlapping_absence",
            message=_("There is already leave recorded between %(from)s and %(to)s.")
            % {"from": clash.start_date, "to": clash.end_date},
        )

    # Holiday is counted in days against a balance in days. Half a day of it
    # would either round --- giving away or eating a day nobody decided --- or
    # turn the balance into a decimal that the law does not use. The permits are
    # where part-days belong, and that is where they are allowed.
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
        reason=reason.strip(),
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
):
    """Anything already there for those dates, approved or still waiting.

    Pending requests count: letting two overlapping requests sit in the queue
    means whoever approves them second creates a contradiction nobody catches.

    **Two part-days on the same date do not clash unless the hours do.** Two
    hours at the doctor in the morning and one looking for work in the afternoon
    are two absences on one Tuesday and no contradiction at all --- and art.
    53.2's six hours a week is a permit somebody is *expected* to split. Refusing
    them was what the date-only check did, and it made every hourly permit
    unusable after the first request of the day.
    """
    qs = Absence.objects.filter(
        Q(status=AbsenceStatus.APPROVED) | Q(status=AbsenceStatus.PENDING),
        employee=employee,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    if start_time is None or end_time is None:
        # A whole-day request clashes with anything on those dates, part-day
        # included: the day is claimed entirely.
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
    from apps.absences.usage import leave_usage

    kind = absence.leave_type
    if kind is None or kind.amount is None:
        return None

    usage = leave_usage(absence.employee, kind, absence.tenant, absence.start_date)
    if usage.remaining is None or usage.remaining >= 0:
        return None
    return usage.as_dict()


def approve_absence(absence: Absence, *, resolved_by) -> Absence:
    _must_be_open(absence)

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
    if clash.filter(status=AbsenceStatus.APPROVED).exists():
        raise BusinessRuleError(
            code="overlapping_absence",
            message=_("Leave has since been approved for those dates."),
        )

    absence.status = AbsenceStatus.APPROVED
    absence.approved_by = resolved_by
    absence.resolved_at = timezone.now()
    absence.save(update_fields=["status", "approved_by", "resolved_at", "updated_at"])
    return absence


def reject_absence(absence: Absence, *, resolved_by) -> Absence:
    """Turned down requests are kept: a refused claim is history too."""
    _must_be_open(absence)

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
    _must_be_open(absence)
    if absence.employee_id != cancelled_by.id and not cancelled_by.can_manage:
        raise BusinessRuleError(
            code="not_your_request",
            message=_("That request belongs to somebody else."),
        )
    absence.delete()


def _must_be_open(absence: Absence) -> None:
    if absence.status != AbsenceStatus.PENDING:
        raise BusinessRuleError(
            code="already_resolved",
            message=_("This request has already been resolved."),
        )
