"""Entrar con el proveedor de identidad de la empresa.

Lo que se fija aquí: que el descubrimiento no chive quién trabaja aquí, que el
navegador va con PKCE y estado de un solo uso, que un token firmado por otro no entra,
que el sujeto ancla la identidad y el correo solo la encuentra la primera vez, y que
cuando el proveedor dice que una sesión se acabó, se acaba.
"""

from __future__ import annotations

import base64
import datetime as dt
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.tenants.identity import SsoDomain, SsoProvider
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
ISSUER = "https://idp.example"
CLIENT_ID = "ott-en-casa-del-cliente"
FERNET_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()
#: El secreto que la aplicación web guarda en el navegador al empezar la entrada.
PRUEBA = "el-secreto-de-este-navegador-0123456789abcdef"


@pytest.fixture(autouse=True)
def _limpio():
    cache.clear()
    with override_settings(
        FIELD_ENCRYPTION_KEY=FERNET_KEY,
        SSO_REDIRECT_URI="https://ott.example/api/auth/sso/callback/",
    ):
        yield
    cache.clear()


@pytest.fixture(scope="module")
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key()


@pytest.fixture
def idp(monkeypatch, keypair):
    """Un proveedor de mentira que sirve su documento y sus claves sin red."""
    _private, public = keypair
    numbers = public.public_numbers()

    def b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    jwk = {
        "kty": "RSA",
        "kid": "idp-1",
        "use": "sig",
        "alg": "RS256",
        "n": b64(numbers.n),
        "e": b64(numbers.e),
    }
    documento = {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
    }

    from apps.tenants import sso

    monkeypatch.setattr(sso, "_get_json", lambda url: documento)

    class FakeJWKClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            return jwt.PyJWK.from_dict(jwk)

    monkeypatch.setattr(jwt, "PyJWKClient", FakeJWKClient)
    return documento


def id_token(
    keypair,
    *,
    sub="sub-de-marta",
    email="marta@contrata.example",
    nonce="",
    audience=CLIENT_ID,
    issuer=ISSUER,
    **extra,
):
    private, _public = keypair
    now = dt.datetime.now(tz=dt.UTC)
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=5)).timestamp()),
        **extra,
    }
    if nonce:
        payload["nonce"] = nonce
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": "idp-1"})


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="Contrata SL", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def provider(company):
    with tenant_context(company.id):
        provider = SsoProvider.objects.create(
            tenant=company,
            name="Entra de la contrata",
            issuer=ISSUER,
            client_id=CLIENT_ID,
            client_secret="un-secreto-que-hay-que-poder-leer",
        )
        SsoDomain.objects.create(tenant=company, provider=provider, domain="contrata.example")
    return provider


# ------------------------------------------------------------ el secreto guardado


@pytest.mark.django_db
def test_el_secreto_no_se_guarda_en_claro(provider):
    """Un volcado de la base no puede llevarse el secreto del proveedor."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT client_secret FROM tenants_ssoprovider WHERE id = %s", [str(provider.pk)]
        )
        crudo = cursor.fetchone()[0]

    assert crudo.startswith("enc:v1:")
    assert "un-secreto" not in crudo
    # Y vuelve legible para quien lo necesita, que es el canje del código.
    with tenant_context(provider.tenant_id):
        guardado = SsoProvider.objects.get(pk=provider.pk)
    assert guardado.client_secret == "un-secreto-que-hay-que-poder-leer"


# ------------------------------------------------------------- el descubrimiento


@pytest.mark.django_db
def test_el_dominio_dice_dónde_se_entra(provider):
    answer = APIClient().post(
        "/api/auth/sso/discover/", {"email": "marta@contrata.example"}, format="json"
    )

    assert answer.status_code == 200
    assert answer.json() == {
        "sso": True,
        "provider": "Entra de la contrata",
        "slug": "entra-de-la-contrata",
    }


@pytest.mark.django_db
def test_un_dominio_cualquiera_no_chiva_nada(provider):
    """La misma respuesta para «no hay proveedor» y «no trabaja aquí»."""
    assert APIClient().post(
        "/api/auth/sso/discover/", {"email": "quien@gmail.com"}, format="json"
    ).json() == {"sso": False}


@pytest.mark.django_db
def test_un_proveedor_a_medio_configurar_no_se_ofrece(company):
    """Solo con la parte de navegador puesta: si no, el botón lleva a un error."""
    with tenant_context(company.id):
        a_medias = SsoProvider.objects.create(
            tenant=company, name="A medias", issuer="https://otro.example", may_act_for_people=True
        )
        SsoDomain.objects.create(tenant=company, provider=a_medias, domain="medias.example")

    assert APIClient().post(
        "/api/auth/sso/discover/", {"email": "x@medias.example"}, format="json"
    ).json() == {"sso": False}


# ------------------------------------------------------------------- el flujo


@pytest.mark.django_db
def test_el_navegador_va_con_pkce_y_un_estado_de_un_solo_uso(provider, idp):
    answer = APIClient().get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})

    assert answer.status_code == 302
    params = parse_qs(urlparse(answer["Location"]).query)
    assert params["client_id"] == [CLIENT_ID]
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"] and params["state"] and params["nonce"]

    from apps.tenants import sso

    estado = sso.take_state(params["state"][0])
    assert estado["provider"] == provider.pk
    with pytest.raises(BusinessRuleError):
        # La segunda vez ya no está: reutilizar un estado es repetir una entrada.
        sso.take_state(params["state"][0])


def sesion_de(answer, client):
    """La sesión que trae la vuelta, llegue como llegue.

    Con una aplicación web configurada ---lo normal--- el callback **devuelve el
    navegador a ella** con un vale, y la sesión se recoge canjeándolo. Sin ella
    responde el JSON directamente. Las dos formas acaban en el mismo sitio, y lo que
    estas pruebas miran es lo que hay dentro.
    """
    if answer.status_code == 302:
        vale = parse_qs(urlparse(answer["Location"]).query)["ticket"][0]
        return client.post(
            "/api/auth/sso/ticket/", {"ticket": vale, "proof": PRUEBA}, format="json"
        ).json()
    return answer.json()


@pytest.mark.django_db
def test_vuelve_con_una_sesion_de_esa_persona(provider, idp, keypair, monkeypatch, company):
    with tenant_context(company.id):
        marta = User.objects.create_user(
            email="marta@contrata.example", password=PASSWORD, tenant=company, first_name="Marta"
        )

    client = APIClient()
    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )
    from apps.tenants import sso

    estado = sso.take_state(params["state"][0])
    # El estado se consume al mirarlo, así que se repone para que lo use el callback.
    from django.core.cache import cache as django_cache

    django_cache.set(f"sso:state:{params['state'][0]}", estado, 600)

    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (200, {"id_token": id_token(keypair, nonce=estado["nonce"])}),
    )

    answer = client.get(
        "/api/auth/sso/callback/", {"code": "un-codigo", "state": params["state"][0]}
    )

    body = sesion_de(answer, client)
    assert body["access"] and body["created"] is False
    marta.refresh_from_db()
    assert marta.oidc_sub == "sub-de-marta", "el sujeto queda anclado en la primera entrada"
    assert marta.oidc_issuer == ISSUER


@pytest.mark.django_db
def test_un_token_firmado_por_otro_no_entra(provider, idp, keypair, monkeypatch):
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = APIClient()
    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )

    from apps.tenants import sso

    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (200, {"id_token": id_token((otra, otra.public_key()))}),
    )

    with override_settings(SSO_WEB_URL=""):
        answer = client.get("/api/auth/sso/callback/", {"code": "x", "state": params["state"][0]})
    assert answer.json()["error"]["code"] == "invalid_id_token"


@pytest.mark.django_db
def test_un_token_de_otra_sesion_no_vale_para_esta(provider, idp, keypair, monkeypatch):
    """El nonce ata el token a esta entrada concreta."""
    client = APIClient()
    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )

    from apps.tenants import sso

    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (200, {"id_token": id_token(keypair, nonce="de-otra-entrada")}),
    )

    with override_settings(SSO_WEB_URL=""):
        answer = client.get("/api/auth/sso/callback/", {"code": "x", "state": params["state"][0]})
    assert answer.json()["error"]["code"] == "nonce_mismatch"


@pytest.mark.django_db
def test_sin_alta_al_vuelo_no_entra_quien_no_esta(provider, idp, keypair, monkeypatch):
    client = APIClient()
    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )
    from apps.tenants import sso

    estado = sso.take_state(params["state"][0])
    from django.core.cache import cache as django_cache

    django_cache.set(f"sso:state:{params['state'][0]}", estado, 600)
    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (
            200,
            {
                "id_token": id_token(
                    keypair, sub="nadie", email="nadie@contrata.example", nonce=estado["nonce"]
                )
            },
        ),
    )

    with override_settings(SSO_WEB_URL=""):
        answer = client.get("/api/auth/sso/callback/", {"code": "x", "state": params["state"][0]})
    assert answer.json()["error"]["code"] == "person_not_here"


@pytest.mark.django_db
def test_con_alta_al_vuelo_entra_sin_contraseña_y_sin_permisos(
    provider, idp, keypair, monkeypatch, company
):
    provider.auto_provision = True
    provider.save(update_fields=["auto_provision"])

    client = APIClient()
    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )
    from apps.tenants import sso

    estado = sso.take_state(params["state"][0])
    from django.core.cache import cache as django_cache

    django_cache.set(f"sso:state:{params['state'][0]}", estado, 600)
    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (
            200,
            {
                "id_token": id_token(
                    keypair,
                    sub="nueva",
                    email="nueva@contrata.example",
                    nonce=estado["nonce"],
                    given_name="Nueva",
                )
            },
        ),
    )

    answer = client.get("/api/auth/sso/callback/", {"code": "x", "state": params["state"][0]})

    assert sesion_de(answer, client)["created"] is True
    with tenant_context(company.id):
        nueva = User.objects.get(email="nueva@contrata.example")
    assert nueva.is_federated, "su contraseña es asunto del proveedor"
    assert not nueva.has_usable_password()


# ---------------------------------------------------------- cerrar desde el IdP


@pytest.mark.django_db
def test_el_proveedor_puede_cerrar_la_sesion_de_alguien(provider, idp, keypair, company):
    """Cambiar la contraseña allí porque se la robaron tiene que llegar aquí."""
    from apps.users.serializers import issue_tokens

    with tenant_context(company.id):
        marta = User.objects.create_user(
            email="marta@contrata.example",
            password=PASSWORD,
            tenant=company,
            oidc_sub="sub-de-marta",
        )
    tokens = issue_tokens(marta)

    answer = APIClient().post(
        "/api/auth/sso/logout/",
        {"logout_token": id_token(keypair, sub="sub-de-marta", email="")},
        format="json",
    )

    assert answer.status_code == 200 and answer.json()["sessions_ended"] >= 1
    # El refresco deja de valer, que es lo que se puede revocar sin mirar una lista
    # en cada petición.
    renovar = APIClient().post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert renovar.status_code != 200


@pytest.mark.django_db
def test_un_cierre_de_un_emisor_desconocido_no_cierra_nada(provider, idp, keypair):
    answer = APIClient().post(
        "/api/auth/sso/logout/",
        {"logout_token": id_token(keypair, issuer="https://otro.example", sub="x")},
        format="json",
    )
    assert answer.json()["error"]["code"] == "issuer_not_trusted"


# ------------------------------------------- la vuelta a la aplicación web


def _hasta_el_callback(client, provider, keypair, monkeypatch):
    """Deja el viaje a punto de volver, y devuelve la respuesta del callback."""
    from django.core.cache import cache as django_cache

    from apps.tenants import sso

    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )
    estado = sso.take_state(params["state"][0])
    django_cache.set(f"sso:state:{params['state'][0]}", estado, 600)
    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (200, {"id_token": id_token(keypair, nonce=estado["nonce"])}),
    )
    return client.get("/api/auth/sso/callback/", {"code": "un-codigo", "state": params["state"][0]})


@pytest.mark.django_db
def test_con_aplicacion_web_el_navegador_acaba_en_ella_y_no_en_un_json(
    provider, idp, keypair, monkeypatch, company
):
    """Quien vuelve del proveedor es una persona, no un integrador.

    Sin esto, el viaje acababa en la respuesta de la API: alguien que entra con la
    cuenta de su empresa se quedaba mirando sus propios testigos en un JSON.
    """
    with tenant_context(company.id):
        User.objects.create_user(
            email="marta@contrata.example", password=PASSWORD, tenant=company, first_name="Marta"
        )

    with override_settings(SSO_WEB_URL="https://ott.example"):
        answer = _hasta_el_callback(APIClient(), provider, keypair, monkeypatch)

    assert answer.status_code == 302
    destino = answer["Location"]
    assert destino.startswith("https://ott.example/entrando?ticket=")
    # Y los testigos **no** viajan en esa dirección: acabarían en el historial, en el
    # registro del servidor web y en el `Referer` de la primera imagen de la página.
    assert "access" not in destino and "refresh" not in destino


@pytest.mark.django_db
def test_el_vale_se_cambia_por_la_sesion_una_sola_vez(provider, idp, keypair, monkeypatch, company):
    with tenant_context(company.id):
        User.objects.create_user(
            email="marta@contrata.example", password=PASSWORD, tenant=company, first_name="Marta"
        )

    client = APIClient()
    with override_settings(SSO_WEB_URL="https://ott.example"):
        vuelta = _hasta_el_callback(client, provider, keypair, monkeypatch)
    vale = parse_qs(urlparse(vuelta["Location"]).query)["ticket"][0]

    primera = client.post("/api/auth/sso/ticket/", {"ticket": vale, "proof": PRUEBA}, format="json")
    assert primera.status_code == 200
    assert primera.json()["access"]

    repetida = client.post(
        "/api/auth/sso/ticket/", {"ticket": vale, "proof": PRUEBA}, format="json"
    )
    assert repetida.json()["error"]["code"] == "ticket_unknown", (
        "repetirlo es reutilizar una sesión"
    )


@pytest.mark.django_db
def test_un_vale_inventado_no_da_sesion(provider):
    answer = APIClient().post(
        "/api/auth/sso/ticket/", {"ticket": "me-lo-invento", "proof": PRUEBA}, format="json"
    )

    assert answer.json()["error"]["code"] == "ticket_unknown"


@pytest.mark.django_db
def test_sin_aplicacion_web_configurada_responde_como_siempre(
    provider, idp, keypair, monkeypatch, company
):
    """Una instalación que solo use la API no se entera de este cambio."""
    with tenant_context(company.id):
        User.objects.create_user(
            email="marta@contrata.example", password=PASSWORD, tenant=company, first_name="Marta"
        )

    with override_settings(SSO_WEB_URL=""):
        answer = _hasta_el_callback(APIClient(), provider, keypair, monkeypatch)

    assert answer.status_code == 200
    assert answer.json()["access"]


def test_un_rechazo_vuelve_a_la_pantalla_y_no_a_un_json(client, provider, settings, monkeypatch):
    """Quien vuelve del proveedor es un navegador, no una integración.

    Antes, que no hubiera nadie con esa cuenta dejaba a la persona mirando la
    página de la API con «person_not_here», su traza y su cabecera. Ahora vuelve a
    la pantalla de entrada con el motivo en la dirección, y allí se convierte en
    una frase.
    """
    settings.SSO_WEB_URL = "https://ott.example"

    respuesta = client.get("/api/auth/sso/callback/", {"state": "el-que-sea", "code": "x"})

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].startswith("https://ott.example/?sso_error=")


def test_sin_aplicacion_web_el_rechazo_sigue_siendo_json(client, provider, settings):
    """Una instalación que solo usa la API espera lo de siempre."""
    settings.SSO_WEB_URL = ""

    respuesta = client.get("/api/auth/sso/callback/", {"state": "el-que-sea", "code": "x"})

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"]


def test_una_empresa_desactivada_no_entra_por_su_proveedor(
    provider, idp, keypair, monkeypatch, company, settings
):
    """Con la empresa desactivada, el proveedor abría sesión igual: la sesión moría en
    la primera petición, pero contestar «adelante» a quien no puede entrar es mentir.

    La dirección de la web se fija aquí: en el puesto venía del entorno y en el CI no
    existe, y con ella vacía el rechazo sale como JSON y no como redirección. Así la
    prueba pasó en local y falló en la puerta.
    """
    settings.SSO_WEB_URL = "https://ott.example"
    with tenant_context(company.id):
        User.objects.create_user(
            email="marta@contrata.example", password=PASSWORD, tenant=company, first_name="Marta"
        )
    company.is_active = False
    company.save(update_fields=["is_active"])

    client = APIClient()
    params = parse_qs(
        urlparse(
            client.get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})["Location"]
        ).query
    )
    from django.core.cache import cache as django_cache

    from apps.tenants import sso

    estado = sso.take_state(params["state"][0])
    django_cache.set(f"sso:state:{params['state'][0]}", estado, 600)
    monkeypatch.setattr(
        sso,
        "_post_form",
        lambda url, data: (200, {"id_token": id_token(keypair, nonce=estado["nonce"])}),
    )

    answer = client.get(
        "/api/auth/sso/callback/", {"code": "un-codigo", "state": params["state"][0]}
    )

    # Con la aplicación web configurada, el rechazo vuelve a la pantalla con su motivo.
    assert answer.status_code == 302
    assert answer["Location"].startswith("https://ott.example/?sso_error=company_inactive")
    assert "ticket" not in answer["Location"]


# ------------------------------------- la entrada, atada a su navegador
#
# La entrada forzada con la cuenta de otro: quien tiene cuenta en un proveedor
# empieza una entrada suya, se para antes de volver y manda el enlace a otra
# persona. Sin atar la entrada al navegador que la empezó, esa persona acababa
# dentro de la cuenta de quien lo mandó, y lo que registrara quedaba a su vista.


def _vale(client, provider, keypair, monkeypatch, company):
    with tenant_context(company.id):
        User.objects.create_user(
            email="marta@contrata.example", password=PASSWORD, tenant=company, first_name="Marta"
        )
    with override_settings(SSO_WEB_URL="https://ott.example"):
        vuelta = _hasta_el_callback(client, provider, keypair, monkeypatch)
    return parse_qs(urlparse(vuelta["Location"]).query)["ticket"][0]


@pytest.mark.django_db
def test_un_vale_mandado_a_otro_navegador_no_da_sesion(
    provider, idp, keypair, monkeypatch, company
):
    vale = _vale(APIClient(), provider, keypair, monkeypatch, company)

    # El otro navegador tiene su propio secreto, no el de quien empezó.
    otra = APIClient().post(
        "/api/auth/sso/ticket/",
        {"ticket": vale, "proof": "el-secreto-de-otro-navegador-0123456789abcdef"},
        format="json",
    )
    assert "access" not in otra.json()
    assert otra.json()["error"]["code"] == "ticket_other_browser"


@pytest.mark.django_db
def test_un_vale_que_salio_de_su_navegador_ya_no_vale_ni_en_el_suyo(
    provider, idp, keypair, monkeypatch, company
):
    """Se gasta aunque la prueba no case: si no, bastaría con probar hasta acertar."""
    client = APIClient()
    vale = _vale(client, provider, keypair, monkeypatch, company)

    mal = client.post(
        "/api/auth/sso/ticket/", {"ticket": vale, "proof": "otra-cosa-" + "x" * 32}, format="json"
    )
    assert mal.json()["error"]["code"] == "ticket_other_browser"

    bien = client.post("/api/auth/sso/ticket/", {"ticket": vale, "proof": PRUEBA}, format="json")
    assert bien.json()["error"]["code"] == "ticket_unknown"


@pytest.mark.django_db
def test_con_web_no_se_empieza_una_entrada_sin_atar(provider, idp, settings):
    """Si no, quien quisiera forzar la entrada empezaría la suya sin secreto."""
    settings.SSO_WEB_URL = "https://ott.example"

    for sin in ({}, {"binding": "corto"}, {"binding": "con espacios " * 4}):
        answer = APIClient().get(f"/api/auth/sso/start/{provider.slug}/", sin)
        assert answer.status_code == 302
        assert answer["Location"] == "https://ott.example/?sso_error=start_from_sign_in"


@pytest.mark.django_db
def test_el_secreto_no_se_guarda_tal_cual(provider, idp):
    """Solo su huella: un volcado de la caché no le da a nadie una prueba."""
    answer = APIClient().get(f"/api/auth/sso/start/{provider.slug}/", {"binding": PRUEBA})
    state = parse_qs(urlparse(answer["Location"]).query)["state"][0]

    from apps.tenants import sso

    guardado = sso.take_state(state)
    assert PRUEBA not in str(guardado)
    assert guardado["binding"]
