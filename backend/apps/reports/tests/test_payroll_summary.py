"""The summary that goes out with the payslip (art. 6.1).

    «la empresa entregará, junto con el recibo de salarios, copia del resumen
    correspondiente al periodo fijado para el abono de las retribuciones.»

The period is the thing to get right. «El periodo fijado para el abono» is not
necessarily a calendar month, and a summary covering the wrong days next to a
payslip covering the right ones is worse than no summary: it invites the reader
to reconcile two documents that were never meant to match.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.reports.payroll import PayrollPeriod, PayrollSummary, period_containing
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


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


def worked(company, person, day, hours=8):
    with tenant_context(company.id):
        with freeze_time(f"{day} 06:00:00"):
            register_punch(employee=person, company=company)
        with freeze_time(f"{day} {6 + hours:02d}:00:00"):
            register_punch(employee=person, company=company)


# ------------------------------------------------------------- the period


def test_a_monthly_period_is_the_calendar_month():
    period = period_containing(date(2026, 9, 17), PayrollPeriod.MONTHLY)
    assert (period.first, period.last) == (date(2026, 9, 1), date(2026, 9, 30))


def test_february_ends_when_february_ends():
    """The kind of thing that works for eleven months a year."""
    assert period_containing(date(2026, 2, 10), PayrollPeriod.MONTHLY).last == date(2026, 2, 28)
    assert period_containing(date(2028, 2, 10), PayrollPeriod.MONTHLY).last == date(2028, 2, 29)


def test_a_fortnight_splits_the_month_at_the_fifteenth():
    """How companies that pay twice a month actually do it. Counting fourteen
    days from an arbitrary origin would drift, and the same day would land in
    different periods depending on when you asked."""
    first = period_containing(date(2026, 9, 3), PayrollPeriod.FORTNIGHTLY)
    second = period_containing(date(2026, 9, 20), PayrollPeriod.FORTNIGHTLY)

    assert (first.first, first.last) == (date(2026, 9, 1), date(2026, 9, 15))
    assert (second.first, second.last) == (date(2026, 9, 16), date(2026, 9, 30))


def test_a_week_runs_monday_to_sunday():
    period = period_containing(date(2026, 9, 3), PayrollPeriod.WEEKLY)  # a Thursday
    assert period.first.weekday() == 0
    assert period.last.weekday() == 6
    assert period.first == date(2026, 8, 31)


def test_the_boundary_days_belong_to_the_right_period():
    """The 15th and the 16th are the two that decide it."""
    assert period_containing(date(2026, 9, 15), PayrollPeriod.FORTNIGHTLY).last == date(2026, 9, 15)
    assert period_containing(date(2026, 9, 16), PayrollPeriod.FORTNIGHTLY).first == date(
        2026, 9, 16
    )


# ------------------------------------------------------------ the summary


@pytest.mark.django_db
def test_the_summary_covers_the_companys_pay_period(company):
    """Not a month because we assumed one: because the company said so."""
    with tenant_context(company.id):
        company.payroll_period = PayrollPeriod.FORTNIGHTLY
        company.save(update_fields=["payroll_period"])

    person = make(company, "ana@example.com")
    worked(company, person, "2026-09-03")
    worked(company, person, "2026-09-20")  # the other fortnight

    body = client_for(person).get("/api/reports/payroll-summary/", {"day": "2026-09-05"}).json()

    assert body["period"]["from"] == "2026-09-01"
    assert body["period"]["to"] == "2026-09-15"
    assert body["total_seconds"] == 8 * 3600  # only the day inside it


@pytest.mark.django_db
def test_a_worker_gets_their_own_and_not_a_colleagues(company):
    ana = make(company, "ana@example.com")
    beto = make(company, "beto@example.com")
    worked(company, beto, "2026-09-03")

    denied = client_for(ana).get(
        "/api/reports/payroll-summary/", {"employee": str(beto.id), "day": "2026-09-05"}
    )

    assert denied.status_code == 409


@pytest.mark.django_db
def test_a_manager_may_ask_for_somebody_elses(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    person = make(company, "ana@example.com")
    worked(company, person, "2026-09-03")

    body = (
        client_for(boss)
        .get("/api/reports/payroll-summary/", {"employee": str(person.id), "day": "2026-09-05"})
        .json()
    )

    assert body["employee"] == str(person.id)


@pytest.mark.django_db
def test_another_companys_person_is_not_found(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    elsewhere = Tenant.objects.create(name="Otra SL", tax_id="B22222222", time_zone="Europe/Madrid")
    stranger = make(elsewhere, "them@otra.com")

    response = client_for(boss).get("/api/reports/payroll-summary/", {"employee": str(stranger.id)})

    assert response.status_code == 409


# ------------------------------------------------------- generating in bulk


@pytest.mark.django_db
def test_generating_records_who_it_was_produced_for(company):
    """«Entregará» is an obligation the company has to be able to evidence.
    Without a record of it, the only answer to "did you hand it over" is
    somebody's memory."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    ana = make(company, "ana@example.com")
    worked(company, ana, "2026-09-03")

    response = client_for(boss).post(
        "/api/reports/payroll-summary/", {"day": "2026-09-05"}, format="json"
    )

    assert response.status_code == 201
    with tenant_context(company.id):
        summary = PayrollSummary.objects.get(employee=ana)
    assert summary.period_start == date(2026, 9, 1)
    assert summary.total_seconds == 8 * 3600
    assert summary.generated_by == boss
    assert summary.fingerprint


@pytest.mark.django_db
def test_people_with_no_hours_are_named_not_summarised(company):
    """A payslip summary with no hours behind it invites the question of
    whether the record failed or the person did not work. Better to say who
    they are and let payroll decide."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    ana = make(company, "ana@example.com")
    quiet = make(company, "quiet@example.com")
    worked(company, ana, "2026-09-03")

    body = (
        client_for(boss)
        .post("/api/reports/payroll-summary/", {"day": "2026-09-05"}, format="json")
        .json()
    )

    assert body["generated"] == 1
    assert any("qui" in name for name in body["without_hours"])
    with tenant_context(company.id):
        assert not PayrollSummary.objects.filter(employee=quiet).exists()


@pytest.mark.django_db
def test_generating_twice_updates_instead_of_duplicating(company):
    """The figures are reproducible, so regenerating is fine. Two rows for the
    same period would make "was it handed over" ambiguous, which is the one
    question this table exists to answer."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    ana = make(company, "ana@example.com")
    worked(company, ana, "2026-09-03")

    for _ in range(2):
        client_for(boss).post("/api/reports/payroll-summary/", {"day": "2026-09-05"}, format="json")

    with tenant_context(company.id):
        assert PayrollSummary.objects.filter(employee=ana).count() == 1


@pytest.mark.django_db
def test_a_worker_cannot_generate_them(company):
    person = make(company, "ana@example.com")

    response = client_for(person).post(
        "/api/reports/payroll-summary/", {"day": "2026-09-05"}, format="json"
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_the_summary_can_be_handed_over_as_a_file(company):
    """It accompanies a payslip, so it has to be something you can attach."""
    person = make(company, "ana@example.com")
    worked(company, person, "2026-09-03")

    for wanted, kind in [("pdf", "application/pdf"), ("csv", "text/csv")]:
        response = client_for(person).get(
            "/api/reports/payroll-summary/", {"day": "2026-09-05", "format": wanted}
        )
        assert response.status_code == 200
        assert kind in response.headers["Content-Type"]
        assert "attachment" in response.headers["Content-Disposition"]
        assert response.headers["X-Report-Hash"]
