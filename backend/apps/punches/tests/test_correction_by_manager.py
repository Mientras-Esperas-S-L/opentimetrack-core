"""A manager correcting somebody else's record.

ADR-0014 allows it: a manager may correct without a prior request, but through
the same procedure and with the same mandatory reason. Nobody touches a time
without leaving why.

The distinction the tests pin down is that **who it concerns** and **who filed
it** are two separate facts. Collapsing them would make a correction imposed
from above indistinguishable from one the worker asked for --- which is exactly
what somebody reading the record later needs to tell apart.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.models import tenant_context
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


def body(employee=None, **extra):
    payload = {
        "kind": "ADD",
        "proposed_type": "OUT",
        "proposed_timestamp": (timezone.now() - timedelta(hours=3)).isoformat(),
        "reason": "La tableta se quedó sin batería en obra.",
        **extra,
    }
    if employee:
        payload["employee"] = str(employee.id)
    return payload


@pytest.mark.django_db
def test_a_manager_can_correct_somebody_elses_record(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")

    response = client_for(boss).post("/api/corrections/", body(worker), format="json")

    assert response.status_code == 201
    assert response.json()["employee"] == str(worker.id)


@pytest.mark.django_db
def test_the_record_keeps_who_it_is_about_and_who_filed_it(company):
    """Two fields, not one. A correction imposed from above and one the worker
    asked for must not look the same afterwards."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")

    created = client_for(boss).post("/api/corrections/", body(worker), format="json").json()

    assert created["employee"] == str(worker.id)
    assert created["requested_by"] == str(boss.id)
    assert created["employee"] != created["requested_by"]


@pytest.mark.django_db
def test_a_worker_cannot_correct_somebody_elses(company):
    ana = make(company, "ana@example.com")
    beto = make(company, "beto@example.com")

    response = client_for(ana).post("/api/corrections/", body(beto), format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_your_record"


@pytest.mark.django_db
def test_naming_yourself_is_the_same_as_naming_nobody(company):
    ana = make(company, "ana@example.com")

    named = client_for(ana).post("/api/corrections/", body(ana), format="json")
    assert named.status_code == 201
    assert named.json()["employee"] == str(ana.id)


@pytest.mark.django_db
def test_the_reason_is_still_mandatory_for_a_manager(company):
    """The privilege is to correct without a request, not to correct without a
    reason. A correction with no stated reason is indistinguishable from
    tampering, whoever files it."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")

    response = client_for(boss).post("/api/corrections/", body(worker, reason=""), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_somebody_from_another_company_is_not_found(company):
    boss = make(company, "boss@example.com", Role.MANAGER)
    elsewhere = Tenant.objects.create(name="Otra SL", tax_id="B22222222", time_zone="Europe/Madrid")
    stranger = make(elsewhere, "them@otra.com")

    response = client_for(boss).post("/api/corrections/", body(stranger), format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unknown_employee"
