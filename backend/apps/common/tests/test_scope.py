"""Who reads whose record, inside one company.

The isolation sweep next door asks whether one company can reach another's
data. This asks the question a rung down, which nothing was asking: whether the
person who runs the gardening crew can read the sick leave of somebody in the
office. They could, everywhere, and departments were only a label to filter by.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.common.scope import unassigned_managers, visible_people
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def world(company):
    with tenant_context(company.id):
        garden = Department.objects.create(tenant=company, name="Jardinería")
        office = Department.objects.create(tenant=company, name="Oficina")

        def person(email, first, role=Role.EMPLOYEE, department=None):
            return User.objects.create_user(
                email=email,
                password=PASSWORD,
                tenant=company,
                first_name=first,
                role=role,
                department=department,
            )

        made = {
            "garden": garden,
            "office": office,
            "gardener": person("jardin@example.com", "Marta", department=garden),
            "clerk": person("oficina@example.com", "Nuria", department=office),
            # Runs the gardening crew from an office desk: the department they
            # belong to and the one they answer for are different on purpose.
            "boss": person("jefa@example.com", "Luisa", Role.MANAGER, department=office),
            "admin": person("admin@example.com", "Ana", Role.ADMIN, department=office),
        }
        garden.managers.add(made["boss"])
        yield made


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ------------------------------------------------------------------- the scope


@pytest.mark.django_db
def test_a_manager_reads_the_departments_they_answer_for(company, world):
    scope = visible_people(world["boss"])

    assert set(scope.values_list("first_name", flat=True)) == {"Marta", "Luisa"}


@pytest.mark.django_db
def test_not_the_department_they_belong_to(company, world):
    """Luisa sits in the office and runs the garden. Reading the scope off
    membership would hand her the office's records instead of hers."""
    scope = visible_people(world["boss"])

    assert "Nuria" not in set(scope.values_list("first_name", flat=True))


@pytest.mark.django_db
def test_an_administrator_reads_everybody(company, world):
    assert visible_people(world["admin"]) is None


@pytest.mark.django_db
def test_a_worker_reads_only_themselves(company, world):
    scope = visible_people(world["gardener"])

    assert list(scope.values_list("first_name", flat=True)) == ["Marta"]


@pytest.mark.django_db
def test_a_manager_in_charge_of_nothing_reads_everybody_while_nobody_is(company, world):
    """The one concession in this design, and it is deliberate.

    A company that signs up today, adds ten people and marks one as manager has
    no departments. Narrowing that manager to nothing would show them an empty
    product on day one, and the fix people find for a default that looks broken
    is to turn it off.

    The name of this test used to stop at *reads everybody*, and it passed for a
    narrower reason than it claimed: removing `boss` here leaves **nobody** in
    the company in charge of anything, which is the day-one state. Once somebody
    else runs a department the concession no longer applies --- see
    `test_reasignar_un_departamento_no_amplia_a_nadie`.
    """
    with tenant_context(company.id):
        world["garden"].managers.remove(world["boss"])
        assert not Department.objects.filter(tenant=company, managers__isnull=False).exists(), (
            "the concession is about a company where nobody is in charge yet"
        )

    assert visible_people(world["boss"]) is None


@pytest.mark.django_db
def test_and_the_settings_screen_says_so(company, world):
    """A trade nobody can see is not a trade, it is a hole."""
    with tenant_context(company.id):
        world["garden"].managers.remove(world["boss"])

        assert [p.first_name for p in unassigned_managers(company)] == ["Luisa"]


@pytest.mark.django_db
def test_the_company_can_turn_scoping_off(company, world):
    """In a firm of twelve, departments are an overhead nobody asked for."""
    company.managers_see_whole_company = True
    company.save(update_fields=["managers_see_whole_company"])

    assert visible_people(world["boss"]) is None
    assert list(unassigned_managers(company)) == []


# --------------------------------------------------------------- through HTTP


@pytest.mark.django_db
def test_a_manager_cannot_list_a_colleagues_leave(company, world):
    """The one that matters: leave is where illness shows."""
    with tenant_context(company.id):
        Absence.objects.create(
            tenant=company,
            employee=world["clerk"],
            absence_type=AbsenceType.SICK_LEAVE,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
            status=AbsenceStatus.APPROVED,
        )

    rows = client_for(world["boss"]).get("/api/absences/").json()["results"]

    assert [r["employee_name"] for r in rows] == []


@pytest.mark.django_db
def test_nor_reach_it_by_id(company, world):
    """The object check has to agree with the list check, or a row hidden from
    the list is still readable by anybody who knows its id."""
    with tenant_context(company.id):
        hidden = Absence.objects.create(
            tenant=company,
            employee=world["clerk"],
            absence_type=AbsenceType.SICK_LEAVE,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
        )

    response = client_for(world["boss"]).get(f"/api/absences/{hidden.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_nor_ask_for_their_balance(company, world):
    response = client_for(world["boss"]).get(
        "/api/absences/balance/", {"employee": str(world["clerk"].id)}
    )

    assert response.status_code >= 400


@pytest.mark.django_db
def test_nor_export_their_record(company, world):
    response = client_for(world["boss"]).get(
        "/api/reports/working-time/", {"employee": str(world["clerk"].id)}
    )

    assert response.status_code >= 400


@pytest.mark.django_db
def test_but_can_do_all_of_that_for_their_own_crew(company, world):
    """The check is not "refuse everything": a manager who cannot resolve for
    the people they answer for is a manager who cannot work."""
    with tenant_context(company.id):
        Absence.objects.create(
            tenant=company,
            employee=world["gardener"],
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
        )

    client = client_for(world["boss"])
    rows = client.get("/api/absences/").json()["results"]

    assert [r["employee_name"] for r in rows] == ["Marta"]
    assert (
        client.get("/api/absences/balance/", {"employee": str(world["gardener"].id)}).status_code
        == 200
    )


@pytest.mark.django_db
def test_the_people_list_is_scoped_too(company, world):
    rows = client_for(world["boss"]).get("/api/employees/").json()["results"]

    assert sorted(r["first_name"] for r in rows) == ["Luisa", "Marta"]


@pytest.mark.django_db
def test_the_pending_queue_holds_only_what_they_can_resolve(company, world):
    """Showing a request they cannot decide is offering work that fails on the
    second click."""
    with tenant_context(company.id):
        for who in ("clerk", "gardener"):
            Absence.objects.create(
                tenant=company,
                employee=world[who],
                absence_type=AbsenceType.VACATION,
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 5),
            )

    queue = client_for(world["boss"]).get("/api/absences/pending/").json()

    assert [row["employee_name"] for row in queue] == ["Marta"]


@pytest.mark.django_db
def test_the_overview_counts_only_their_own(company, world):
    """A headcount of the whole company next to a queue holding one department
    is two numbers that do not belong on the same screen."""
    body = client_for(world["boss"]).get("/api/overview/").json()

    assert body["scope"] == "departments"
    assert body["headcount"] == 2


@pytest.mark.django_db
def test_only_a_manager_may_be_put_in_charge(company, world):
    """Putting an employee in charge grants nothing --- the scope only applies
    to the manager profile --- so it would read as a permission given and be
    none at all."""
    response = client_for(world["admin"]).patch(
        f"/api/departments/{world['office'].id}/",
        {"managers": [str(world["clerk"].id)]},
        format="json",
    )

    assert response.status_code == 400
