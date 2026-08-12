"""The floors that protect workers under eighteen.

These are the only rules in the system that are **not configurable**, and that
is the decision worth defending. Everything else is a figure the company sets,
because a collective agreement can improve it and RD 1561/1995 modifies several
outright. None of these can be lowered by anybody, so offering a setting would
be offering one whose only use is breaking the law.

    Art. 6.2 ET   no night work at all
    Art. 6.3 ET   no overtime at all
    Art. 34.3 ET  eight hours a day, with no "unless the agreement says"
    Art. 34.4 ET  thirty minutes' break, from four and a half hours
    Art. 37.1 ET  two uninterrupted days of weekly rest

The other thing under test is that age is read **per day**. Somebody turns
eighteen and the protections stop from that date; evaluating the age once would
either apply them a month too long or drop them a month too early.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import HoursNature, OvertimeSettlement
from apps.punches.services import register_punch
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

MORNING = [{"start": "08:00", "end": "16:00"}]  # 8 h, at the limit
LONG_DAY = [{"start": "08:00", "end": "17:00"}]  # 9 h, over it
SHORT_DAY = [{"start": "09:00", "end": "13:00"}]  # 4 h, under the break threshold
FIVE_HOURS = [{"start": "09:00", "end": "14:00"}]  # over four and a half
NIGHT = [{"start": "22:00", "end": "06:00"}]


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def person_born(company, born, email="joven@example.com"):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email,
            password=PASSWORD,
            tenant=company,
            first_name="Joven",
            date_of_birth=born,
        )


def shift(company, person, day, segments=MORNING):
    with tenant_context(company.id):
        return Shift.objects.create(tenant=company, employee=person, day=day, segments=segments)


def findings_for(company, first=date(2026, 9, 1), last=date(2026, 9, 30)):
    with tenant_context(company.id):
        return review_roster(company=company, first=first, last=last)


# ------------------------------------------------------ age, read per day


@pytest.mark.django_db
def test_age_is_read_on_the_day_not_today(company):
    """A roster drawn for last month has to be read with the age they had
    then. Asking "are they a minor" without a date silently rewrites the past
    every birthday."""
    person = person_born(company, date(2009, 6, 15))  # turns 18 on 15/06/2027

    assert person.is_minor_on(date(2027, 6, 14))
    assert not person.is_minor_on(date(2027, 6, 15))
    assert not person.is_minor_on(date(2028, 1, 1))


@pytest.mark.django_db
def test_without_a_date_of_birth_nothing_is_assumed(company):
    """`age_is_known` exists so a caller can tell "adult" from "we do not
    know". The second means the protections are not being applied, which
    somebody should be told rather than left to assume."""
    unknown = person_born(company, None)

    assert not unknown.age_is_known
    assert not unknown.is_minor_on(date(2026, 9, 1))


@pytest.mark.django_db
def test_the_protections_stop_the_day_they_turn_eighteen(company):
    """Not the month, not the year: the day."""
    person = person_born(company, date(2008, 9, 10))  # eighteen on 10/09/2026
    shift(company, person, date(2026, 9, 9), LONG_DAY)  # still a minor
    shift(company, person, date(2026, 9, 10), LONG_DAY)  # an adult now

    over = [f for f in findings_for(company) if f.code == "minor_over_daily_limit"]

    assert [f.day for f in over] == [date(2026, 9, 9)]


# ------------------------------------------------------- art. 34.3, eight hours


@pytest.mark.django_db
def test_nine_hours_is_over_the_limit_for_a_minor(company):
    person = person_born(company, date(2009, 1, 1))
    shift(company, person, date(2026, 9, 1), LONG_DAY)

    over = [f for f in findings_for(company) if f.code == "minor_over_daily_limit"]

    assert len(over) == 1
    assert over[0].basis == "Art. 34.3 ET"


@pytest.mark.django_db
def test_exactly_eight_hours_is_not(company):
    """The article says "no more than eight", so eight is allowed. A warning
    here would fire on every ordinary full day and be ignored within a week."""
    person = person_born(company, date(2009, 1, 1))
    shift(company, person, date(2026, 9, 1), MORNING)

    assert [f for f in findings_for(company) if f.code == "minor_over_daily_limit"] == []


@pytest.mark.django_db
def test_an_adult_may_work_nine_hours(company):
    """Art. 34.3 allows adults nine, and more if the agreement distributes it
    differently. The whole point of reading the age is not applying the minor's
    floor to everybody."""
    adult = person_born(company, date(1990, 1, 1))
    shift(company, adult, date(2026, 9, 1), LONG_DAY)

    assert [f for f in findings_for(company) if f.code == "minor_over_daily_limit"] == []


# --------------------------------------------- art. 34.4, thirty from four and a half


@pytest.mark.django_db
def test_a_minor_is_owed_a_break_from_four_and_a_half_hours(company):
    """Where an adult would not be: their threshold is six."""
    minor = person_born(company, date(2009, 1, 1))
    adult = person_born(company, date(1990, 1, 1), "adulto@example.com")
    shift(company, minor, date(2026, 9, 1), FIVE_HOURS)
    shift(company, adult, date(2026, 9, 1), FIVE_HOURS)

    findings = findings_for(company)
    minor_breaks = [f for f in findings if f.code == "minor_break_owed"]
    adult_breaks = [f for f in findings if f.code == "break_owed"]

    assert len(minor_breaks) == 1
    assert minor_breaks[0].basis == "Art. 34.4 ET"
    assert adult_breaks == []  # five hours does not exceed six


@pytest.mark.django_db
def test_a_short_day_owes_nothing(company):
    person = person_born(company, date(2009, 1, 1))
    shift(company, person, date(2026, 9, 1), SHORT_DAY)

    assert [f for f in findings_for(company) if f.code == "minor_break_owed"] == []


@pytest.mark.django_db
def test_a_split_day_is_not_continuous(company):
    """The article says «jornada diaria continuada». A split day already has
    its break."""
    person = person_born(company, date(2009, 1, 1))
    shift(
        company,
        person,
        date(2026, 9, 1),
        [{"start": "09:00", "end": "13:00"}, {"start": "15:00", "end": "18:00"}],
    )

    assert [f for f in findings_for(company) if f.code == "minor_break_owed"] == []


# ------------------------------------------------------- art. 6.2, no night work


@pytest.mark.django_db
def test_a_night_shift_for_a_minor_is_reported_as_forbidden(company):
    """Not as a threshold. Art. 6.2 admits no permitted amount, which is why
    this is the only wording in the module that says so."""
    person = person_born(company, date(2009, 1, 1))
    shift(company, person, date(2026, 9, 1), NIGHT)

    night = [f for f in findings_for(company) if f.code == "minor_night_work"]

    assert len(night) == 1
    assert night[0].basis == "Art. 6.2 ET"


@pytest.mark.django_db
def test_one_night_is_enough_to_report_it(company):
    """For an adult it takes three before the roster says anything, because
    what it flags there is a status. Here a single one is already unlawful."""
    person = person_born(company, date(2009, 1, 1))
    shift(company, person, date(2026, 9, 1), NIGHT)

    findings = findings_for(company)
    assert any(f.code == "minor_night_work" for f in findings)
    assert not any(f.code == "looks_like_night_work" for f in findings)


# ------------------------------------------------------ art. 6.3, no overtime


@pytest.mark.django_db
def test_a_minor_cannot_be_given_overtime(company):
    person = person_born(company, date(2009, 1, 1))

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        register_punch(
            employee=person,
            company=company,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
        )

    assert caught.value.code == "overtime_forbidden_for_minors"


@pytest.mark.django_db
def test_not_even_for_force_majeure(company):
    """Art. 12.4.c lets part-time work do the hours of art. 35.3. Art. 6.3 has
    no such escape: «Se prohíbe realizar horas extraordinarias a los menores de
    dieciocho años», full stop."""
    person = person_born(company, date(2009, 1, 1))

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        register_punch(
            employee=person,
            company=company,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
            force_majeure=True,
        )

    assert caught.value.code == "overtime_forbidden_for_minors"


@pytest.mark.django_db
def test_an_ordinary_punch_is_never_refused(company):
    """The record has to reflect what happened. Refusing to record a minor's
    ordinary hours would not undo the work: it would only remove the proof that
    they did it, which harms the person the article protects."""
    person = person_born(company, date(2009, 1, 1))

    with tenant_context(company.id):
        event = register_punch(employee=person, company=company)

    assert event.pk is not None


# -------------------------------------------------- art. 37.1, two days' rest


@pytest.mark.django_db
def test_a_minor_needs_two_uninterrupted_days(company):
    """Where a day and a half would do for an adult. Twelve days on with a
    36-hour gap satisfies the adult floor and not theirs."""
    minor = person_born(company, date(2009, 1, 1))

    with tenant_context(company.id):
        # Monday to Saturday, then Monday again: 36 h between Saturday 16:00
        # and Monday 08:00 minus... enough for an adult, short for a minor.
        for offset in list(range(6)) + list(range(7, 13)):
            Shift.objects.create(
                tenant=company,
                employee=minor,
                day=date(2026, 9, 7) + timedelta(days=offset),
                segments=MORNING,
            )

        findings = review_roster(company=company, first=date(2026, 9, 7), last=date(2026, 9, 30))

    assert any(f.code == "short_weekly_rest" for f in findings)
