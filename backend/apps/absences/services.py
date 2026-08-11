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
from datetime import date

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.exceptions import BusinessRuleError

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
    )

    taken = sum(_days_within(a, start, end) for a in inside.filter(status=AbsenceStatus.APPROVED))
    pending = sum(_days_within(a, start, end) for a in inside.filter(status=AbsenceStatus.PENDING))

    return LeaveBalance(start, end, entitled, taken, pending)


def _days_within(absence: Absence, start: date, end: date) -> int:
    """Only the part of the absence that falls inside the period.

    Leave straddling the period boundary counts on each side for the days it
    actually occupies there.
    """
    first = max(absence.start_date, start)
    last = min(absence.end_date, end)
    return (last - first).days + 1 if last >= first else 0


# ------------------------------------------------------------------- requesting


def request_absence(
    *,
    employee,
    company,
    absence_type: str,
    start_date: date,
    end_date: date,
    reason: str = "",
    justification=None,
) -> Absence:
    """Records the request. Nothing is blocked until somebody approves it."""
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

    clash = _overlapping(employee, start_date, end_date).first()
    if clash is not None:
        raise BusinessRuleError(
            code="overlapping_absence",
            message=_("There is already leave recorded between %(from)s and %(to)s.")
            % {"from": clash.start_date, "to": clash.end_date},
        )

    absence = Absence(
        tenant=company,
        employee=employee,
        absence_type=absence_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason.strip(),
    )
    if justification:
        absence.justification = justification
    absence.full_clean()
    absence.save()
    return absence


def _overlapping(employee, start_date: date, end_date: date, exclude_pk=None):
    """Anything already there for those dates, approved or still waiting.

    Pending requests count: letting two overlapping requests sit in the queue
    means whoever approves them second creates a contradiction nobody catches.
    """
    qs = Absence.objects.filter(
        Q(status=AbsenceStatus.APPROVED) | Q(status=AbsenceStatus.PENDING),
        employee=employee,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    return qs.exclude(pk=exclude_pk) if exclude_pk else qs


# -------------------------------------------------------------------- resolving


def approve_absence(absence: Absence, *, resolved_by) -> Absence:
    _must_be_open(absence)

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
