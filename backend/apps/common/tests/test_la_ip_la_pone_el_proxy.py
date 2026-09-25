"""The caller's address is the one our own proxy wrote, not the one the caller sent.

`X-Forwarded-For` arrives as `<whatever the client sent>, <what our proxy saw>`.
The punch used to keep the first entry, so anybody could choose the address on
their own punch. And DRF, with no `NUM_PROXIES`, keyed the rate limits on the
whole header, so a different made-up entry on each attempt started a new bucket:
the five sign-ins a minute stopped counting.

Both now read `TRUSTED_PROXIES` from the end of the list. These tests send the
header the way a deployment behind nginx receives it: with a forged entry first.
"""

from __future__ import annotations

import logging

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
PROXY = "10.0.0.1"
REAL = "203.0.113.9"
FORGED = "6.6.6.6"


def behind_proxies(count):
    return override_settings(
        TRUSTED_PROXIES=count, REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": count}
    )


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def person(company):
    with tenant_context(company.id):
        return User.objects.create_user(
            email="ana@acme.test",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            role=Role.ADMIN,
        )


def punch_through_nginx(person, forwarded):
    client = APIClient()
    client.force_authenticate(user=person)
    response = client.post(
        "/api/punches/", {}, format="json", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=forwarded
    )
    assert response.status_code == 201, response.data
    with tenant_context(person.tenant_id):
        return Punch.objects.get(pk=response.data["id"]).ip_address


@pytest.mark.django_db
def test_behind_one_proxy_the_punch_keeps_what_the_proxy_saw(person):
    with behind_proxies(1):
        assert punch_through_nginx(person, f"{FORGED}, {REAL}") == REAL


@pytest.mark.django_db
def test_with_no_proxy_declared_the_header_is_not_believed(person):
    """With nothing declared the header could come from anybody, so it is ignored."""
    with behind_proxies(0):
        assert punch_through_nginx(person, f"{FORGED}, {REAL}") == PROXY


def guess_with_forged_addresses(client):
    codes = []
    for attempt in range(12):
        response = client.post(
            "/api/auth/token/",
            {"email": "ana@acme.test", "password": f"wrong-{attempt}"},
            format="json",
            REMOTE_ADDR=PROXY,
            HTTP_X_FORWARDED_FOR=f"198.51.100.{attempt}, {REAL}",
        )
        codes.append(response.status_code)
    return codes


@pytest.mark.django_db
def test_a_forged_entry_does_not_buy_more_sign_in_attempts(person):
    """The attack in one loop: a new made-up address on every wrong password.

    With the settings as they come, not overridden here: the hole was in what
    the settings left unset, so overriding them would test the fix into place."""
    codes = guess_with_forged_addresses(APIClient())

    assert 429 in codes, "twelve forged addresses and twelve fresh buckets"


@pytest.mark.django_db
def test_behind_one_proxy_a_forged_entry_does_not_either(person):
    with behind_proxies(1):
        codes = guess_with_forged_addresses(APIClient())

    assert 429 in codes


def test_the_limits_count_the_same_address_the_punch_keeps():
    assert settings.REST_FRAMEWORK["NUM_PROXIES"] == settings.TRUSTED_PROXIES


@pytest.mark.django_db
def test_a_proxy_nobody_declared_is_named_in_the_log(person, caplog):
    """The symptom of the forgotten setting is everybody sharing one bucket, which
    looks like a broken login. The log says which setting it is."""
    with behind_proxies(0), caplog.at_level(logging.WARNING, logger="security"):
        punch_through_nginx(person, REAL)

    assert any("TRUSTED_PROXIES" in r.getMessage() for r in caplog.records)
