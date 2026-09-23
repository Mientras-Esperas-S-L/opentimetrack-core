"""A session for one of the application's people, from a signed assertion.

What is fixed here is what makes this door safe enough to exist: both keys are
required, the issuer must be trusted *and* allowed to act, the assertion is short
lived and single use, nothing crosses companies, and a punch made with the session
says an application was acting.
"""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchSource
from apps.tenants.identity import SsoProvider
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
URL = "/api/app/sessions/"
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
    """Serves the issuer's public key without going out to the network."""
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
    # Y de dónde sale la URL de las claves, que desde que hay una sola respuesta
    # para los dos flujos la pregunta al proveedor: sin esto el fixture serviría la
    # clave y la resolución de la URL saldría a la red de verdad.
    from apps.tenants import sso

    monkeypatch.setattr(
        sso, "discovery", lambda p: {"issuer": p.issuer, "jwks_uri": f"{p.issuer}/jwks.json"}
    )
    return key


def assertion_for(
    keypair, reference, *, issuer=ISSUER, audience=ISSUER, lifetime=60, jti="one", now=None
):
    private, _public = keypair
    now = now or dt.datetime.now(tz=dt.UTC)
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": str(reference),
        "employee_id": str(reference),
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=lifetime)).timestamp()),
        "jti": jti,
    }
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def provider(company):
    return SsoProvider.objects.create(
        tenant=company, name="Conector de ejemplo", issuer=ISSUER, may_act_for_people=True
    )


def credential(company, *scopes, name="Geosian"):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name=name, scopes=[str(scope) for scope in scopes]
        )
        _credential, secret = ApplicationCredential.issue(application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    return client


@pytest.fixture
def connector(company):
    return credential(company, ApplicationScope.PUNCH_SELF)


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


# --------------------------------------------------------------- the exchange


@pytest.mark.django_db
def test_a_signed_assertion_buys_a_session_for_that_person(
    connector, provider, rosa, keypair, jwks
):
    answer = connector.post(
        URL, {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")}, format="json"
    )

    assert answer.status_code == 201
    body = answer.json()
    assert body["employee"] == str(rosa.id) and body["name"] == "Rosa Campos"
    assert body["access"] and body["refresh"]

    # And the session really is hers.
    person = APIClient()
    person.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert person.get("/api/auth/me/").json()["user"]["email"] == "rosa@acme.example"


@pytest.mark.django_db
def test_what_it_clocks_is_recorded_as_coming_from_the_application(
    connector, provider, rosa, keypair, jwks
):
    tokens = connector.post(
        URL, {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")}, format="json"
    ).json()
    person = APIClient()
    person.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    # Even declaring another origin: the token wins, the body does not.
    clocked = person.post(
        "/api/punches/", {"source": "WEB", "evidence": {"map": "papeleras"}}, format="json"
    )

    assert clocked.status_code == 201
    with tenant_context(rosa.tenant_id):
        punch = Punch.objects.get(employee=rosa)
    assert punch.source == PunchSource.APPLICATION
    assert punch.source_application == "Geosian"
    assert punch.evidence == {"map": "papeleras"}, "la referencia de contexto viaja en la evidencia"


# ------------------------------------------------------------------ refusals


@pytest.mark.django_db
def test_both_keys_are_required(company, provider, rosa, keypair, jwks):
    without_scope = credential(company, ApplicationScope.READ_PEOPLE)
    assert (
        without_scope.post(
            URL,
            {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")},
            format="json",
        ).status_code
        == 403
    )
    assert (
        APIClient()
        .post(
            URL,
            {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")},
            format="json",
        )
        .status_code
        == 401
    )


@pytest.mark.django_db
def test_an_unknown_issuer_is_refused(connector, rosa, keypair, jwks):
    answer = connector.post(
        URL, {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")}, format="json"
    )
    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "issuer_not_trusted"


@pytest.mark.django_db
def test_a_provider_that_may_not_act_is_refused(connector, company, rosa, keypair, jwks):
    SsoProvider.objects.create(
        tenant=company, name="Entra", issuer=ISSUER, may_act_for_people=False
    )
    answer = connector.post(
        URL, {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")}, format="json"
    )
    assert answer.json()["error"]["code"] == "issuer_may_not_act"


@pytest.mark.django_db
def test_an_expired_assertion_is_refused(connector, provider, rosa, keypair, jwks):
    old = dt.datetime.now(tz=dt.UTC) - dt.timedelta(minutes=10)
    answer = connector.post(
        URL,
        {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042", now=old)},
        format="json",
    )
    assert answer.json()["error"]["code"] == "assertion_expired"


@pytest.mark.django_db
def test_a_long_lived_assertion_is_refused(connector, provider, rosa, keypair, jwks):
    answer = connector.post(
        URL,
        {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042", lifetime=3600)},
        format="json",
    )
    assert answer.json()["error"]["code"] == "assertion_too_long"


@pytest.mark.django_db
def test_an_assertion_cannot_be_used_twice(connector, provider, rosa, keypair, jwks):
    token = assertion_for(keypair, "gcc-0042", jti="only-once")
    assert (
        connector.post(URL, {"grant_type": GRANT, "assertion": token}, format="json").status_code
        == 201
    )
    second = connector.post(URL, {"grant_type": GRANT, "assertion": token}, format="json")
    assert second.json()["error"]["code"] == "assertion_replayed"


@pytest.mark.django_db
def test_an_assertion_for_another_system_is_refused(connector, provider, rosa, keypair, jwks):
    answer = connector.post(
        URL,
        {
            "grant_type": GRANT,
            "assertion": assertion_for(keypair, "gcc-0042", audience="https://otro.example"),
        },
        format="json",
    )
    assert answer.json()["error"]["code"] == "assertion_wrong_audience"


@pytest.mark.django_db
def test_a_signature_from_another_key_is_refused(connector, provider, rosa, jwks):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = assertion_for((other, other.public_key()), "gcc-0042")
    answer = connector.post(URL, {"grant_type": GRANT, "assertion": forged}, format="json")
    assert answer.json()["error"]["code"] == "assertion_invalid"


@pytest.mark.django_db
def test_somebody_who_is_not_there_is_refused(connector, provider, keypair, jwks):
    answer = connector.post(
        URL, {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-nadie")}, format="json"
    )
    assert answer.json()["error"]["code"] == "employee_not_found"


@pytest.mark.django_db
def test_another_companys_credential_gets_nobody_here(provider, rosa, keypair, jwks):
    other = Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")
    SsoProvider.objects.create(tenant=other, name="GCC", issuer=ISSUER, may_act_for_people=True)
    intruder = credential(other, ApplicationScope.PUNCH_SELF)

    answer = intruder.post(
        URL, {"grant_type": GRANT, "assertion": assertion_for(keypair, "gcc-0042")}, format="json"
    )
    assert answer.json()["error"]["code"] == "employee_not_found"


@pytest.mark.django_db
def test_only_the_jwt_bearer_grant_is_accepted(connector, provider, rosa, keypair, jwks):
    answer = connector.post(
        URL,
        {"grant_type": "password", "assertion": assertion_for(keypair, "gcc-0042")},
        format="json",
    )
    assert answer.status_code == 400


def test_las_claves_se_piden_donde_dice_el_proveedor(provider, monkeypatch):
    """Con el campo en blanco, la URL sale del documento de descubrimiento.

    Antes se derivaba `issuer + /.well-known/jwks.json`, que no es un sitio que
    defina ningún estándar: contra un proveedor que publica sus claves en otra ruta
    ---y la anuncia, como manda OpenID Connect Discovery--- esto daba 404 y el
    rechazo decía «no se han podido obtener las claves», que no señala a la URL.
    """
    from apps.tenants import sso

    provider.jwks_uri = ""
    provider.save(update_fields=["jwks_uri"])
    monkeypatch.setattr(
        sso,
        "discovery",
        lambda p: {"issuer": p.issuer, "jwks_uri": "https://gcc.example/o/jwks.json"},
    )

    assert sso.keys_url(provider) == "https://gcc.example/o/jwks.json"


def test_el_campo_manda_sobre_el_descubrimiento(provider, monkeypatch):
    """Y quien lo rellena a mano ---una instalación sin descubrimiento--- gana."""
    from apps.tenants import sso

    provider.jwks_uri = "https://gcc.example/claves-a-mano"
    provider.save(update_fields=["jwks_uri"])

    def no_deberia_llamarse(p):
        raise AssertionError("con el campo puesto no hace falta preguntar al proveedor")

    monkeypatch.setattr(sso, "discovery", no_deberia_llamarse)

    assert sso.keys_url(provider) == "https://gcc.example/claves-a-mano"
