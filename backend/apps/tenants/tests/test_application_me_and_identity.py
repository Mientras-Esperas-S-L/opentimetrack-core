"""The two small doors a connector needed: who am I, and an alta with issuer and role."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


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


# ---------------------------------------------------------------- who am I


@pytest.mark.django_db
def test_an_application_can_ask_who_it_is(company):
    client = credential(company, ApplicationScope.READ_PEOPLE, ApplicationScope.PUNCH_DELEGATED)
    answer = client.get("/api/app/me/")
    assert answer.status_code == 200
    body = answer.json()
    assert body["application"]["name"] == "Geosian"
    assert sorted(body["application"]["scopes"]) == ["punch:delegated", "read:people"]
    assert body["company"] == {
        "id": str(company.id),
        "name": "ACME Ltd",
        "time_zone": "Europe/Madrid",
    }


@pytest.mark.django_db
def test_who_am_i_needs_no_scope_but_does_need_a_credential(company):
    assert credential(company).get("/api/app/me/").status_code == 200
    assert APIClient().get("/api/app/me/").status_code == 401


@pytest.mark.django_db
def test_a_person_cannot_use_the_application_door(company):
    with tenant_context(company.id):
        admin = User.objects.create_user(
            email="jefa@acme.example", password=PASSWORD, tenant=company, role=Role.ADMIN
        )
    client = APIClient()
    client.force_authenticate(user=admin)
    assert client.get("/api/app/me/").status_code == 403


# --------------------------------------------------- issuer and role at alta


@pytest.mark.django_db
def test_the_alta_records_the_issuer_and_honours_the_role_only_when_creating(company):
    client = credential(company, ApplicationScope.WRITE_PEOPLE, ApplicationScope.READ_PEOPLE)
    payload = {
        "email": "rosa@acme.example",
        "first_name": "Rosa",
        "employee_id": "EMP-0042",
        "oidc_sub": "abc",
        "oidc_issuer": "https://gcc.example/o",
        "role": "MANAGER",
    }
    created = client.put("/api/app/people/EMP-0042/", payload, format="json")
    assert created.status_code == 201
    assert created.json()["oidc_issuer"] == "https://gcc.example/o"
    assert created.json()["role"] == "MANAGER"

    # A second push demoting her is ignored: the role of people who exist is decided here.
    again = client.put("/api/app/people/EMP-0042/", {**payload, "role": "EMPLOYEE"}, format="json")
    assert again.status_code == 200
    assert again.json()["role"] == "MANAGER"


@pytest.mark.django_db
def test_an_unknown_role_is_refused(company):
    client = credential(company, ApplicationScope.WRITE_PEOPLE)
    answer = client.put(
        "/api/app/people/EMP-1/",
        {"email": "p@acme.example", "first_name": "P", "role": "BOSS"},
        format="json",
    )
    assert answer.status_code == 400
