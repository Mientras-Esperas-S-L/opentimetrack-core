"""Slicing a list by a range of days.

Two things worth testing and neither is "the filter filters".

**Where a day ends.** `?date_from=2026-08-01` means the first of August where
the company is. A punch at 00:30 Madrid time on the first is 22:30 UTC on the
31st of July, and a filter comparing against UTC would leave it out of the
range it belongs to. The clearest case is the Canary Islands, an hour behind
the mainland and inside the same country: the same instant falls on different
days for two companies of the same customer.

**That both ends are inclusive.** `date_to=2026-08-31` has to include the 31st.
Somebody typing two dates into a form means the days they typed, and a range
that silently drops its last day would understate a month's hours.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchSource, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

MADRID = ZoneInfo("Europe/Madrid")
CANARIES = ZoneInfo("Atlantic/Canary")


def company_in(zone_name):
    return Tenant.objects.create(
        name=f"ACME {zone_name}", tax_id=f"B{abs(hash(zone_name)) % 10**8:08d}", time_zone=zone_name
    )


def worker_of(company):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=f"ana@{company.tax_id}.test",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            role=Role.ADMIN,
        )


def punch_at(company, person, moment):
    with tenant_context(company.id):
        return Punch.objects.create(
            tenant=company,
            employee=person,
            timestamp=moment,
            punch_type=PunchType.IN,
            source=PunchSource.WEB,
        )


def ask(person, **params):
    client = APIClient()
    client.force_authenticate(person)
    return client.get("/api/punches/", params).json()


# ------------------------------------------------------------ the boundary


@pytest.mark.django_db
def test_the_day_starts_where_the_company_is():
    """Half past midnight in Madrid on the first of August. In UTC that is the
    31st of July, so a filter that did not convert would miss it."""
    company = company_in("Europe/Madrid")
    person = worker_of(company)
    punch_at(company, person, datetime(2026, 8, 1, 0, 30, tzinfo=MADRID))

    assert ask(person, date_from="2026-08-01")["count"] == 1
    assert ask(person, date_to="2026-07-31")["count"] == 0


@pytest.mark.django_db
def test_the_same_instant_falls_on_different_days_in_two_zones():
    """00:30 in Madrid is 23:30 the previous day in the Canaries. Both are
    Spain, both could be the same customer, and each has to be sliced by its
    own calendar."""
    moment = datetime(2026, 8, 1, 0, 30, tzinfo=MADRID)

    mainland = company_in("Europe/Madrid")
    islands = company_in("Atlantic/Canary")
    here, there = worker_of(mainland), worker_of(islands)
    punch_at(mainland, here, moment)
    punch_at(islands, there, moment)

    assert moment.astimezone(CANARIES).date().isoformat() == "2026-07-31"

    assert ask(here, date_from="2026-08-01")["count"] == 1
    assert ask(there, date_from="2026-08-01")["count"] == 0
    assert ask(there, date_from="2026-07-31", date_to="2026-07-31")["count"] == 1


# ------------------------------------------------------------- both ends in


@pytest.mark.django_db
def test_the_last_day_of_the_range_is_included():
    """The most likely way to get this wrong: comparing `lte` against midnight
    of the closing day, which keeps only a punch at exactly 00:00."""
    company = company_in("Europe/Madrid")
    person = worker_of(company)
    punch_at(company, person, datetime(2026, 8, 31, 23, 45, tzinfo=MADRID))

    assert ask(person, date_from="2026-08-01", date_to="2026-08-31")["count"] == 1


@pytest.mark.django_db
def test_the_first_day_of_the_range_is_included():
    company = company_in("Europe/Madrid")
    person = worker_of(company)
    punch_at(company, person, datetime(2026, 8, 1, 0, 0, tzinfo=MADRID))

    assert ask(person, date_from="2026-08-01", date_to="2026-08-31")["count"] == 1


@pytest.mark.django_db
def test_a_single_day_range_holds_that_day_and_no_other():
    company = company_in("Europe/Madrid")
    person = worker_of(company)
    for offset in (-1, 0, 1):
        punch_at(
            company, person, datetime(2026, 8, 15, 12, 0, tzinfo=MADRID) + timedelta(days=offset)
        )

    body = ask(person, date_from="2026-08-15", date_to="2026-08-15")
    assert body["count"] == 1
    assert body["results"][0]["timestamp"].startswith("2026-08-15")


# ------------------------------------------------- what the screens rely on


@pytest.mark.django_db
def test_the_count_reports_the_whole_range_not_the_page():
    """What makes a paginated screen honest. The list answers with fifty rows;
    `count` is the only thing that can tell somebody there are more, and every
    screen used to throw it away."""
    company = company_in("Europe/Madrid")
    person = worker_of(company)
    start = datetime(2026, 8, 1, 8, 0, tzinfo=MADRID)
    for offset in range(60):
        punch_at(company, person, start + timedelta(hours=offset * 5))

    body = ask(person, date_from="2026-08-01", date_to="2026-08-31")

    assert body["count"] == 60
    assert len(body["results"]) == 50
    assert body["next"] is not None


@pytest.mark.django_db
def test_no_range_still_returns_everything():
    """The filter is optional. Screens that do not offer dates --- the worker's
    own history, for one --- must not start getting an empty list."""
    company = company_in("Europe/Madrid")
    person = worker_of(company)
    punch_at(company, person, datetime(2020, 1, 1, 9, 0, tzinfo=MADRID))

    assert ask(person)["count"] == 1
