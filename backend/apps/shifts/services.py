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

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from itertools import pairwise

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps import legal
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
    #: Filled in one pass at the end, from the company's country. Empty at
    #: construction because the place a finding is built has no business
    #: knowing which country's article covers it.
    basis: str = ""
    #: Carried alongside the id so a warning can name who it is about without
    #: the caller holding the whole workforce to look it up in --- which is what
    #: the roster screen was doing, and it only ever held the first page of it.
    employee_name: str = ""

    def as_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "employee": str(self.employee_id),
            "employee_name": self.employee_name,
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
def paint_cells(*, company, cells) -> dict:
    """Sets a scattered handful of days at once, each to its own shift.

    `assign_pattern` paints one pattern over a rectangle of the calendar, which
    is how a roster gets built and not how it gets corrected. Dragging on the
    grid needs the other shape: *these* people on *these* days, each becoming
    whatever the stroke says --- and, for undo, each going back to whatever it
    was, which is a different pattern per cell and sometimes no pattern at all.

    A cell carries a pattern, or bare spans, or neither:

    **A pattern** copies its spans, exactly as assigning does. Editing "morning"
    next month must not rewrite a day already published.

    **Bare spans** are a day that never came from a pattern --- a one-off, a
    twelve-hour night somebody typed in. Undo has to be able to put those back
    as they were rather than approximating them with the nearest pattern.

    **Neither** rubs the day out.
    """
    wanted = list(cells)
    if not wanted:
        return {"painted": 0, "cleared": 0}

    # Resolved through the tenant manager, so a cell naming somebody else's
    # person or pattern finds nothing and is refused rather than written.
    people = {
        str(person.pk): person
        for person in _users().objects.filter(
            tenant=company, pk__in={c["employee"] for c in wanted}
        )
    }
    patterns = {
        str(pattern.pk): pattern
        for pattern in ShiftPattern.objects.filter(
            pk__in={c["pattern"] for c in wanted if c.get("pattern")}
        )
    }

    for cell in wanted:
        if str(cell["employee"]) not in people:
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("Somebody in that list is not in this company."),
            )
        if cell.get("pattern") and str(cell["pattern"]) not in patterns:
            raise BusinessRuleError(
                code="unknown_pattern", message=_("That shift pattern does not exist.")
            )

    # Every named day goes first, whatever it held. A stroke replaces; it does
    # not merge with what was underneath, and the unique constraint would refuse
    # the write anyway.
    #
    # One clause per person rather than one per cell --- for a dragged rectangle
    # that is the number of rows instead of rows times days --- and days crossed
    # with people, which would take out somebody else's Tuesday.
    days_of: dict = {}
    for cell in wanted:
        days_of.setdefault(str(cell["employee"]), set()).add(cell["day"])

    matcher = Q()
    for employee, days in days_of.items():
        matcher |= Q(employee_id=employee, day__in=days)
    Shift.objects.filter(matcher).delete()

    drawn = []
    for cell in wanted:
        pattern = patterns.get(str(cell["pattern"])) if cell.get("pattern") else None
        segments = pattern.segments if pattern else cell.get("segments")
        if not segments:
            continue
        drawn.append(
            Shift(
                tenant=company,
                employee=people[str(cell["employee"])],
                day=cell["day"],
                pattern=pattern,
                segments=segments,
            )
        )

    Shift.objects.bulk_create(drawn)
    return {"painted": len(drawn), "cleared": len(wanted) - len(drawn)}


def _users():
    """Imported late: `users` imports this module's app for the roster."""
    from apps.users import models

    return models.User


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

    framework = legal.for_company(company)

    findings: list[Finding] = []
    for employee_id, roster in by_person.items():
        findings.extend(_check_daily_rest(roster, rules, framework.shifts, first, last))
        findings.extend(_check_weekly_hours(employee_id, roster, rules, first, last))
        findings.extend(_check_breaks(roster, rules, first, last))
        findings.extend(
            _check_weekly_rest(
                employee_id, roster, rules, framework.minors, framework.shifts, first, last
            )
        )
        findings.extend(
            _check_night_work(roster, rules, framework.night, framework.shifts, first, last)
        )
        findings.extend(_check_under_eighteen(roster, rules, framework.minors, first, last))
    findings.extend(_check_leave_clashes(first, last, employee))
    findings.extend(_check_rostered_on_a_holiday(by_person, first, last))
    findings.extend(_check_outside_the_contract(by_person))
    findings.extend(_check_time_actually_worked(company, rules, first, last, employee))

    # The citation comes from the company's country, not from the place the
    # finding was built. Nine of them used to be typed in beside each `Finding`,
    # which made every warning quietly Spanish --- and made adding a country a
    # search-and-replace through this file.
    findings = [replace(f, basis=framework.finding_citation(f.code).basis) for f in findings]

    # Filled in one pass rather than at each of the nine places a Finding is
    # built: one of them would be forgotten, and a warning about a person whose
    # name is missing reads like a bug in the warning.
    # Only the blanks. The names map is built from the roster, and somebody with
    # no fixed schedule has no roster at all --- their findings come from the
    # record and already carry the name. Overwriting would blank exactly the
    # people the worked-time check exists for.
    names = {shift.employee_id: shift.employee.get_full_name() for shift in shifts}
    findings = [
        f if f.employee_name else replace(f, employee_name=names.get(f.employee_id, ""))
        for f in findings
    ]

    return sorted(findings, key=lambda f: (f.day, f.code))


def _check_daily_rest(roster, rules, shifts_law, first, last) -> list[Finding]:
    """Rest between one day and the next, against the floor that applies.

    Two floors, not one. The ordinary twelve hours, and --- for somebody on
    rotating shifts, on the day the rotation moves them --- the shorter one the
    law allows precisely so that the rotation is possible. Applying the ordinary
    floor to a changeover reported every rotating team in the country as being
    in breach, which is how this check came to be rewritten.

    The shorter rest is still reported. It is not a breach and the wording says
    so, but the difference has to be given back within four weeks and nobody
    gives back what nobody wrote down.
    """
    found = []
    person = roster[0].employee if roster else None
    rotating = bool(person and person.rotating_shifts and shifts_law)

    for previous, current in pairwise(roster):
        gap = (current.starts_at - previous.ends_at).total_seconds() / 3600
        if gap >= rules.daily_rest_hours or not (first <= current.day <= last):
            continue

        # A changeover is a day the shift moved. Same hours two days running is
        # not a rotation, and a short rest there is short for the ordinary
        # reason --- the roster asked for it.
        moved = rotating and _start_of(current) != _start_of(previous)

        if moved and gap >= float(shifts_law.changeover_rest_hours):
            found.append(
                Finding(
                    day=current.day,
                    employee_id=current.employee_id,
                    code="changeover_rest_owed",
                    message=_(
                        "%(hours)s h of rest at a shift changeover, which is allowed. "
                        "The %(owed)s h missing from the usual %(usual)s h are owed back "
                        "within %(weeks)s weeks."
                    )
                    % {
                        "hours": f"{gap:.1f}",
                        "owed": f"{float(rules.daily_rest_hours) - gap:.1f}",
                        "usual": f"{float(rules.daily_rest_hours):g}",
                        "weeks": shifts_law.accumulation_weeks,
                    },
                )
            )
            continue

        floor = float(shifts_law.changeover_rest_hours) if moved else float(rules.daily_rest_hours)
        found.append(
            Finding(
                day=current.day,
                employee_id=current.employee_id,
                code="short_daily_rest",
                message=(
                    _(
                        "Only %(hours)s h of rest since the previous shift, under the "
                        "%(floor)s h a changeover may go down to."
                    )
                    if moved
                    else _("Only %(hours)s h of rest since the previous shift.")
                )
                % {"hours": f"{gap:.1f}", "floor": f"{floor:g}"},
            )
        )
    return found


def _start_of(shift) -> str:
    """The shift's starting time as text, for telling one shift team from another."""
    return min(span["start"] for span in shift.segments)


def _check_weekly_hours(employee_id, roster, rules, first, last) -> list[Finding]:
    """Hours per week, against two different things.

    They used to be one check against the company's figure, which meant a
    twenty-five hour contract rostered for thirty-eight said nothing at all:
    thirty-eight is under forty, so the legal ceiling was fine and nobody was
    looking at the contract.

    They are not the same question and they do not have the same answer:

    **Over the legal maximum** is a breach. Art. 34.1 ET sets it and no contract
    may go above it.

    **Over what was agreed** is not. Those extra hours are lawful and they are a
    *different kind of hour* --- complementary, under art. 12.5 for part-time
    work --- with their own cap and their own duty to be recorded separately.
    Reporting it as an excess would be wrong; saying nothing loses the only
    signal that the roster is asking for hours nobody agreed to.

    Weeks only partly inside the window are skipped. Reporting a half-counted
    week as an excess would be worse than saying nothing: whoever reads it goes
    looking for hours that are not there and stops trusting the rest.
    """
    weeks: dict = {}
    for shift in roster:
        year, week, _weekday = shift.day.isocalendar()
        weeks.setdefault((year, week), []).append(shift)

    ceiling = float(rules.weekly_hours)
    person = roster[0].employee

    # Only a weekly figure can be compared week by week. An annual one --- 1700
    # hours in the gardening agreement --- is met or missed over a year, and
    # dividing it by 52 would produce a number nobody agreed to and that no
    # single week is supposed to match.
    agreed_pair = person.agreed_hours(rules)
    agreed = agreed_pair[0] if agreed_pair and agreed_pair[1] == "WEEK" else None

    found = []
    for (_year, _week), shifts_of_week in weeks.items():
        monday = min(s.day for s in shifts_of_week) - timedelta(
            days=min(s.day for s in shifts_of_week).weekday()
        )
        sunday = monday + timedelta(days=6)
        if monday < first or sunday > last:
            continue

        hours = sum(s.minutes for s in shifts_of_week) / 60

        if hours > ceiling:
            found.append(
                Finding(
                    day=monday,
                    employee_id=employee_id,
                    code="weekly_hours_exceeded",
                    message=_("%(hours)s h rostered that week, over the %(limit)s h configured.")
                    % {"hours": f"{hours:.1f}", "limit": f"{ceiling:g}"},
                )
            )
        # Only when it is not already over the ceiling: two warnings about the
        # same week would bury the more serious one.
        elif agreed is not None and hours > agreed:
            found.append(
                Finding(
                    day=monday,
                    employee_id=employee_id,
                    code="over_contracted_hours",
                    message=_(
                        "%(hours)s h rostered that week against %(agreed)s h contracted. "
                        "The %(extra)s h over are complementary hours and count towards "
                        "their own limit."
                    )
                    % {
                        "hours": f"{hours:.1f}",
                        "agreed": f"{agreed:g}",
                        "extra": f"{hours - agreed:.1f}",
                    },
                )
            )

    # Somebody with no agreed weekly figure has nothing to be measured against.
    # Said once for the window rather than passed over in silence: a roster
    # screen with no warnings should mean "nothing to say", not "not looked at".
    if not person.has_agreed_hours and roster:
        found.append(
            Finding(
                day=first,
                employee_id=employee_id,
                code="no_agreed_weekly_hours",
                message=_(
                    "No agreed weekly hours on this contract, so the weekly total is "
                    "not checked. Only the legal maximum applies."
                ),
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
                )
            )
    return found


def _check_weekly_rest(
    employee_id, roster, rules, minors, shifts_law, first, last
) -> list[Finding]:
    """Art. 37.1 ET: a day and a half uninterrupted, accumulable.

    The accumulation is why this looks at a period rather than at each week.
    Reporting a week without its full rest would be wrong for anybody on a
    pattern that concentrates it --- which is most of hospitality and retail ---
    and a warning that is wrong half the time gets ignored the other half.

    Fourteen days as a rule; four weeks for somebody on rotating shifts, which
    is the longer window art. 19.b RD 1561/1995 gives them. Reading a rotating
    rota against the shorter one produces the same false positive the daily rest
    used to: lawful patterns reported as breaches, on the days the law wrote the
    exception for.
    """
    if not roster:
        return []

    # Two uninterrupted days for a minor (art. 37.1), and the company's figure
    # for everybody else. Taken from the first day of the window: somebody who
    # turns eighteen inside it keeps the stronger floor for that fortnight,
    # which errs on the side of the protection.
    person = roster[0].employee
    minimum = timedelta(
        hours=minors.weekly_rest_hours if person.is_minor_on(first) else rules.weekly_rest_hours
    )
    found = []

    span_days = shifts_law.accumulation_weeks * 7 if shifts_law and person.rotating_shifts else 14

    # Longest gap in each rolling period that sits inside the window.
    days = sorted({s.day for s in roster})
    for anchor in days:
        window_end = anchor + timedelta(days=span_days - 1)
        if anchor < first or window_end > last:
            continue

        inside = [s for s in roster if anchor <= s.day <= window_end]
        if len(inside) < 2:
            continue

        ordered = sorted(inside, key=lambda s: s.day)
        gaps = [b.starts_at - a.ends_at for a, b in pairwise(ordered)]

        # The edges count too. A fortnight of ten days on followed by four off
        # has its rest at the end, and looking only between shifts would miss
        # it and report a pattern that is perfectly lawful.
        window_opens = datetime.combine(anchor, dt_time.min)
        window_closes = datetime.combine(window_end + timedelta(days=1), dt_time.min)
        gaps.append(ordered[0].starts_at - window_opens)
        gaps.append(window_closes - ordered[-1].ends_at)

        longest = max(gaps, default=timedelta(0))
        if longest < minimum:
            found.append(
                Finding(
                    day=anchor,
                    employee_id=employee_id,
                    code="short_weekly_rest",
                    message=_(
                        "The longest break in those %(days)s days is %(hours)s h, under "
                        "the %(minimum)s h configured."
                    )
                    % {
                        "days": span_days,
                        "hours": f"{longest.total_seconds() / 3600:.0f}",
                        "minimum": minimum.total_seconds() / 3600,
                    },
                )
            )
            break  # one per person is enough to say the pattern is wrong

    return found


def _check_night_work(roster, rules, night, shifts_law, first, last) -> list[Finding]:
    """Art. 36.1 and 36.3 ET: the status, then the limits it brings.

    The order matters and getting it backwards was one of the four errors the
    legal review corrected. The eight-hour average attaches to somebody who
    **holds the status of night worker**, not to anybody who happens to work
    between 22:00 and 06:00, so the status is settled first and the limits are
    only applied to whoever holds it.

    Three things come out of here:

    **The status is unrecorded but the roster shows it.** Reported, because it
    is a decision the company owes the person --- the status carries a health
    assessment and a pay supplement, neither of which this product handles.

    **The average over the reference period.** An average, not a ceiling: nine
    hours on Tuesday breaches nothing if the fortnight comes out at eight.

    **Too long on the night shift.** Art. 36.3 caps the run at two consecutive
    weeks on a rotation, unless the person asked to stay.
    """
    if not night or not roster:
        return []

    person = roster[0].employee
    window = (night.window_starts_at, night.window_ends_at)
    inside = [s for s in roster if first <= s.day <= last]
    if not inside:
        return []

    holds = person.holds_night_worker_status(night, roster)
    found = []

    # The roster's own reading, said out loud when the company has not answered.
    # An override to "no" is left alone: the company answered, and repeating the
    # reading underneath its answer would read as the product arguing.
    if person.night_worker == "AUTO" and holds:
        nightly = sum(
            1 for s in inside if s.night_minutes(*window) >= night.qualifying_daily_hours * 60
        )
        found.append(
            Finding(
                day=min(s.day for s in inside),
                employee_id=person.pk,
                code="looks_like_night_work",
                message=_(
                    "%(count)s of %(total)s days with %(hours)s h or more at night. If "
                    "the person holds the status of night worker, that brings a "
                    "%(limit)s h average over %(days)s days, a ban on overtime and a "
                    "health assessment. Nobody has recorded whether they do."
                )
                % {
                    "count": nightly,
                    "total": len(inside),
                    "hours": f"{night.qualifying_daily_hours:g}",
                    "limit": f"{night.average_daily_hours:g}",
                    "days": night.average_over_days,
                },
            )
        )

    if holds:
        declared = person.night_worker == "YES"
        found.extend(_check_night_average(person, inside, night, declared, first, last))

    if shifts_law and shifts_law.max_consecutive_night_weeks and not person.voluntary_night_shift:
        found.extend(_check_consecutive_night_weeks(person, inside, night, shifts_law))

    return found


def _check_night_average(person, roster, night, declared, first, last) -> list[Finding]:
    """Eight hours a day on average across the reference period.

    Averaged over every day in the period, not over the days worked: art. 36.1
    says "de promedio, en un período de referencia de quince días", and the rest
    days are part of what the average is taken over. Dividing by days worked
    instead would make a four-on-four-off rota --- the commonest night pattern
    there is --- look like a breach on every single window.

    Two wordings, depending on who decided the status. When the company recorded
    it, this is a limit that was exceeded and says so. When the roster inferred
    it, the excess is stated conditionally --- the status carries obligations
    outside this product, the annual limb of art. 36.1 is invisible from a
    month of calendar, and telling a company it breached a limit its people may
    not even be subject to is the error the legal review already caught once.
    """
    by_day = {s.day: s.minutes for s in roster}
    span = night.average_over_days
    found = []

    for anchor in sorted(by_day):
        window_end = anchor + timedelta(days=span - 1)
        if anchor < first or window_end > last:
            continue
        worked = sum(minutes for day, minutes in by_day.items() if anchor <= day <= window_end)
        average = worked / 60 / span
        if average > night.average_daily_hours:
            found.append(
                Finding(
                    day=anchor,
                    employee_id=person.pk,
                    code="night_worker_average",
                    message=(
                        _(
                            "A night worker averaging %(average)s h a day over %(days)s "
                            "days, above the %(limit)s h allowed."
                        )
                        if declared
                        else _(
                            "Averaging %(average)s h a day over %(days)s days. The roster "
                            "reads like night work, and if the status applies that is "
                            "above the %(limit)s h of art. 36.1 ET."
                        )
                    )
                    % {
                        "average": f"{average:.1f}",
                        "days": span,
                        "limit": f"{night.average_daily_hours:g}",
                    },
                )
            )
            break  # one is enough to say the period is over; the rest overlap

    return found


def _check_consecutive_night_weeks(person, roster, night, shifts_law) -> list[Finding]:
    """Art. 36.3 ET: no more than two weeks running on the night shift.

    Only for somebody who did not volunteer --- the article's own exception, and
    the reason `voluntary_night_shift` is a field. A rota is read week by week:
    a week counts as a night week when most of its rostered days are nights,
    which is how a team is actually assigned to a shift.
    """
    window = (night.window_starts_at, night.window_ends_at)
    weeks: dict = {}
    for shift in roster:
        year, week, _weekday = shift.day.isocalendar()
        weeks.setdefault((year, week), []).append(shift)

    run, started = 0, None
    for key in sorted(weeks):
        days = weeks[key]
        nights = sum(
            1 for s in days if s.night_minutes(*window) >= night.qualifying_daily_hours * 60
        )
        if nights * 2 > len(days):
            run += 1
            started = started or min(s.day for s in days)
            if run > shifts_law.max_consecutive_night_weeks:
                return [
                    Finding(
                        day=started,
                        employee_id=person.pk,
                        code="consecutive_night_weeks",
                        message=_(
                            "%(weeks)s consecutive weeks on the night shift, over the "
                            "%(limit)s allowed. More needs the person to have asked for "
                            "it, which is a field on their record."
                        )
                        % {"weeks": run, "limit": shifts_law.max_consecutive_night_weeks},
                    )
                ]
        else:
            run, started = 0, None
    return []


def _check_under_eighteen(roster, rules, minors, first, last) -> list[Finding]:
    """The floors that apply to workers under eighteen.

    Age is read **per day**, not once: somebody turns eighteen mid-roster and
    the protections stop from that date. Evaluating it once for the whole window
    would either apply them a month too long or drop them a month too early.

    These are the only findings in the module phrased as prohibitions. Elsewhere
    the wording is careful to say "departs from the rules configured", because
    sector regimes lawfully modify them. Here nothing does: art. 6.2 and 6.3
    admit no amount that is allowed, and no agreement can lower art. 34.3 or
    34.4 for a minor.
    """
    found = []
    for shift in roster:
        if not (first <= shift.day <= last):
            continue
        if not shift.employee.is_minor_on(shift.day):
            continue

        hours = shift.minutes / 60

        if hours > minors.max_daily_hours:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="minor_over_daily_limit",
                    message=_(
                        "%(hours)s h rostered for somebody under eighteen. The limit is "
                        "%(limit)s h a day and no agreement can raise it."
                    )
                    % {"hours": f"{hours:.1f}", "limit": minors.max_daily_hours},
                )
            )

        if len(shift.segments) == 1 and hours > minors.break_after_hours:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="minor_break_owed",
                    message=_(
                        "A continuous day of %(hours)s h for somebody under eighteen "
                        "needs a break of %(minutes)s min, from %(after)s h."
                    )
                    % {
                        "hours": f"{hours:.1f}",
                        "minutes": minors.break_minutes,
                        "after": f"{minors.break_after_hours:g}",
                    },
                )
            )

        if shift.overlaps_night(rules.night_starts_at, rules.night_ends_at):
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="minor_night_work",
                    message=_(
                        "Night shift rostered for somebody under eighteen. Art. 6.2 ET "
                        "forbids it outright: there is no permitted amount."
                    ),
                )
            )

    return found


def _check_time_actually_worked(company, rules, first, last, employee) -> list[Finding]:
    """The same limits, against the record instead of the plan.

    Every other check here reads the roster, and that leaves two holes.

    Somebody with no fixed schedule has no roster at all --- which is right,
    there is nothing to plan --- and so had **no limits check of any kind**. They
    could work sixty hours a week and nothing said a word.

    And for everybody else the roster is a plan. A company that rosters forty
    and works fifty is over the maximum, and art. 34.1 ET is about hours
    actually worked, not hours intended.

    So this reads punches. Weeks only fully inside the window, for the same
    reason as the roster check: a half-counted week reported as an excess sends
    somebody looking for hours that are not there.
    """
    from apps.punches.models import Punch, PunchType

    zone = company.tzinfo
    punches = Punch.objects.filter(
        timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        timestamp__lt=datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=zone),
        is_active=True,
    ).select_related("employee")
    if employee is not None:
        punches = punches.filter(employee=employee)

    # Pair each person's events into worked spans. An unclosed one is left out
    # rather than guessed at: inventing an end would put hours in the total that
    # nobody recorded.
    spans: dict = {}
    for punch in punches.order_by("employee_id", "timestamp"):
        bucket = spans.setdefault(
            punch.employee_id, {"person": punch.employee, "open": None, "weeks": {}}
        )
        if punch.punch_type == PunchType.IN:
            bucket["open"] = punch.timestamp
        elif bucket["open"] is not None:
            local = bucket["open"].astimezone(zone)
            year, week, _weekday = local.date().isocalendar()
            hours = (punch.timestamp - bucket["open"]).total_seconds() / 3600
            bucket["weeks"][(year, week)] = bucket["weeks"].get((year, week), 0) + hours
            bucket["open"] = None

    ceiling = float(rules.weekly_hours)
    found = []
    for employee_id, bucket in spans.items():
        person = bucket["person"]
        agreed_pair = person.agreed_hours(rules)
        agreed = agreed_pair[0] if agreed_pair and agreed_pair[1] == "WEEK" else None

        for (year, week), hours in bucket["weeks"].items():
            monday = date.fromisocalendar(year, week, 1)
            if monday < first or monday + timedelta(days=6) > last:
                continue

            if hours > ceiling:
                found.append(
                    Finding(
                        day=monday,
                        employee_id=employee_id,
                        code="worked_over_the_maximum",
                        employee_name=person.get_full_name(),
                        message=_(
                            "%(hours)s h actually worked that week, over the %(limit)s h "
                            "maximum. This is the record, not the roster."
                        )
                        % {"hours": f"{hours:.1f}", "limit": f"{ceiling:g}"},
                    )
                )
            elif agreed is not None and hours > agreed:
                found.append(
                    Finding(
                        day=monday,
                        employee_id=employee_id,
                        code="worked_over_the_contract",
                        employee_name=person.get_full_name(),
                        message=_("%(hours)s h actually worked against %(agreed)s h contracted.")
                        % {"hours": f"{hours:.1f}", "agreed": f"{agreed:g}"},
                    )
                )
    return found


def _check_outside_the_contract(by_person) -> list[Finding]:
    """Somebody rostered on a day their contract does not cover.

    Within one company there will be open-ended contracts, six-month ones and
    permanent-seasonal ones, and a roster drawn a month ahead does not know
    which ended last Friday. Nothing else catches it: the person still exists,
    is still active, and every other check passes happily on a day they are not
    engaged for.
    """
    found = []
    for _employee_id, roster in by_person.items():
        person = roster[0].employee
        if not (person.contract_start or person.contract_end):
            continue
        for shift in roster:
            if person.is_engaged_on(shift.day):
                continue
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="outside_the_contract",
                    message=_("Rostered on a day outside the dates of their contract."),
                )
            )
    return found


def _check_rostered_on_a_holiday(by_person, first, last) -> list[Finding]:
    """Somebody rostered on a public holiday.

    Not a breach, and the wording says so. Art. 37.2 makes the fourteen days
    non-recoverable and paid, and working one is lawful --- what it generates is
    compensation, in rest or in pay, and which one is the collective agreement's
    business rather than ours.

    It is reported because it is a decision somebody has to have made, and
    because the compensation is owed from the moment the day is worked. The
    roster is where it first becomes visible.

    Which days are holidays depends on the **workplace**: two of the fourteen
    are the town hall's, so a company with sites in two provinces has two
    calendars and one of them is not the other's.
    """
    from apps.tenants.holidays import holidays_for

    found = []
    for roster in by_person.values():
        if not roster:
            continue
        person = roster[0].employee
        off = holidays_for(person, first, last)
        if not off:
            continue
        for shift in roster:
            if first <= shift.day <= last and shift.day in off:
                found.append(
                    Finding(
                        day=shift.day,
                        employee_id=person.pk,
                        code="rostered_on_a_holiday",
                        message=_(
                            "Rostered on a public holiday. It is allowed, and it earns "
                            "compensation in rest or in pay under the agreement."
                        ),
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
