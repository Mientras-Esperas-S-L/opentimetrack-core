"""Attendance over a range, for the application that paints a calendar.

What makes it usable from a connector: every day of the range is there even when
nothing happened, each day says whether the roster expected work, which holiday it
was and which absence explains the gap, the range is bounded, it pages by person,
and nothing crosses companies.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.shifts.models import Shift
from apps.tenants import attendance_api
from apps.tenants.holidays import PublicHoliday
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User, Workplace

PASSWORD = "a-sufficiently-long-password"
URL = "/api/app/attendance/range/"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def credential(company, *scopes):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="Geosian", scopes=[str(scope) for scope in scopes]
        )
        _credential, secret = ApplicationCredential.issue(application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    return client


@pytest.fixture
def connector(company):
    return credential(company, ApplicationScope.READ_ATTENDANCE)


@pytest.fixture
def rosa(company):
    """Two worked days, a roster on three, holidays, and an approved absence."""
    with tenant_context(company.id):
        workplace = Workplace.objects.create(
            tenant=company, name="Cádiz", municipality="Cádiz", region="ES-AN"
        )
        rosa = User.objects.create_user(
            email="rosa@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="EMP-0042",
            first_name="Rosa",
            last_name="Campos",
            workplace=workplace,
        )
        # Tuesday 15th: 08:00 to 16:00 Madrid time (06:00Z to 14:00Z in September).
        with freeze_time("2026-09-15 06:00:00"):
            register_punch(employee=rosa, company=company)
        with freeze_time("2026-09-15 14:00:00"):
            register_punch(employee=rosa, company=company)
        # Wednesday 16th: clocked in, still working when asked.
        with freeze_time("2026-09-16 06:00:00"):
            register_punch(employee=rosa, company=company)
        for day in (date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17)):
            Shift.objects.create(
                tenant=company,
                employee=rosa,
                day=day,
                segments=[{"start": "08:00", "end": "16:00"}],
            )
        Absence.objects.create(
            tenant=company,
            employee=rosa,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            status=AbsenceStatus.APPROVED,
        )
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 9, 18), name="Fiesta local", workplace=workplace
        )
    return rosa


@pytest.mark.django_db
@freeze_time("2026-09-16 10:00:00")
def test_every_day_of_the_range_is_there_with_what_explains_it(connector, rosa):
    answer = connector.get(
        URL, {"from": "2026-09-15", "to": "2026-09-18", "employee_ref": "EMP-0042"}
    )

    assert answer.status_code == 200
    body = answer.json()
    assert body["from"] == "2026-09-15" and body["to"] == "2026-09-18"
    assert body["count"] == 1 and body["has_more"] is False
    (person,) = body["people"]
    assert person["employee_id"] == "EMP-0042" and person["name"] == "Rosa Campos"
    days = {d["day"]: d for d in person["days"]}
    assert list(days) == ["2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]

    worked = days["2026-09-15"]
    assert worked["state"] == "OFF" and worked["worked_seconds"] == 8 * 3600
    assert worked["scheduled"] is True
    assert worked["holiday"] is None
    assert worked["absence"] is None
    # Timestamps travel in UTC with their offset; the *day* is the local one.
    assert (
        worked["segments"][0]["in"] == "2026-09-15T06:00:00+00:00" and worked["segments"][0]["out"]
    )

    still = days["2026-09-16"]
    assert still["state"] == "WORKING" and still["worked_seconds"] == 4 * 3600
    assert still["segments"][0]["out"] is None

    away = days["2026-09-17"]
    assert away["state"] == "NOT_STARTED" and away["scheduled"] is True
    # The name arrives translated for the caller's language; the code is the contract.
    assert away["absence"]["code"] == "VACATION" and away["absence"]["name"]
    assert away["absence"]["status"] == "APPROVED" and away["absence"]["partial"] is False

    fiesta = days["2026-09-18"]
    assert fiesta["holiday"] == "Fiesta local" and fiesta["scheduled"] is False


@pytest.mark.django_db
def test_no_capture_metadata_leaves_the_company(connector, rosa):
    answer = connector.get(
        URL, {"from": "2026-09-15", "to": "2026-09-16", "employee_ref": "EMP-0042"}
    )
    text = str(answer.json())
    assert "ip_address" not in text and "device" not in text and "user_agent" not in text


@pytest.mark.django_db
def test_somebody_without_a_roster_says_unknown_not_off(connector, company):
    with tenant_context(company.id):
        User.objects.create_user(
            email="p@acme.example", password=PASSWORD, tenant=company, employee_id="EMP-1"
        )
    answer = connector.get(URL, {"from": "2026-09-15", "to": "2026-09-15", "employee_ref": "EMP-1"})
    assert answer.json()["people"][0]["days"][0]["scheduled"] is None


@pytest.mark.django_db
def test_somebody_who_left_still_has_their_calendar(connector, company):
    with tenant_context(company.id):
        gone = User.objects.create_user(
            email="g@acme.example", password=PASSWORD, tenant=company, employee_id="EMP-9"
        )
        with freeze_time("2026-09-15 06:00:00"):
            register_punch(employee=gone, company=company)
        with freeze_time("2026-09-15 10:00:00"):
            register_punch(employee=gone, company=company)
        gone.is_active = False
        gone.save(update_fields=["is_active"])

    answer = connector.get(URL, {"from": "2026-09-15", "to": "2026-09-15", "employee_ref": "EMP-9"})
    assert answer.status_code == 200
    person = answer.json()["people"][0]
    assert person["is_active"] is False and person["days"][0]["worked_seconds"] == 4 * 3600


@pytest.mark.django_db
def test_the_whole_workforce_pages_by_person(connector, company, monkeypatch):
    monkeypatch.setattr(attendance_api, "PEOPLE_PER_PAGE", 2)
    with tenant_context(company.id):
        for i in range(3):
            User.objects.create_user(
                email=f"p{i}@acme.example", password=PASSWORD, tenant=company, last_name=f"P{i}"
            )
    first = connector.get(URL, {"from": "2026-09-15", "to": "2026-09-15"}).json()
    second = connector.get(URL, {"from": "2026-09-15", "to": "2026-09-15", "page": 2}).json()
    assert first["count"] == 3 and len(first["people"]) == 2 and first["has_more"] is True
    assert second["page"] == 2 and len(second["people"]) == 1 and second["has_more"] is False
    assert len(first["people"][0]["days"]) == 1


@pytest.mark.django_db
def test_the_range_is_bounded_and_the_dates_are_checked(connector):
    assert connector.get(URL, {"to": "2026-09-15"}).status_code == 400
    assert connector.get(URL, {"from": "2026-09-15"}).status_code == 400
    assert connector.get(URL, {"from": "2026-09-15", "to": "2026-09-14"}).status_code == 400
    too_long = connector.get(URL, {"from": "2026-01-01", "to": "2026-03-31"})
    assert too_long.status_code == 400
    assert "62" in str(too_long.json())
    assert connector.get(URL, {"from": "2026-01-01", "to": "2026-03-03"}).status_code == 200


@pytest.mark.django_db
def test_the_range_needs_read_attendance(company):
    client = credential(company, ApplicationScope.READ_PEOPLE)
    assert client.get(URL, {"from": "2026-09-15", "to": "2026-09-15"}).status_code == 403


@pytest.mark.django_db
def test_another_company_cannot_see_her(rosa):
    other = Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")
    client = credential(other, ApplicationScope.READ_ATTENDANCE)
    answer = client.get(URL, {"from": "2026-09-15", "to": "2026-09-15", "employee_ref": "EMP-0042"})
    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "employee_not_found"
    everybody = client.get(URL, {"from": "2026-09-15", "to": "2026-09-15"}).json()
    assert everybody["count"] == 0
