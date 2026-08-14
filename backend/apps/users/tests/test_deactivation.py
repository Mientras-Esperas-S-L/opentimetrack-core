"""The ways a company can end up with nobody able to administer it.

Found by deactivating the wrong account while testing the admin panel and being
unable to sign back in. Neither route is exotic: both are one click away from
the people list.

A company in that state cannot add people, resolve requests, or undo whatever
caused it. The only way out is somebody with database access, which for a hosted
customer means a support ticket and for a self-hosted one means a shell.
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


def admins_of(company):
    return User.objects.filter(tenant=company, role=Role.ADMIN, is_active=True).count()


# ------------------------------------------------------------------- demotion

# This is the route that actually happens. Deactivation cannot strand a company
# --- only an administrator may deactivate, so another one always remains --- but
# demoting yourself is a dropdown away and used to answer 200.


@pytest.mark.django_db
def test_the_only_administrator_cannot_demote_themselves(company):
    admin = make(company, "solo@example.com", Role.ADMIN)

    response = client_for(admin).patch(
        f"/api/employees/{admin.id}/", {"role": "EMPLOYEE"}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_administrator"
    admin.refresh_from_db()
    assert admin.role == Role.ADMIN
    assert admins_of(company) == 1


@pytest.mark.django_db
def test_an_administrator_can_demote_themselves_when_another_one_exists(company):
    admin = make(company, "admin@example.com", Role.ADMIN)
    make(company, "second@example.com", Role.ADMIN)

    response = client_for(admin).patch(
        f"/api/employees/{admin.id}/", {"role": "EMPLOYEE"}, format="json"
    )

    assert response.status_code == 200
    admin.refresh_from_db()
    assert admin.role == Role.EMPLOYEE
    assert admins_of(company) == 1


@pytest.mark.django_db
def test_the_last_administrator_cannot_be_demoted_by_anybody(company):
    """Not only self-demotion: the rule is about the company, not the actor."""
    admin = make(company, "admin@example.com", Role.ADMIN)
    other = make(company, "other@example.com", Role.ADMIN)

    # Reduce to one administrator, legitimately.
    client_for(admin).patch(f"/api/employees/{other.id}/", {"role": "MANAGER"}, format="json")
    assert admins_of(company) == 1

    denied = client_for(admin).patch(
        f"/api/employees/{admin.id}/", {"role": "MANAGER"}, format="json"
    )
    assert denied.status_code == 409
    assert admins_of(company) == 1


@pytest.mark.django_db
def test_another_companys_administrators_do_not_count(company):
    """People are not a TenantOwnedModel --- sign-in has to find them before the
    company is known --- so the default manager spans every company. Counting
    with it would let a stranger's administrator stand in for this one's."""
    admin = make(company, "solo@example.com", Role.ADMIN)

    elsewhere = Tenant.objects.create(name="Otra SL", tax_id="B22222222", time_zone="Europe/Madrid")
    make(elsewhere, "a@otra.com", Role.ADMIN)
    make(elsewhere, "b@otra.com", Role.ADMIN)

    denied = client_for(admin).patch(
        f"/api/employees/{admin.id}/", {"role": "EMPLOYEE"}, format="json"
    )

    assert denied.status_code == 409
    assert admins_of(company) == 1
    assert admins_of(elsewhere) == 2  # untouched


@pytest.mark.django_db
def test_an_ordinary_role_change_is_unaffected(company):
    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")

    response = client_for(admin).patch(
        f"/api/employees/{worker.id}/", {"role": "MANAGER"}, format="json"
    )

    assert response.status_code == 200
    worker.refresh_from_db()
    assert worker.role == Role.MANAGER


# ---------------------------------------------------------------- deactivation


@pytest.mark.django_db
def test_you_cannot_deactivate_yourself(company):
    """One click from every row, and undoing it needs somebody else with the
    same privilege --- who may not exist."""
    admin = make(company, "admin@example.com", Role.ADMIN)

    response = client_for(admin).delete(f"/api/employees/{admin.id}/")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_deactivate_yourself"
    admin.refresh_from_db()
    assert admin.is_active


@pytest.mark.django_db
def test_deactivating_somebody_else_still_works(company):
    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")

    response = client_for(admin).delete(f"/api/employees/{worker.id}/")

    # 200 con cuerpo y no 204: la respuesta dice cuántos turnos quedan sin
    # nadie después de la baja. Quien acaba de pulsar es quien va a tener que
    # rehacer el cuadrante, y enterarse tres días después son tres días de
    # ausencias sin justificar.
    assert response.status_code == 200
    assert response.json()["future_shifts"] == 0
    worker.refresh_from_db()
    assert not worker.is_active


@pytest.mark.django_db
def test_deactivating_keeps_the_person_and_their_record(company):
    """Deactivation is not deletion: the clock events have to survive four years
    whether or not the person still works here."""
    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")

    from apps.punches.services import register_punch

    with tenant_context(company.id):
        punch = register_punch(employee=worker, company=company)

    client_for(admin).delete(f"/api/employees/{worker.id}/")

    punch.refresh_from_db()
    assert punch.is_active
    assert User.objects.filter(pk=worker.pk).exists()
