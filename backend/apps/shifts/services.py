"""Building a roster, and telling the truth about it.

Everything in `review_roster` reports; nothing refuses. That is a decision, not
an omission, and it is the same one taken in `apps.tenants.rules`: RD 1561/1995
modifies the rest periods for transport, on-call work and shift handovers, all
lawfully. A product that refused to save those rosters would be unusable in
exactly the sectors where working time matters most, and refusing would mean
deciding a compliance question that belongs to the company and its advisers.

What it does instead is say **what it found and on what basis**, so nobody can
claim they were not told.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.absences.models import Absence, AbsenceStatus
from apps.common.exceptions import BusinessRuleError
from apps.shifts.models import Shift, ShiftPattern, working_days_between
from apps.tenants.rules import WorkingTimeRules


@dataclass(frozen=True)
class Finding:
    """Something worth saying about a roster.

    `basis` is not decoration: a warning nobody can trace to an article is a
    warning nobody can argue with, and the person reading it is entitled to know
    which rule the company has configured and why.
    """

    day: date
    employee_id: str
    code: str
    message: str
    basis: str

    def as_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "employee": str(self.employee_id),
            "code": self.code,
            "message": str(self.message),
            "basis": self.basis,
        }


# ------------------------------------------------------------------- assigning


@transaction.atomic
def assign_pattern(*, employee, company, pattern: ShiftPattern, days) -> list[Shift]:
    """Puts a pattern on a set of days, replacing whatever was there.

    Replacing rather than refusing: a roster gets redrawn, and making somebody
    clear the old one first turns one action into two with a broken state in
    between.

    The spans are **copied** from the pattern. Editing "morning" next month must
    not rewrite a day that was already published --- people arranged their lives
    around it.
    """
    wanted = list(days)
    if not wanted:
        raise BusinessRuleError(
            code="no_days",
            message=_("Choose at least one day."),
        )

    Shift.objects.filter(employee=employee, day__in=wanted).delete()

    return Shift.objects.bulk_create(
        [
            Shift(
                tenant=company,
                employee=employee,
                day=day,
                pattern=pattern,
                segments=pattern.segments,
            )
            for day in wanted
        ]
    )


@transaction.atomic
def clear_shifts(*, employee, days) -> int:
    deleted, _detail = Shift.objects.filter(employee=employee, day__in=list(days)).delete()
    return deleted


def weekdays_in(first: date, last: date, weekdays: list[int]) -> list[date]:
    """Days in the range falling on the given weekdays (Monday = 0).

    What makes "every Monday to Friday in September" one action instead of
    twenty-two.
    """
    return [d for d in working_days_between(first, last) if d.weekday() in weekdays]


# -------------------------------------------------------------------- reviewing


def review_roster(*, company, first: date, last: date, employee=None) -> list[Finding]:
    """Reads the roster and says what departs from the company's own rules.

    Deliberately reads one day either side of the window: the rest between
    working days is a property of the boundary between two shifts, so checking a
    month in isolation would miss whether the first day of it clashes with the
    last day of the month before.
    """
    rules = WorkingTimeRules.for_company(company)

    shifts = Shift.objects.filter(
        day__gte=first - timedelta(days=1), day__lte=last + timedelta(days=1)
    ).select_related("employee")
    if employee is not None:
        shifts = shifts.filter(employee=employee)

    by_person: dict = {}
    for shift in shifts.order_by("employee_id", "day"):
        by_person.setdefault(shift.employee_id, []).append(shift)

    findings: list[Finding] = []
    for employee_id, roster in by_person.items():
        findings.extend(_check_daily_rest(roster, rules, first, last))
        findings.extend(_check_weekly_hours(employee_id, roster, rules, first, last))
        findings.extend(_check_breaks(roster, rules, first, last))
    findings.extend(_check_leave_clashes(first, last, employee))

    return sorted(findings, key=lambda f: (f.day, f.code))


def _check_daily_rest(roster, rules, first, last) -> list[Finding]:
    found = []
    for previous, current in pairwise(roster):
        gap = (current.starts_at - previous.ends_at).total_seconds() / 3600
        if gap < rules.daily_rest_hours and first <= current.day <= last:
            found.append(
                Finding(
                    day=current.day,
                    employee_id=current.employee_id,
                    code="short_daily_rest",
                    message=_("Only %(hours)s h of rest since the previous shift.")
                    % {"hours": f"{gap:.1f}"},
                    basis="Art. 34.3 ET",
                )
            )
    return found


def _check_weekly_hours(employee_id, roster, rules, first, last) -> list[Finding]:
    """Hours per ISO week. Weeks only partly inside the window are skipped.

    Reporting a half-counted week as an excess would be worse than saying
    nothing: whoever reads it would go looking for hours that are not there and
    stop trusting the rest of the warnings.
    """
    weeks: dict = {}
    for shift in roster:
        year, week, _weekday = shift.day.isocalendar()
        weeks.setdefault((year, week), []).append(shift)

    limit = float(rules.weekly_hours)
    found = []
    for (_year, _week), shifts_of_week in weeks.items():
        monday = min(s.day for s in shifts_of_week) - timedelta(
            days=min(s.day for s in shifts_of_week).weekday()
        )
        sunday = monday + timedelta(days=6)
        if monday < first or sunday > last:
            continue

        hours = sum(s.minutes for s in shifts_of_week) / 60
        if hours > limit:
            found.append(
                Finding(
                    day=monday,
                    employee_id=employee_id,
                    code="weekly_hours_exceeded",
                    message=_("%(hours)s h rostered that week, over the %(limit)s h configured.")
                    % {"hours": f"{hours:.1f}", "limit": f"{limit:g}"},
                    basis="Art. 34.1 ET",
                )
            )
    return found


def _check_breaks(roster, rules, first, last) -> list[Finding]:
    """A continuous day past the threshold needs its break.

    Only continuous days: a split shift already has one. And the break is
    reported as owed, not added to the hours --- art. 34.4 ET makes it working
    time only when the agreement says so, which is the company's setting to
    make.
    """
    threshold = float(rules.break_after_hours) * 60
    found = []
    for shift in roster:
        if not (first <= shift.day <= last):
            continue
        if len(shift.segments) > 1:
            continue
        if shift.minutes > threshold:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="break_owed",
                    message=_("A continuous day of %(hours)s h needs a break of %(minutes)s min.")
                    % {"hours": f"{shift.minutes / 60:.1f}", "minutes": rules.break_minutes},
                    basis="Art. 34.4 ET",
                )
            )
    return found


def _check_leave_clashes(first, last, employee) -> list[Finding]:
    """Somebody rostered on a day they have approved leave for.

    The most ordinary planning mistake there is, and the one that reaches the
    worker fastest: they turn up, or they do not and it looks like an absence.
    """
    absences = Absence.objects.filter(
        status=AbsenceStatus.APPROVED, start_date__lte=last, end_date__gte=first
    )
    if employee is not None:
        absences = absences.filter(employee=employee)

    found = []
    for absence in absences.select_related("employee"):
        clashing = Shift.objects.filter(
            employee_id=absence.employee_id,
            day__gte=max(absence.start_date, first),
            day__lte=min(absence.end_date, last),
        )
        for shift in clashing:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="rostered_on_leave",
                    message=_("Rostered on a day of approved %(kind)s.")
                    % {"kind": absence.get_absence_type_display()},
                    basis="—",
                )
            )
    return found


# ------------------------------------------------------- roster against reality


def expected_vs_worked(*, employee, company, day: date) -> dict:
    """What was expected against what was recorded, for one day.

    Kept strictly one-directional. The shift never becomes a clock event, and no
    hour is inferred from a roster: a record that filled itself in from the plan
    would be precisely the fiction art. 34.9 ET exists to prevent, and it would
    look identical to a real one.
    """
    from apps.punches.services import build_day_status

    shift = Shift.objects.filter(employee=employee, day=day).first()
    status = build_day_status(employee, company, day)

    expected = shift.minutes if shift else 0
    worked = status.worked_seconds // 60

    return {
        "day": day.isoformat(),
        "expected_minutes": expected,
        "worked_minutes": worked,
        "difference_minutes": worked - expected,
        "has_shift": shift is not None,
        "state": status.state,
    }
