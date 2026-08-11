"""Company settings, and the one that is not a preference.

These fields were reachable only through the Django admin. Several carry legal
weight, so the endpoint is where the limits belong --- and the retention floor is
a limit, not a default somebody can lower.
"""

from __future__ import annotations

import pytest
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


@pytest.mark.django_db
def test_anybody_in_the_company_can_read_the_settings(company):
    """A worker is entitled to know the time zone their hours are recorded in."""
    worker = make(company, "worker@example.com")

    response = client_for(worker).get("/api/company/")

    assert response.status_code == 200
    assert response.json()["time_zone"] == "Europe/Madrid"


@pytest.mark.django_db
def test_only_an_administrator_changes_them(company):
    worker = make(company, "worker@example.com")
    manager = make(company, "boss@example.com", Role.MANAGER)

    for person in (worker, manager):
        denied = client_for(person).patch("/api/company/", {"annual_leave_days": 30}, format="json")
        assert denied.status_code == 403

    admin = make(company, "admin@example.com", Role.ADMIN)
    allowed = client_for(admin).patch("/api/company/", {"annual_leave_days": 30}, format="json")
    assert allowed.status_code == 200

    company.refresh_from_db()
    assert company.annual_leave_days == 30


@pytest.mark.django_db
def test_retention_cannot_go_below_the_legal_floor(company):
    """Art. 34.9 ET is not a preference. Letting a company set two years would
    mean the product helping it fail to keep what the law says it must."""
    admin = make(company, "admin@example.com", Role.ADMIN)

    denied = client_for(admin).patch("/api/company/", {"record_retention_years": 2}, format="json")
    assert denied.status_code == 400

    allowed = client_for(admin).patch("/api/company/", {"record_retention_years": 6}, format="json")
    assert allowed.status_code == 200
    company.refresh_from_db()
    assert company.record_retention_years == 6


@pytest.mark.django_db
def test_the_tax_number_is_not_a_setting(company):
    """It identifies the company in every report already issued."""
    admin = make(company, "admin@example.com", Role.ADMIN)

    client_for(admin).patch("/api/company/", {"tax_id": "B99999999"}, format="json")

    company.refresh_from_db()
    assert company.tax_id == "B11111111"


@pytest.mark.django_db
def test_an_invalid_time_zone_is_refused(company):
    admin = make(company, "admin@example.com", Role.ADMIN)

    response = client_for(admin).patch(
        "/api/company/", {"time_zone": "Europe/Narnia"}, format="json"
    )

    assert response.status_code == 400
    company.refresh_from_db()
    assert company.time_zone == "Europe/Madrid"


@pytest.mark.django_db
def test_the_settings_are_the_callers_own_company(company):
    """No id in the path: the company is the caller's. Worth pinning --- an
    endpoint that took one would need scoping, and forgetting it would let
    anybody read another company's configuration."""
    elsewhere = Tenant.objects.create(
        name="Otra SL", tax_id="B22222222", time_zone="Atlantic/Canary"
    )
    make(elsewhere, "them@otra.com", Role.ADMIN)
    ours = make(company, "admin@example.com", Role.ADMIN)

    body = client_for(ours).get("/api/company/").json()

    assert body["tax_id"] == "B11111111"
    assert body["time_zone"] == "Europe/Madrid"
