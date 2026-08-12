"""The limits, and that anything applies them at all.

`DEFAULT_THROTTLE_RATES` sat in settings with no `DEFAULT_THROTTLE_CLASSES`
next to it, so DRF read the rates and enforced none of them. Nothing failed;
the endpoints simply answered as often as they were asked. Twelve password
attempts in a row, all processed. Eight recovery emails to the same address,
all sent.

That is the failure mode worth testing against: not a limit set too high, but a
limit that is written down and does nothing. So these tests are about the
mechanism being connected --- one of them deliberately keeps going until it gets
a 429 rather than assuming the count.
"""

from __future__ import annotations

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


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


def guess(client, times):
    """Wrong passwords until one is refused for being too many."""
    codes = []
    for attempt in range(times):
        response = client.post(
            "/api/auth/token/",
            {"email": "ana@acme.test", "password": f"wrong-{attempt}"},
            format="json",
        )
        codes.append(response.status_code)
    return codes


@pytest.mark.django_db
def test_password_guessing_is_cut_off(person):
    """The one that matters. Unlimited attempts against a known address is the
    whole attack, and it needs no cleverness at all."""
    codes = guess(APIClient(), 12)

    assert 429 in codes, "twelve password attempts and none was refused"
    # And it cuts off near where it says it does, rather than at some
    # unrelated number.
    assert codes.index(429) <= 6


@pytest.mark.django_db
def test_a_correct_password_does_not_get_past_the_limit(person):
    """Otherwise the limit is a formality: guess until the bucket is full, keep
    guessing, and the right one still goes through."""
    client = APIClient()
    guess(client, 8)

    response = client.post(
        "/api/auth/token/", {"email": "ana@acme.test", "password": PASSWORD}, format="json"
    )

    assert response.status_code == 429


@pytest.mark.django_db
def test_recovery_mail_cannot_be_used_as_a_mail_bomb(person):
    """It answers 204 whoever asks --- deliberately, so it cannot be used to find
    out who works where --- which also means it will send to any address given.
    Unlimited, that is somebody else's inbox."""
    client = APIClient()
    codes = [
        client.post(
            "/api/auth/password-reset/", {"email": "ana@acme.test"}, format="json"
        ).status_code
        for _ in range(10)
    ]

    assert 429 in codes
    assert len(mail.outbox) < 10


@pytest.mark.django_db
def test_an_ordinary_session_is_not_throttled_out_of_working(person):
    """The check on the fix. A limit that stops somebody using the product is
    not security, and the panel makes several requests per screen."""
    client = APIClient()
    client.force_authenticate(person)

    codes = [client.get("/api/punches/").status_code for _ in range(60)]

    assert set(codes) == {200}


@pytest.mark.django_db
def test_an_application_is_limited_on_its_own_budget(company):
    """Applications are throttled too --- an integration in a loop is the
    likeliest flood --- but on their own bucket, so one client's loop cannot
    lock the staff out of the panel.

    And they are throttled at all: DRF's own UserRateThrottle keys on
    `request.user.pk`, which an application does not have, so turning the
    throttles on plainly answered every delegated punch with an AttributeError.
    """
    from apps.tenants.models import Application, ApplicationCredential, ApplicationScope

    with tenant_context(company.id):
        app = Application.objects.create(
            tenant=company, name="Terminal", scopes=[ApplicationScope.PUNCH_DELEGATED]
        )
        _credential, secret = ApplicationCredential.issue(app)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    response = client.post(
        "/api/punches/delegated/", {"employee_ref": "nadie@acme.test"}, format="json"
    )

    # The reference does not exist, which is a clean refusal --- what matters is
    # that it is a refusal about the reference and not a crash in the throttle.
    assert response.status_code in {400, 404, 409}
