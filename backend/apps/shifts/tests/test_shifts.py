"""Rosters: the arithmetic, and the line that must not be crossed.

The line first, because everything else is detail: **a shift is not the
record**. Nothing here may ever produce a clock event. A record that filled
itself in from the plan would be the exact fiction art. 34.9 ET exists to
prevent, and it would be indistinguishable from a real one.

The arithmetic that keeps breaking in this kind of code is midnight. A night
shift from 22:00 to 06:00 is eight hours, not minus sixteen, and the rest before
it is measured from the previous day's end --- which is itself on another date.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError

from apps.absences.models import AbsenceType
from apps.absences.services import approve_absence, request_absence
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftPattern, span_minutes
from apps.shifts.services import (
    assign_pattern,
    expected_vs_worked,
    review_roster,
    weekdays_in,
)
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

MORNING = [{"start": "08:00", "end": "16:00"}]
LONG_DAY = [{"start": "08:00", "end": "17:00"}]
NIGHT = [{"start": "22:00", "end": "06:00"}]
SPLIT = [{"start": "09:00", "end": "13:00"}, {"start": "15:00", "end": "19:00"}]


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


def pattern(company, name, segments):
    with tenant_context(company.id):
        return ShiftPattern.objects.create(tenant=company, name=name, segments=segments)


def shift(company, worker, day, segments):
    with tenant_context(company.id):
        return Shift.objects.create(tenant=company, employee=worker, day=day, segments=segments)


# ---------------------------------------------------------------------- midnight


def test_a_night_span_is_eight_hours_not_minus_sixteen():
    """The one that breaks first in every roster implementation."""
    assert span_minutes({"start": "22:00", "end": "06:00"}) == 8 * 60
    assert span_minutes({"start": "08:00", "end": "16:00"}) == 8 * 60
    assert span_minutes({"start": "23:30", "end": "00:30"}) == 60


@pytest.mark.django_db
def test_a_night_shift_ends_on_the_following_day(company, worker):
    night = shift(company, worker, date(2026, 9, 1), NIGHT)

    assert night.starts_at.date() == date(2026, 9, 1)
    assert night.ends_at.date() == date(2026, 9, 2)
    assert night.minutes == 8 * 60


@pytest.mark.django_db
def test_a_split_day_adds_its_spans(company, worker):
    split = shift(company, worker, date(2026, 9, 1), SPLIT)

    assert split.minutes == 8 * 60
    assert split.starts_at.hour == 9
    assert split.ends_at.hour == 19


# ------------------------------------------------------------------- assigning


@pytest.mark.django_db
def test_assigning_copies_the_spans_rather_than_pointing_at_them(company, worker):
    """Editing "morning" next month must not rewrite a day already published:
    people arranged their lives around it."""
    morning = pattern(company, "Mañana", MORNING)
    with tenant_context(company.id):
        assign_pattern(employee=worker, company=company, pattern=morning, days=[date(2026, 9, 1)])

        morning.segments = [{"start": "06:00", "end": "14:00"}]
        morning.save(update_fields=["segments"])

        stored = Shift.objects.get(employee=worker, day=date(2026, 9, 1))

    assert stored.segments == MORNING


@pytest.mark.django_db
def test_reassigning_replaces_instead_of_clashing(company, worker):
    """A roster gets redrawn. Refusing would turn one action into two with a
    broken state in between."""
    morning = pattern(company, "Mañana", MORNING)
    night = pattern(company, "Noche", NIGHT)
    days = [date(2026, 9, 1), date(2026, 9, 2)]

    with tenant_context(company.id):
        assign_pattern(employee=worker, company=company, pattern=morning, days=days)
        assign_pattern(employee=worker, company=company, pattern=night, days=days)

        assert Shift.objects.filter(employee=worker).count() == 2
        assert Shift.objects.get(employee=worker, day=days[0]).segments == NIGHT


@pytest.mark.django_db
def test_one_shift_per_person_per_day(company, worker):
    """A split day is several spans in one shift, not two shifts. Otherwise
    "what is expected today" has no single answer."""
    from django.db import IntegrityError, transaction

    shift(company, worker, date(2026, 9, 1), MORNING)

    with pytest.raises(IntegrityError), transaction.atomic(), tenant_context(company.id):
        Shift.objects.create(tenant=company, employee=worker, day=date(2026, 9, 1), segments=NIGHT)


@pytest.mark.django_db
def test_assigning_nothing_is_refused(company, worker):
    morning = pattern(company, "Mañana", MORNING)
    with pytest.raises(BusinessRuleError) as caught, tenant_context(company.id):
        assign_pattern(employee=worker, company=company, pattern=morning, days=[])
    assert caught.value.code == "no_days"


def test_weekdays_picks_the_right_days():
    """Monday to Friday of the first full week of September 2026."""
    days = weekdays_in(date(2026, 9, 1), date(2026, 9, 13), [0, 1, 2, 3, 4])

    assert date(2026, 9, 5) not in days  # Saturday
    assert date(2026, 9, 6) not in days  # Sunday
    assert date(2026, 9, 7) in days  # Monday
    assert len(days) == 9


# -------------------------------------------------------------------- segments


@pytest.mark.django_db
def test_a_shift_with_no_spans_is_refused(company, worker):
    with pytest.raises(ValidationError):
        Shift(tenant=company, employee=worker, day=date(2026, 9, 1), segments=[]).clean()


@pytest.mark.django_db
def test_a_malformed_span_is_caught_when_saved_not_later(company, worker):
    """Otherwise it does not fail until something compares the roster against a
    real day, by which time it has been on a screen for a week."""
    for broken in ([{"start": "08:00"}], [{"start": "8am", "end": "4pm"}], ["08:00-16:00"]):
        with pytest.raises(ValidationError):
            Shift(tenant=company, employee=worker, day=date(2026, 9, 1), segments=broken).clean()


# --------------------------------------------------------------------- review


@pytest.mark.django_db
def test_a_short_rest_between_days_is_reported(company, worker):
    """Closing at 22:00 and opening at 06:00 is eight hours of rest."""
    with tenant_context(company.id):
        shift(company, worker, date(2026, 9, 1), [{"start": "14:00", "end": "22:00"}])
        shift(company, worker, date(2026, 9, 2), [{"start": "06:00", "end": "14:00"}])

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    rest = [f for f in findings if f.code == "short_daily_rest"]
    assert len(rest) == 1
    assert rest[0].day == date(2026, 9, 2)
    assert rest[0].basis == "Art. 34.3 ET"


@pytest.mark.django_db
def test_a_lawful_rest_is_not_reported(company, worker):
    with tenant_context(company.id):
        shift(company, worker, date(2026, 9, 1), MORNING)  # ends 16:00
        shift(company, worker, date(2026, 9, 2), MORNING)  # starts 08:00 -> 16 h
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "short_daily_rest"] == []


@pytest.mark.django_db
def test_the_review_looks_one_day_past_the_window(company, worker):
    """Rest is a property of the boundary between two shifts, so a month checked
    in isolation would miss a clash with the month before."""
    with tenant_context(company.id):
        shift(company, worker, date(2026, 8, 31), [{"start": "14:00", "end": "22:00"}])
        shift(company, worker, date(2026, 9, 1), [{"start": "06:00", "end": "14:00"}])

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f.code for f in findings if f.code == "short_daily_rest"] == ["short_daily_rest"]


@pytest.mark.django_db
def test_too_many_hours_in_a_week_are_reported(company, worker):
    with tenant_context(company.id):
        # Monday to Sunday, 8 h a day = 56 h
        for offset in range(7):
            shift(company, worker, date(2026, 9, 7) + timedelta(days=offset), MORNING)

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    weekly = [f for f in findings if f.code == "weekly_hours_exceeded"]
    assert len(weekly) == 1
    assert weekly[0].basis == "Art. 34.1 ET"


@pytest.mark.django_db
def test_a_week_only_half_inside_the_window_is_not_reported(company, worker):
    """Reporting a half-counted week as an excess is worse than saying nothing:
    whoever reads it goes looking for hours that are not there."""
    with tenant_context(company.id):
        for offset in range(7):
            shift(company, worker, date(2026, 9, 7) + timedelta(days=offset), MORNING)

        # Window cuts the week in half.
        findings = review_roster(company=company, first=date(2026, 9, 9), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "weekly_hours_exceeded"] == []


@pytest.mark.django_db
def test_a_long_continuous_day_is_owed_a_break(company, worker):
    with tenant_context(company.id):
        shift(company, worker, date(2026, 9, 1), [{"start": "08:00", "end": "17:00"}])
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    owed = [f for f in findings if f.code == "break_owed"]
    assert len(owed) == 1
    assert owed[0].basis == "Art. 34.4 ET"


@pytest.mark.django_db
def test_a_split_day_is_not_owed_one(company, worker):
    with tenant_context(company.id):
        shift(company, worker, date(2026, 9, 1), SPLIT)  # 8 h, but in two spans
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "break_owed"] == []


@pytest.mark.django_db
def test_being_rostered_on_approved_leave_is_reported(company, worker):
    """The most ordinary planning mistake, and the one that reaches the worker
    fastest: they turn up, or they do not and it looks like an absence."""
    with tenant_context(company.id):
        boss = User.objects.create_user(
            email="boss@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Jefa",
            role=Role.MANAGER,
        )
        absence = request_absence(
            employee=worker,
            company=company,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 11),
        )
        approve_absence(absence, resolved_by=boss)

        shift(company, worker, date(2026, 9, 9), MORNING)
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    clashes = [f for f in findings if f.code == "rostered_on_leave"]
    assert len(clashes) == 1
    assert clashes[0].day == date(2026, 9, 9)
    # This one is built from the absence rather than from the roster loop, so
    # it is the finding most likely to slip past the pass that fills in names.
    assert clashes[0].employee_name == worker.get_full_name()


@pytest.mark.django_db
def test_every_finding_says_who_it_is_about(company, worker):
    """The name is filled in one pass at the end rather than at each of the
    nine places a Finding is built. That is less fragile but it is also silent:
    a code that stops matching would produce warnings about nobody. The roster
    below is written to break several rules at once so the check has something
    to be right about."""
    with tenant_context(company.id):
        # Twelve days straight of nine-hour shifts: over the daily limit, short
        # of weekly rest, and past the weekly hours.
        for offset in range(12):
            shift(company, worker, date(2026, 9, 7) + timedelta(days=offset), LONG_DAY)
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert len(findings) > 1, "the roster was meant to break several rules"
    nameless = [f.code for f in findings if not f.employee_name]
    assert nameless == []


@pytest.mark.django_db
def test_a_finding_about_somebody_with_no_roster_still_names_them(company, worker):
    """The case the pass above cannot cover, and it came out blank on screen.

    The names come from the roster, and the whole point of checking the record
    is to reach people who have none --- anybody with no fixed schedule. Their
    warning has to carry its own name.
    """
    from apps.punches.models import Punch, PunchSource, PunchType
    from apps.users.models import WorkingTimeRegime

    with tenant_context(company.id):
        worker.regime = WorkingTimeRegime.VARIABLE
        worker.save(update_fields=["regime"])

        # A full week of long days, and not one shift.
        for offset in range(6):
            day = date(2026, 9, 7) + timedelta(days=offset)
            for hour, kind in ((7, PunchType.IN), (19, PunchType.OUT)):
                Punch.objects.create(
                    tenant=company,
                    employee=worker,
                    timestamp=datetime.combine(day, time(hour, 0), tzinfo=company.tzinfo),
                    punch_type=kind,
                    source=PunchSource.WEB,
                )

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    worked = [f for f in findings if f.code == "worked_over_the_maximum"]
    assert worked, "seventy-two hours in a week and nothing said so"
    assert worked[0].employee_name == worker.get_full_name()


@pytest.mark.django_db
def test_nothing_is_ever_refused_only_reported(company, worker):
    """The decision recorded in apps.tenants.rules. RD 1561/1995 modifies the
    rest periods for transport, on-call work and shift handovers, all lawfully;
    refusing would make the product unusable there and would mean deciding a
    compliance question that is not ours."""
    with tenant_context(company.id):
        shift(company, worker, date(2026, 9, 1), [{"start": "08:00", "end": "23:00"}])
        awful = shift(company, worker, date(2026, 9, 2), [{"start": "01:00", "end": "23:00"}])

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert awful.pk is not None  # saved, not refused
    assert len(findings) > 0  # and reported


@pytest.mark.django_db
def test_the_rules_are_the_companys_own(company, worker):
    """They are data, not constants: a company on a 35-hour agreement gets
    warned at 35, not at 40."""
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.weekly_hours = 20
        rules.save(update_fields=["weekly_hours"])

        for offset in range(5):
            shift(company, worker, date(2026, 9, 7) + timedelta(days=offset), MORNING)  # 40 h

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert any(f.code == "weekly_hours_exceeded" for f in findings)


# ------------------------------------------------- the roster is not the record


@pytest.mark.django_db
def test_a_roster_never_creates_a_clock_event(company, worker):
    """The line the whole module lives on. A record that filled itself in from
    the plan would be the fiction art. 34.9 ET exists to prevent --- and it would
    look identical to a real one."""
    from apps.punches.models import Punch

    morning = pattern(company, "Mañana", MORNING)
    with tenant_context(company.id):
        assign_pattern(
            employee=worker,
            company=company,
            pattern=morning,
            days=[date(2026, 9, 1), date(2026, 9, 2)],
        )

    assert Punch.objects_all_tenants.count() == 0


@pytest.mark.django_db
def test_expected_against_worked_reports_both_without_mixing_them(company, worker):
    from django.utils import timezone

    from apps.punches.services import register_punch

    today = timezone.localdate()
    with tenant_context(company.id):
        shift(company, worker, today, MORNING)
        register_punch(employee=worker, company=company)  # in, still open

        result = expected_vs_worked(employee=worker, company=company, day=today)

    assert result["expected_minutes"] == 480
    assert result["worked_minutes"] == 0  # nothing closed yet
    assert result["difference_minutes"] == -480
    assert result["has_shift"] is True


@pytest.mark.django_db
def test_a_day_with_no_shift_says_so(company, worker):
    from django.utils import timezone

    with tenant_context(company.id):
        result = expected_vs_worked(employee=worker, company=company, day=timezone.localdate())

    assert result["has_shift"] is False
    assert result["expected_minutes"] == 0


# ------------------------------------- the rules that were configured and unused


@pytest.mark.django_db
def test_a_fortnight_with_no_long_break_is_reported(company, worker):
    """Art. 37.1 ET: a day and a half uninterrupted, accumulable over fourteen
    days. Fourteen straight days of work has no such break anywhere."""
    with tenant_context(company.id):
        for offset in range(14):
            shift(company, worker, date(2026, 9, 1) + timedelta(days=offset), MORNING)

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    weekly = [f for f in findings if f.code == "short_weekly_rest"]
    assert len(weekly) == 1
    assert weekly[0].basis == "Art. 37.1 ET"


@pytest.mark.django_db
def test_rest_concentrated_at_the_end_of_the_fortnight_is_accepted(company, worker):
    """The accumulation is the point. Ten days on and then a long break is
    lawful, and a warning that fires here would be wrong for most of hospitality
    --- and a warning that is wrong half the time gets ignored the other half."""
    with tenant_context(company.id):
        for offset in range(10):
            shift(company, worker, date(2026, 9, 1) + timedelta(days=offset), MORNING)
        # Then four days off, and back on the 15th.
        shift(company, worker, date(2026, 9, 15), MORNING)

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "short_weekly_rest"] == []


@pytest.mark.django_db
def test_repeated_night_shifts_flag_the_status_not_a_limit(company, worker):
    """The correction that cost us an external review. Art. 36.1 ET attaches
    its limits to somebody who **holds the status** of night worker, not to
    anybody who happens to work between 22:00 and 06:00. So this says what it
    found and leaves the status to the company."""
    with tenant_context(company.id):
        for offset in range(5):
            shift(company, worker, date(2026, 9, 1) + timedelta(days=offset), NIGHT)

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    night = [f for f in findings if f.code == "looks_like_night_work"]
    assert len(night) == 1
    assert night[0].basis == "Art. 36.1 ET"

    # The wording is the point, not the count. It has to make the limits
    # conditional on the status --- "if the person holds it" --- and never
    # assert that one has been exceeded. Checked in English so the assertion
    # does not depend on which catalogue is compiled.
    from django.utils import translation

    with translation.override("en"):
        again = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))
        wording = str(next(f.message for f in again if f.code == "looks_like_night_work"))

    assert wording.startswith("5 of 5 days with 3 h or more at night")
    assert "If the person holds the status" in wording
    assert "exceeds" not in wording


@pytest.mark.django_db
def test_one_night_shift_is_not_flagged(company, worker):
    """Working one night does not make somebody a night worker.

    A majority of one day is still a majority, which is how the first version of
    the reading turned a colleague's covered shift into a status with an
    eight-hour average attached to it.
    """
    with tenant_context(company.id):
        shift(company, worker, date(2026, 9, 1), NIGHT)
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "looks_like_night_work"] == []


@pytest.mark.django_db
def test_a_late_finish_is_not_night_work(company, worker):
    """Art. 36.1 counts hours inside the window, not shifts that touch it.

    A bar closing at 22:30 touches the night window every single day. Reading
    the status from "touches" instead of "three hours" would put the whole of
    hospitality under limits that do not apply to them.
    """
    with tenant_context(company.id):
        for offset in range(20):
            shift(
                company,
                worker,
                date(2026, 9, 1) + timedelta(days=offset),
                [{"start": "15:00", "end": "22:30"}],
            )
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "looks_like_night_work"] == []


@pytest.mark.django_db
def test_the_company_can_declare_the_status_the_roster_cannot_see(company, worker):
    """Somebody hired for nights is a night worker before any roster exists.

    The roster is a worse witness to "normally" than the contract, so an answer
    from the company wins --- and once it is there, the average stops being
    reported conditionally and becomes the limit it is.
    """
    with tenant_context(company.id):
        worker.night_worker = "YES"
        worker.save(update_fields=["night_worker"])
        # Nine-hour nights, every day: nine over fifteen days averages more than
        # the eight art. 36.1 allows.
        for offset in range(20):
            shift(
                company,
                worker,
                date(2026, 9, 1) + timedelta(days=offset),
                [{"start": "22:00", "end": "07:00"}],
            )
        from django.utils import translation

        with translation.override("en"):
            findings = review_roster(
                company=company, first=date(2026, 9, 1), last=date(2026, 9, 30)
            )

    average = [f for f in findings if f.code == "night_worker_average"]
    assert len(average) == 1
    assert average[0].basis == "Art. 36.1 ET"
    assert str(average[0].message).startswith("A night worker averaging")


@pytest.mark.django_db
def test_the_company_can_say_no_and_the_limits_stop(company, worker):
    """The override goes both ways, or it is not an override."""
    with tenant_context(company.id):
        worker.night_worker = "NO"
        worker.save(update_fields=["night_worker"])
        for offset in range(20):
            shift(
                company,
                worker,
                date(2026, 9, 1) + timedelta(days=offset),
                [{"start": "22:00", "end": "07:00"}],
            )
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "night_worker_average"] == []
    assert [f for f in findings if f.code == "looks_like_night_work"] == []


@pytest.mark.django_db
def test_more_than_two_weeks_on_nights(company, worker):
    """Art. 36.3 ET: three consecutive weeks on the night shift, unasked for."""
    with tenant_context(company.id):
        worker.rotating_shifts = True
        worker.save(update_fields=["rotating_shifts"])
        for offset in range(21):
            day = date(2026, 9, 7) + timedelta(days=offset)
            if day.weekday() < 5:
                shift(company, worker, day, NIGHT)
        findings = review_roster(company=company, first=date(2026, 9, 7), last=date(2026, 9, 27))

    weeks = [f for f in findings if f.code == "consecutive_night_weeks"]
    assert len(weeks) == 1
    assert weeks[0].basis == "Art. 36.3 ET"


@pytest.mark.django_db
def test_volunteering_lifts_the_two_week_cap(company, worker):
    """The article's own exception: more than two weeks needs the person to
    have asked, which is why it is a field and not an assumption."""
    with tenant_context(company.id):
        worker.rotating_shifts = True
        worker.voluntary_night_shift = True
        worker.save(update_fields=["rotating_shifts", "voluntary_night_shift"])
        for offset in range(21):
            day = date(2026, 9, 7) + timedelta(days=offset)
            if day.weekday() < 5:
                shift(company, worker, day, NIGHT)
        findings = review_roster(company=company, first=date(2026, 9, 7), last=date(2026, 9, 27))

    assert [f for f in findings if f.code == "consecutive_night_weeks"] == []


@pytest.mark.django_db
def test_a_shift_changeover_is_not_a_breach_of_the_daily_rest(company, worker):
    """The false positive this whole layer exists for.

    A rotating team coming off nights onto mornings cannot take twelve hours in
    between. Art. 19.a RD 1561/1995 lets the rest drop to seven on that day
    precisely so the rotation is possible, and the roster used to report every
    changeover in the country as a breach.
    """
    with tenant_context(company.id):
        worker.rotating_shifts = True
        worker.save(update_fields=["rotating_shifts"])
        # Off nights (ends 06:00 on the 2nd), onto afternoons (starts 14:00):
        # eight hours between them, under twelve and over seven.
        shift(company, worker, date(2026, 9, 1), [{"start": "22:00", "end": "06:00"}])
        shift(company, worker, date(2026, 9, 2), [{"start": "14:00", "end": "22:00"}])
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "short_daily_rest"] == []
    owed = [f for f in findings if f.code == "changeover_rest_owed"]
    assert len(owed) == 1
    assert owed[0].basis == "Art. 19.a RD 1561/1995"


@pytest.mark.django_db
def test_the_changeover_allowance_has_a_floor_of_its_own(company, worker):
    """Seven hours is a floor, not a licence. Below it, it is short again."""
    with tenant_context(company.id):
        worker.rotating_shifts = True
        worker.save(update_fields=["rotating_shifts"])
        shift(company, worker, date(2026, 9, 1), [{"start": "22:00", "end": "06:00"}])
        shift(company, worker, date(2026, 9, 2), [{"start": "11:00", "end": "19:00"}])
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "changeover_rest_owed"] == []
    assert [f for f in findings if f.code == "short_daily_rest"] != []


@pytest.mark.django_db
def test_the_allowance_needs_the_shift_to_have_actually_moved(company, worker):
    """Same hours two days running is not a rotation.

    Otherwise "rotating shifts" would become a blanket permission to roster
    eight hours of rest every night of the week, which is the opposite of what
    the article allows it for.
    """
    with tenant_context(company.id):
        worker.rotating_shifts = True
        worker.save(update_fields=["rotating_shifts"])
        # Two identical thirteen-hour days: the second starts eleven hours after
        # the first ended, which is short, and nothing rotated.
        shift(company, worker, date(2026, 9, 1), [{"start": "20:00", "end": "09:00"}])
        shift(company, worker, date(2026, 9, 2), [{"start": "20:00", "end": "09:00"}])
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    short = [f for f in findings if f.code == "short_daily_rest" and f.day == date(2026, 9, 2)]
    assert short != []


@pytest.mark.django_db
def test_the_night_window_is_the_companys_to_set(company, worker):
    """Another rule that was stored and never read."""
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.night_starts_at = time(2, 0)
        rules.night_ends_at = time(4, 0)
        rules.save(update_fields=["night_starts_at", "night_ends_at"])

        # 06:00-14:00 is nowhere near 02:00-04:00.
        for offset in range(5):
            shift(
                company,
                worker,
                date(2026, 9, 1) + timedelta(days=offset),
                [{"start": "06:00", "end": "14:00"}],
            )

        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert [f for f in findings if f.code == "looks_like_night_work"] == []
