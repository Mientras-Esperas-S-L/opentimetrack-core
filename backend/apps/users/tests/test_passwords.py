"""Password recovery and invitations."""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.tenants.models import Tenant
from apps.users.models import User
from apps.users.passwords import build_token

PASSWORD = "a-sufficiently-long-password"
NEW_PASSWORD = "another-long-enough-password"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def acme(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def globex(db):
    return Tenant.objects.create(name="Globex Inc", tax_id="B22222222")


def make_user(tenant, email="ana@example.com", **extra):
    return User.objects.create_user(
        email=email, password=PASSWORD, tenant=tenant,
        first_name="Ana", last_name="García", **extra,
    )


# ------------------------------------------------------------------- requesting


@pytest.mark.django_db
def test_requesting_recovery_sends_the_link(client, acme):
    make_user(acme)

    response = client.post(reverse("auth:password-reset"), {"email": "ana@example.com"})

    assert response.status_code == 204
    assert len(mail.outbox) == 1
    assert "set-password" in mail.outbox[0].body


@pytest.mark.django_db
def test_an_unknown_address_gets_the_same_answer(client, db):
    """Otherwise the endpoint tells you who works where."""
    response = client.post(reverse("auth:password-reset"), {"email": "nobody@example.com"})

    assert response.status_code == 204
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_an_address_in_two_companies_gets_one_link_each(client, acme, globex):
    """Nobody should have to type a tax number to get back in."""
    make_user(acme)
    make_user(globex)

    client.post(reverse("auth:password-reset"), {"email": "ana@example.com"})

    assert len(mail.outbox) == 2
    bodies = " ".join(message.body for message in mail.outbox)
    assert "ACME Ltd" in bodies
    assert "Globex Inc" in bodies


@pytest.mark.django_db
def test_a_federated_account_gets_no_link(client, acme):
    """Its credentials belong to the provider; a password here would be useless."""
    user = make_user(acme, oidc_sub="sub-1", oidc_issuer="https://login.example.com")
    user.set_unusable_password()
    user.save()

    client.post(reverse("auth:password-reset"), {"email": "ana@example.com"})

    assert len(mail.outbox) == 0


# ---------------------------------------------------------------------- setting


@pytest.mark.django_db
def test_the_link_sets_the_password_and_signs_in(client, acme):
    user = make_user(acme)
    uid, token = build_token(user)

    response = client.post(
        reverse("auth:set-password"),
        {"uid": uid, "token": token, "password": NEW_PASSWORD},
    )

    assert response.status_code == 200
    assert "access" in response.data  # straight in, no second sign-in
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_the_link_only_works_once(client, acme):
    """Using it changes the password hash, which is what the token is built on."""
    user = make_user(acme)
    uid, token = build_token(user)

    first = client.post(
        reverse("auth:set-password"), {"uid": uid, "token": token, "password": NEW_PASSWORD}
    )
    second = client.post(
        reverse("auth:set-password"), {"uid": uid, "token": token, "password": "yet-another-one-x"}
    )

    assert first.status_code == 200
    assert second.status_code == 400


@pytest.mark.django_db
def test_a_tampered_token_is_rejected(client, acme):
    user = make_user(acme)
    uid, _token = build_token(user)

    response = client.post(
        reverse("auth:set-password"),
        {"uid": uid, "token": "made-up-token", "password": NEW_PASSWORD},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_somebody_invited_without_a_password_can_get_in(client, acme):
    """The dead end this whole flow exists to remove.

    An administrator creates an account with no password on purpose -- a default
    one would be worse -- and without this the person could never sign in.
    """
    user = User.objects.create_user(
        email="nueva@example.com", password=None, tenant=acme,
        first_name="Nueva", last_name="Persona",
    )
    user.set_unusable_password()
    user.save()

    assert not user.has_usable_password()

    uid, token = build_token(user)
    response = client.post(
        reverse("auth:set-password"), {"uid": uid, "token": token, "password": NEW_PASSWORD}
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_a_short_password_is_rejected(client, acme):
    user = make_user(acme)
    uid, token = build_token(user)

    response = client.post(
        reverse("auth:set-password"), {"uid": uid, "token": token, "password": "short"}
    )

    assert response.status_code == 400
