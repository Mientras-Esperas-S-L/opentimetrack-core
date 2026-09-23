"""A punch sent twice by a queue that could not hear the answer.

The phone records the punch with no signal, sends it when the signal returns, and
does not hear back. It tries again. Without a key naming the operation, that second
try does not repeat the entry: it records an **exit**, because the type is inferred
from the current state, and a nine-hour day reads as thirty seconds.

The delegated door has had this from the start. What is fixed here is the ordinary
door --- the one an application uses with the person's own session, which is where
the queue actually lives.
"""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.tenants.identity import SsoProvider
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
ISSUER = "https://gcc.example/o"
GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(scope="module")
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key()


@pytest.fixture
def jwks(keypair, monkeypatch):
    _private, public = keypair
    numbers = public.public_numbers()

    def to_b64(value: int) -> str:
        import base64

        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    key = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": to_b64(numbers.n),
        "e": to_b64(numbers.e),
    }

    class FakeJWKClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            from jwt import PyJWK

            return PyJWK.from_dict(key)

    monkeypatch.setattr(jwt, "PyJWKClient", FakeJWKClient)
    # Y de dónde sale la URL de las claves, que ahora se le pregunta al proveedor:
    # sin esto el fixture serviría la clave y la resolución saldría a la red.
    from apps.tenants import sso

    monkeypatch.setattr(
        sso, "discovery", lambda p: {"issuer": p.issuer, "jwks_uri": f"{p.issuer}/jwks.json"}
    )
    return key


def assertion_for(keypair, reference, *, jti="one"):
    private, _public = keypair
    now = dt.datetime.now(tz=dt.UTC)
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": ISSUER,
            "sub": str(reference),
            "employee_id": str(reference),
            "iat": int(now.timestamp()),
            "exp": int((now + dt.timedelta(seconds=60)).timestamp()),
            "jti": jti,
        },
        private,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def provider(company):
    return SsoProvider.objects.create(
        tenant=company, name="Conector de ejemplo", issuer=ISSUER, may_act_for_people=True
    )


@pytest.fixture
def rosa(company):
    with tenant_context(company.id):
        return User.objects.create_user(
            email="rosa@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="gcc-0042",
            first_name="Rosa",
            last_name="Campos",
        )


@pytest.fixture
def phone(company, provider, rosa, keypair, jwks):
    """A client holding the session the application bought for Rosa."""
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="Geosian", scopes=[str(ApplicationScope.PUNCH_SELF)]
        )
        _credential, secret = ApplicationCredential.issue(application)
    connector = APIClient()
    connector.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    tokens = connector.post(
        "/api/app/sessions/",
        {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")},
        format="json",
    ).json()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


# ------------------------------------------------------------------ the retry


@pytest.mark.django_db
def test_the_same_key_twice_records_one_punch_and_returns_it(phone, rosa):
    first = phone.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-1")
    second = phone.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-1")

    assert first.status_code == 201
    assert second.status_code == 200, "el reintento no crea nada, devuelve lo que ya hay"
    assert first.json()["id"] == second.json()["id"]
    with tenant_context(rosa.tenant_id):
        assert Punch.objects.filter(employee=rosa).count() == 1


@pytest.mark.django_db
def test_without_a_key_the_retry_would_have_recorded_an_exit(phone, rosa):
    """Lo que la clave evita, dicho con el caso que lo provoca."""
    phone.post("/api/punches/", {}, format="json")
    # Pasado el margen del doble toque, que es de segundos y no de una cola.
    with tenant_context(rosa.tenant_id):
        Punch.objects.filter(employee=rosa).update(
            timestamp=Punch.objects.get(employee=rosa).timestamp - dt.timedelta(minutes=30)
        )
    phone.post("/api/punches/", {}, format="json")

    with tenant_context(rosa.tenant_id):
        tipos = list(
            Punch.objects.filter(employee=rosa)
            .order_by("timestamp")
            .values_list("punch_type", flat=True)
        )
    assert tipos == [PunchType.IN, PunchType.OUT], "la jornada de Rosa dura media hora"


@pytest.mark.django_db
def test_two_different_keys_are_two_punches(phone, rosa):
    primero = phone.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-1")
    with tenant_context(rosa.tenant_id):
        Punch.objects.filter(employee=rosa).update(
            timestamp=Punch.objects.get(employee=rosa).timestamp - dt.timedelta(minutes=30)
        )
    segundo = phone.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-2")

    assert primero.status_code == 201
    assert segundo.status_code == 201
    with tenant_context(rosa.tenant_id):
        assert Punch.objects.filter(employee=rosa).count() == 2


@pytest.mark.django_db
def test_the_queue_keeps_the_time_it_was_made_at(phone, rosa):
    hecho = dt.datetime.now(tz=dt.UTC) - dt.timedelta(hours=2)

    answer = phone.post(
        "/api/punches/",
        {"declared_at": hecho.isoformat()},
        format="json",
        HTTP_IDEMPOTENCY_KEY="cola-sin-cobertura",
    )

    assert answer.status_code == 201
    assert answer.json()["was_deferred"] is True
    with tenant_context(rosa.tenant_id):
        punch = Punch.objects.get(employee=rosa)
    assert punch.timestamp == hecho
    assert punch.received_at > punch.declared_at


# ---------------------------------------------------------------- the limits


@pytest.mark.django_db
def test_a_person_on_their_own_is_told_the_key_means_nothing_here(company, rosa):
    """Sin aplicación no hay cola, y ofrecer la garantía sería ofrecer humo."""
    client = APIClient()
    client.force_authenticate(user=rosa)

    answer = client.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-1")

    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "idempotency_key_not_accepted"
    with tenant_context(rosa.tenant_id):
        assert not Punch.objects.filter(employee=rosa).exists()


@pytest.mark.django_db
def test_another_application_cannot_read_back_this_punch(
    phone, company, rosa, provider, keypair, jwks
):
    """Las claves son de cada aplicación: dos conectores numerando lo suyo no chocan."""
    phone.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-1")

    with tenant_context(company.id):
        otra = Application.objects.create(
            tenant=company, name="Otra", scopes=[str(ApplicationScope.PUNCH_SELF)]
        )
        _credential, secret = ApplicationCredential.issue(otra)
    connector = APIClient()
    connector.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    tokens = connector.post(
        "/api/app/sessions/",
        {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042", jti="dos")},
        format="json",
    ).json()
    vecina = APIClient()
    vecina.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    with tenant_context(rosa.tenant_id):
        Punch.objects.filter(employee=rosa).update(
            timestamp=Punch.objects.get(employee=rosa).timestamp - dt.timedelta(minutes=30)
        )
    answer = vecina.post("/api/punches/", {}, format="json", HTTP_IDEMPOTENCY_KEY="cola-1")

    assert answer.status_code == 201, "la misma clave en otra aplicación es otra operación"
    with tenant_context(rosa.tenant_id):
        assert Punch.objects.filter(employee=rosa).count() == 2
