"""The team calendar window.

One rule carries the whole thing: **overlap, not containment**. Leave running
from June into July has to appear when looking at July. Filtering on
`start_date` alone drops it, and that off-by-one stays invisible until somebody
books over a colleague's holiday the calendar never showed.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import approve_absence, request_absence
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
JULY = {"from": "2026-07-01", "to": "2026-07-31"}


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def make(company, email, role=Role.EMPLOYEE):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email, password=PASSWORD, tenant=company, first_name=email[:3], role=role
        )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def leave(company, person, start, end, approver=None, kind=AbsenceType.VACATION):
    with tenant_context(company.id):
        absence = request_absence(
            employee=person,
            company=company,
            absence_type=kind,
            start_date=start,
            end_date=end,
        )
        if approver:
            approve_absence(absence, resolved_by=approver)
        return absence


@pytest.mark.django_db
def test_leave_starting_before_the_window_still_shows(company):
    """The one that matters. June 25 to July 5, looking at July."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    leave(company, worker, date(2026, 6, 25), date(2026, 7, 5), boss)

    rows = client_for(boss).get("/api/absences/calendar/", JULY).json()

    assert len(rows) == 1
    assert rows[0]["start_date"] == "2026-06-25"


@pytest.mark.django_db
def test_leave_ending_after_the_window_still_shows(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    leave(company, worker, date(2026, 7, 28), date(2026, 8, 10), boss)

    rows = client_for(boss).get("/api/absences/calendar/", JULY).json()

    assert len(rows) == 1


@pytest.mark.django_db
def test_leave_spanning_the_whole_window_shows(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    leave(company, worker, date(2026, 6, 1), date(2026, 9, 1), boss)

    assert len(client_for(boss).get("/api/absences/calendar/", JULY).json()) == 1


@pytest.mark.django_db
def test_leave_entirely_outside_the_window_does_not(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    leave(company, worker, date(2026, 9, 1), date(2026, 9, 10), boss)

    assert client_for(boss).get("/api/absences/calendar/", JULY).json() == []


@pytest.mark.django_db
def test_pending_requests_come_too(company):
    """Deciding whether to approve August needs to show what is already asked
    for, not only what is settled."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    leave(company, worker, date(2026, 7, 10), date(2026, 7, 14))  # not approved

    rows = client_for(boss).get("/api/absences/calendar/", JULY).json()

    assert len(rows) == 1
    assert rows[0]["status"] == "PENDING"


@pytest.mark.django_db
def test_rejected_requests_do_not(company):
    """They are kept as history, but drawing them on a calendar would show days
    off that nobody is taking."""
    from apps.absences.services import reject_absence

    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    absence = leave(company, worker, date(2026, 7, 10), date(2026, 7, 14))
    with tenant_context(company.id):
        reject_absence(absence, resolved_by=boss)

    assert client_for(boss).get("/api/absences/calendar/", JULY).json() == []


@pytest.mark.django_db
def test_a_worker_sees_only_their_own(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    ana = make(company, "ana@example.com")
    beto = make(company, "beto@example.com")
    leave(company, ana, date(2026, 7, 1), date(2026, 7, 5), boss)
    leave(company, beto, date(2026, 7, 6), date(2026, 7, 10), boss, AbsenceType.SICK_LEAVE)

    mine = client_for(ana).get("/api/absences/calendar/", JULY).json()
    theirs = client_for(boss).get("/api/absences/calendar/", JULY).json()

    assert len(mine) == 1
    assert mine[0]["employee"] == str(ana.id)
    assert len(theirs) == 2


@pytest.mark.django_db
def test_a_missing_or_broken_window_is_refused(company):
    boss = make(company, "boss@example.com", Role.MANAGER)

    assert client_for(boss).get("/api/absences/calendar/").status_code == 409
    assert (
        client_for(boss).get("/api/absences/calendar/", {"from": "ayer", "to": "hoy"}).status_code
        == 409
    )
