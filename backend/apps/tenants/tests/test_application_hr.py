"""Leave, roster and holidays through the application door.

What is fixed here: each answer needs its own permission, reading does not grant
asking, nothing crosses companies, and a request made from outside goes through the
same rules as one made here — including that it is not approved on the way in.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, AbsenceType, LeaveType
from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.tenants.holidays import PublicHoliday
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User, Workplace

PASSWORD = "a-sufficiently-long-password"
RANGE = {"from": "2026-09-14", "to": "2026-09-20"}


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
def rosa(company):
    with tenant_context(company.id):
        workplace = Workplace.objects.create(
            tenant=company, name="Cádiz", municipality="Cádiz", region="ES-AN"
        )
        return User.objects.create_user(
            email="rosa@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="EMP-0042",
            workplace=workplace,
        )


# ------------------------------------------------------------------ absences


@pytest.mark.django_db
def test_the_leave_that_explains_a_gap_comes_with_its_legal_type(company, rosa):
    with tenant_context(company.id):
        vacation = LeaveType.objects.create(
            tenant=company, code="VAC", name="Vacaciones", family="VACATION", amount=22
        )
        Absence.objects.create(
            tenant=company,
            employee=rosa,
            leave_type=vacation,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 16),
            end_date=date(2026, 9, 17),
            status=AbsenceStatus.APPROVED,
        )

    answer = credential(company, ApplicationScope.READ_ABSENCES).get("/api/app/absences/", RANGE)

    assert answer.status_code == 200
    (row,) = answer.json()["absences"]
    assert row["code"] == "VAC" and row["name"] == "Vacaciones"
    assert row["from"] == "2026-09-16" and row["to"] == "2026-09-17"
    assert row["employee_id"] == "EMP-0042" and row["status"] == "APPROVED"


@pytest.mark.django_db
def test_a_rejected_request_explains_nothing_so_it_does_not_come(company, rosa):
    with tenant_context(company.id):
        Absence.objects.create(
            tenant=company,
            employee=rosa,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 16),
            end_date=date(2026, 9, 16),
            status=AbsenceStatus.REJECTED,
        )

    answer = credential(company, ApplicationScope.READ_ABSENCES).get("/api/app/absences/", RANGE)
    assert answer.json()["absences"] == []


@pytest.mark.django_db
def test_asking_for_leave_is_a_different_permission_from_reading_it(company, rosa):
    only_reads = credential(company, ApplicationScope.READ_ABSENCES)
    answer = only_reads.post(
        "/api/app/absences/",
        {
            "employee_ref": "EMP-0042",
            "code": "VAC",
            "start_date": "2026-09-16",
            "end_date": "2026-09-16",
        },
        format="json",
    )
    assert answer.status_code == 403, "pintar un calendario no es poder pedir vacaciones"


@pytest.mark.django_db
def test_a_request_from_outside_arrives_pending_not_approved(company, rosa):
    with tenant_context(company.id):
        LeaveType.objects.create(
            tenant=company, code="VAC", name="Vacaciones", family="VACATION", amount=22
        )

    answer = credential(company, ApplicationScope.WRITE_ABSENCES).post(
        "/api/app/absences/",
        {
            "employee_ref": "EMP-0042",
            "code": "VAC",
            "start_date": "2026-09-16",
            "end_date": "2026-09-17",
            "reason": "Lo pidió por la aplicación de gestión",
        },
        format="json",
    )

    assert answer.status_code == 201
    assert answer.json()["status"] == "PENDING", "pedir no es conceder"
    with tenant_context(company.id):
        assert Absence.objects.filter(employee=rosa, status=AbsenceStatus.PENDING).exists()


@pytest.mark.django_db
def test_a_code_this_company_does_not_have_is_refused(company, rosa):
    answer = credential(company, ApplicationScope.WRITE_ABSENCES).post(
        "/api/app/absences/",
        {
            "employee_ref": "EMP-0042",
            "code": "INVENTADO",
            "start_date": "2026-09-16",
            "end_date": "2026-09-16",
        },
        format="json",
    )
    assert answer.json()["error"]["code"] == "leave_type_unknown"


# -------------------------------------------------------------------- roster


@pytest.mark.django_db
def test_the_roster_says_what_was_expected(company, rosa):
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=rosa,
            day=date(2026, 9, 15),
            segments=[{"start": "08:00", "end": "16:00"}],
        )

    answer = credential(company, ApplicationScope.READ_ROSTER).get("/api/app/roster/", RANGE)

    assert answer.status_code == 200
    (row,) = answer.json()["shifts"]
    assert row["day"] == "2026-09-15" and row["minutes"] == 480
    assert row["segments"] == [{"start": "08:00", "end": "16:00"}]


@pytest.mark.django_db
def test_the_roster_needs_its_own_permission(company, rosa):
    assert (
        credential(company, ApplicationScope.READ_ABSENCES)
        .get("/api/app/roster/", RANGE)
        .status_code
        == 403
    )


# ------------------------------------------------------------------ calendar


@pytest.mark.django_db
def test_a_local_holiday_says_which_workplace_it_belongs_to(company, rosa):
    with tenant_context(company.id):
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 9, 15), name="Fiesta nacional", workplace=None
        )
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 9, 16), name="Fiesta local", workplace=rosa.workplace
        )

    answer = credential(company, ApplicationScope.READ_CALENDAR).get("/api/app/calendar/", RANGE)

    assert answer.status_code == 200
    holidays = {row["name"]: row["workplace"] for row in answer.json()["holidays"]}
    assert holidays["Fiesta nacional"] is None, "null es toda la empresa, no un centro cualquiera"
    assert holidays["Fiesta local"] == "Cádiz"


@pytest.mark.django_db
def test_the_calendar_needs_its_own_permission(company):
    assert (
        credential(company, ApplicationScope.READ_ROSTER)
        .get("/api/app/calendar/", RANGE)
        .status_code
        == 403
    )


# ----------------------------------------------------------------- the limits


@pytest.mark.django_db
def test_the_three_are_bounded_the_same_way(company):
    client = credential(
        company,
        ApplicationScope.READ_ABSENCES,
        ApplicationScope.READ_ROSTER,
        ApplicationScope.READ_CALENDAR,
    )
    for url in ("/api/app/absences/", "/api/app/roster/", "/api/app/calendar/"):
        assert client.get(url, {"from": "2026-01-01", "to": "2026-12-31"}).status_code == 400
        assert client.get(url, {"from": "2026-09-14"}).status_code == 400


@pytest.mark.django_db
def test_another_company_sees_nobody_here(company, rosa):
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=rosa,
            day=date(2026, 9, 15),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
    other = Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")
    intruder = credential(other, ApplicationScope.READ_ROSTER, ApplicationScope.READ_ABSENCES)

    assert intruder.get("/api/app/roster/", RANGE).json()["shifts"] == []
    named = intruder.get("/api/app/absences/", {**RANGE, "employee_ref": "EMP-0042"})
    assert named.json()["error"]["code"] == "employee_not_found"


# ------------------------------------------------------------- the catalogue


@pytest.mark.django_db
def test_the_catalogue_gives_the_codes_that_requesting_leave_expects(company):
    with tenant_context(company.id):
        LeaveType.objects.create(
            tenant=company,
            code="es.vacation",
            name="Vacaciones",
            family="VACATION",
            basis="art. 38 ET",
        )
    answer = credential(company, ApplicationScope.READ_ABSENCES).get("/api/app/leave-types/")

    assert answer.status_code == 200
    kinds = answer.json()["leave_types"]
    esperado = {
        "code": "es.vacation",
        "name": "Vacaciones",
        "family": "VACATION",
        "basis": "art. 38 ET",
    }
    assert esperado in kinds


@pytest.mark.django_db
def test_a_type_the_company_invented_has_no_code_so_it_is_not_offered(company):
    """Sin código no hay nada que pedir desde fuera, y ofrecerlo sería ofrecer un fallo."""
    with tenant_context(company.id):
        LeaveType.objects.create(tenant=company, code="", name="Día de la empresa")
    answer = credential(company, ApplicationScope.READ_ABSENCES).get("/api/app/leave-types/")

    assert [kind["name"] for kind in answer.json()["leave_types"]] == []


@pytest.mark.django_db
def test_the_catalogue_needs_permission_to_read_leave(company):
    answer = credential(company, ApplicationScope.READ_ROSTER).get("/api/app/leave-types/")

    assert answer.status_code == 403


@pytest.mark.django_db
def test_another_company_does_not_see_this_catalogue(company):
    with tenant_context(company.id):
        LeaveType.objects.create(tenant=company, code="es.vacation", name="Vacaciones")
    other = Tenant.objects.create(name="Globex", tax_id="B33333333", time_zone="Europe/Madrid")

    intruder = credential(other, ApplicationScope.READ_ABSENCES).get("/api/app/leave-types/")

    assert intruder.json()["leave_types"] == []
