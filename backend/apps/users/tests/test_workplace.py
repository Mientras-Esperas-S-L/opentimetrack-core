"""Centros de trabajo, y la hora que se le aplica a cada persona.

El caso que lo justifica todo: una empresa con oficina en Madrid y otra en Las
Palmas. Una hora de diferencia, y una hora es lo que separa un fichaje que cae
en lunes de uno que cae en domingo. El código que parte el día ya lo decía en un
comentario meses antes de que hubiera dónde apuntar la respuesta.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.punches.services import punches_of_the_day
from apps.tenants.models import Tenant
from apps.users.models import Role, User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def sites(company):
    with tenant_context(company.id):
        yield {
            "madrid": Workplace.objects.create(
                tenant=company, name="Madrid", municipality="Madrid", region="ES-MD"
            ),
            "canarias": Workplace.objects.create(
                tenant=company,
                name="Las Palmas",
                municipality="Las Palmas de Gran Canaria",
                region="ES-CN",
                time_zone="Atlantic/Canary",
            ),
        }


def person(company, email, workplace=None, role=Role.EMPLOYEE):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email,
            password=PASSWORD,
            tenant=company,
            first_name=email.split("@")[0],
            role=role,
            workplace=workplace,
        )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ------------------------------------------------------------------ the zone


@pytest.mark.django_db
def test_without_a_workplace_the_company_zone_applies(company):
    assert str(person(company, "nadie@example.com").tzinfo) == "Europe/Madrid"


@pytest.mark.django_db
def test_a_workplace_with_no_zone_of_its_own_uses_the_company_one(company, sites):
    assert str(person(company, "mad@example.com", sites["madrid"]).tzinfo) == "Europe/Madrid"


@pytest.mark.django_db
def test_the_canary_islands_are_an_hour_behind(company, sites):
    assert str(person(company, "lpa@example.com", sites["canarias"]).tzinfo) == "Atlantic/Canary"


@pytest.mark.django_db
def test_the_same_instant_falls_on_different_days(company, sites):
    """23:30 in Madrid is 22:30 in Las Palmas, on the day before nothing --- but
    00:30 in Madrid is 23:30 the previous day out there, and that is a punch on
    the wrong date in the record that has to stand up in court."""
    here = person(company, "mad@example.com", sites["madrid"])
    there = person(company, "lpa@example.com", sites["canarias"])

    # 2026-09-02 00:30 in Madrid == 2026-09-01 23:30 in the Canaries.
    moment = datetime(2026, 9, 1, 22, 30, tzinfo=UTC)
    with tenant_context(company.id):
        for who in (here, there):
            Punch.objects.create(
                tenant=company, employee=who, punch_type=PunchType.IN, timestamp=moment
            )

        from datetime import date

        assert punches_of_the_day(here, company, date(2026, 9, 2)).count() == 1
        assert punches_of_the_day(here, company, date(2026, 9, 1)).count() == 0
        assert punches_of_the_day(there, company, date(2026, 9, 1)).count() == 1
        assert punches_of_the_day(there, company, date(2026, 9, 2)).count() == 0


# ------------------------------------------------------------------- the API


@pytest.mark.django_db
def test_a_region_that_does_not_exist_is_refused(company):
    """Free text here would be the same mistake as a calendar keyed by name: it
    looks stored and quietly matches nothing when the holidays arrive."""
    admin = person(company, "admin@example.com", role=Role.ADMIN)

    response = client_for(admin).post(
        "/api/workplaces/", {"name": "Sede", "region": "ES-XX"}, format="json"
    )

    assert response.status_code == 400
    assert "region" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_the_region_comes_back_with_its_name(company):
    admin = person(company, "admin@example.com", role=Role.ADMIN)

    body = (
        client_for(admin)
        .post("/api/workplaces/", {"name": "Sede", "region": "ES-AN"}, format="json")
        .json()
    )

    assert body["region_name"] == "Andalucía"
    # Resolved, not blank: the field can be empty and mean "the company's", and
    # showing the blank would hide the answer rather than say there is a default.
    assert body["effective_time_zone"] == "Europe/Madrid"


@pytest.mark.django_db
def test_a_workplace_with_people_in_it_cannot_be_deleted(company, sites):
    """`SET_NULL` is a tidy answer for a department and the wrong one here:
    people left without a workplace silently lose their local holidays and
    start being measured in the company's zone."""
    admin = person(company, "admin@example.com", role=Role.ADMIN)
    person(company, "lpa@example.com", sites["canarias"])

    response = client_for(admin).delete(f"/api/workplaces/{sites['canarias'].id}/")

    assert response.status_code >= 400
    with tenant_context(company.id):
        assert Workplace.objects.filter(pk=sites["canarias"].pk).exists()


@pytest.mark.django_db
def test_an_empty_one_can(company, sites):
    admin = person(company, "admin@example.com", role=Role.ADMIN)

    assert client_for(admin).delete(f"/api/workplaces/{sites['madrid'].id}/").status_code == 204


@pytest.mark.django_db
def test_a_worker_may_read_the_workplaces(company, sites):
    """They are entitled to know where their record is kept and which holiday
    calendar is being applied to them."""
    worker = person(company, "obrero@example.com", sites["madrid"])

    assert client_for(worker).get("/api/workplaces/").status_code == 200


@pytest.mark.django_db
def test_but_not_change_one(company, sites):
    worker = person(company, "obrero@example.com", sites["madrid"])

    response = client_for(worker).patch(
        f"/api/workplaces/{sites['madrid'].id}/", {"name": "Mío"}, format="json"
    )

    assert response.status_code == 403
