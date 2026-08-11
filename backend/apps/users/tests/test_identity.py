"""Identity: per-company email, passwords and authentication."""

from __future__ import annotations

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction

from apps.tenants.models import Tenant
from apps.users.models import Role

User = get_user_model()

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def acme(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def globex(db):
    return Tenant.objects.create(name="Globex Inc", tax_id="B22222222")


def make_user(tenant, email="ana@example.com", password=PASSWORD, **extra):
    return User.objects.create_user(
        email=email,
        password=password,
        tenant=tenant,
        first_name=extra.pop("first_name", "Ana"),
        last_name=extra.pop("last_name", "García"),
        **extra,
    )


# ------------------------------------------------------------------ unique email


@pytest.mark.django_db
def test_the_same_person_can_belong_to_two_companies(acme, globex):
    """The case that broke the previous design, with a globally unique email."""
    a = make_user(acme)
    b = make_user(globex)

    assert a.pk != b.pk
    assert a.email == b.email


@pytest.mark.django_db
def test_the_email_cannot_repeat_within_one_company(acme):
    make_user(acme)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_user(acme)


@pytest.mark.django_db
def test_the_email_is_normalised_to_lowercase(acme):
    user = make_user(acme, email="Ana.Garcia@Example.COM")

    assert user.email == "ana.garcia@example.com"


# --------------------------------------------------------------------- passwords


@pytest.mark.django_db
def test_the_password_is_stored_with_argon2(acme):
    """RF-01.6: strong hashing. Never in the clear, and with the chosen algorithm."""
    user = make_user(acme)

    assert user.password.startswith("argon2$")
    assert PASSWORD not in user.password
    assert user.check_password(PASSWORD)


# ---------------------------------------------------------------- authentication


@pytest.mark.django_db
def test_sign_in_naming_the_company(acme, globex):
    make_user(acme)
    make_user(globex)

    user = authenticate(None, email="ana@example.com", password=PASSWORD, tenant_id=acme.id)

    assert user is not None
    assert user.tenant_id == acme.id


@pytest.mark.django_db
def test_an_email_in_two_companies_without_naming_one_is_rejected(acme, globex):
    """Picking one would be guessing, so it is refused."""
    make_user(acme)
    make_user(globex)

    assert authenticate(None, email="ana@example.com", password=PASSWORD) is None


@pytest.mark.django_db
def test_an_email_in_a_single_company_signs_in_without_naming_it(acme):
    make_user(acme)

    assert authenticate(None, email="ana@example.com", password=PASSWORD) is not None


@pytest.mark.django_db
def test_the_wrong_password_is_rejected(acme):
    make_user(acme)

    assert authenticate(None, email="ana@example.com", password="something-else") is None


@pytest.mark.django_db
def test_a_deactivated_person_cannot_sign_in(acme):
    make_user(acme, is_active=False)

    assert authenticate(None, email="ana@example.com", password=PASSWORD) is None


@pytest.mark.django_db
def test_when_the_company_is_deactivated_nobody_from_it_signs_in(acme):
    """Deactivating a company has to cut off access for all of its people."""
    make_user(acme)
    acme.is_active = False
    acme.save()

    assert authenticate(None, email="ana@example.com", password=PASSWORD) is None


@pytest.mark.django_db
def test_a_federated_account_cannot_sign_in_with_a_password(acme):
    """Its identity is governed by the provider; no local password applies."""
    user = make_user(acme, oidc_sub="sub-123", oidc_issuer="https://login.example.com")
    user.set_unusable_password()
    user.save()

    assert user.is_federated
    assert authenticate(None, email="ana@example.com", password="anything") is None


# -------------------------------------------------------------------------- roles


@pytest.mark.django_db
def test_roles_resolve_what_they_promise(acme):
    employee = make_user(acme, email="e@example.com", role=Role.EMPLOYEE)
    manager = make_user(acme, email="m@example.com", role=Role.MANAGER)
    admin = make_user(acme, email="a@example.com", role=Role.ADMIN)

    assert not employee.can_manage and not employee.is_admin
    assert manager.can_manage and not manager.is_admin
    assert admin.can_manage and admin.is_admin


# ---------------------------------------------------------------------- time zones


@pytest.mark.django_db
def test_a_company_can_live_in_any_time_zone(db):
    """Spain alone spans two zones, and the product is not limited to Spain."""
    canary = Tenant.objects.create(
        name="Isleña S.L.", tax_id="B33333333", time_zone="Atlantic/Canary"
    )
    mexico = Tenant.objects.create(
        name="Azteca SA de CV",
        tax_id="RFC12345678",
        country="MX",
        time_zone="America/Mexico_City",
    )

    assert str(canary.tzinfo) == "Atlantic/Canary"
    assert str(mexico.tzinfo) == "America/Mexico_City"


@pytest.mark.django_db
def test_an_invalid_time_zone_is_rejected(db):
    from django.core.exceptions import ValidationError

    company = Tenant(name="Bad", tax_id="B44444444", time_zone="Mars/Olympus_Mons")

    with pytest.raises(ValidationError):
        company.full_clean()
