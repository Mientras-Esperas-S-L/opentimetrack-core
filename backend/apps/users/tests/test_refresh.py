"""Renovar la sesión sin volver a escribir la contraseña.

Faltaba entero: el refresco se entregaba, se guardaba y no había dónde
canjearlo, así que la sesión moría a los quince minutos.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


def sign_in(worker):
    return (
        APIClient()
        .post("/api/auth/token/", {"email": worker.email, "password": PASSWORD}, format="json")
        .json()
    )


@pytest.mark.django_db
def test_a_refresh_token_buys_a_new_access_token(worker):
    session = sign_in(worker)
    answer = APIClient().post("/api/auth/refresh/", {"refresh": session["refresh"]}, format="json")
    assert answer.status_code == 200
    assert answer.json()["access"]
    # Y el nuevo sirve para pedir algo de verdad.
    fresh = APIClient()
    fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {answer.json()['access']}")
    assert fresh.get("/api/auth/me/").status_code == 200


@pytest.mark.django_db
def test_the_refresh_token_rotates_and_the_old_one_dies(worker):
    """Un token que se filtra vale un solo uso, y usarlo dos veces es lo que
    delata el robo."""
    session = sign_in(worker)
    renewed = (
        APIClient()
        .post("/api/auth/refresh/", {"refresh": session["refresh"]}, format="json")
        .json()
    )

    assert renewed["refresh"] != session["refresh"]
    again = APIClient().post("/api/auth/refresh/", {"refresh": session["refresh"]}, format="json")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "session_expired"


@pytest.mark.django_db
def test_a_made_up_token_says_the_same_as_an_expired_one(worker):
    """Distinguirlos diría si un token llegó a existir."""
    answer = APIClient().post("/api/auth/refresh/", {"refresh": "inventado"}, format="json")
    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "session_expired"


@pytest.mark.django_db
def test_signing_out_kills_the_refresh_token(worker):
    session = sign_in(worker)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access']}")
    assert (
        c.post("/api/auth/logout/", {"refresh": session["refresh"]}, format="json").status_code
        == 204
    )

    # Y ya no se puede renovar con él: cerrar sesión cierra la sesión.
    assert (
        APIClient()
        .post("/api/auth/refresh/", {"refresh": session["refresh"]}, format="json")
        .status_code
        == 409
    )


@pytest.mark.django_db
def test_renewing_does_not_share_the_login_bucket(worker, settings):
    """Detrás de un NAT, una oficina entera renueva desde la misma IP.

    Con la cubeta del login --- cinco por minuto y anónima, o sea por IP --- la
    sexta persona en abrir la aplicación por la mañana se habría encontrado con
    la sesión cerrada teniéndola viva. Y al volver a entrar habría gastado la
    misma cubeta.
    """
    from apps.users.views import RefreshView, SignInView

    assert RefreshView.throttle_scope != SignInView.throttle_scope
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    login = int(rates["login"].split("/")[0])
    renewal = int(rates[RefreshView.throttle_scope].split("/")[0])
    assert renewal > login


@pytest.mark.django_db
def test_quien_ya_no_esta_de_alta_no_renueva(company, worker):
    """Dar de baja a alguien cerraba su acceso pero no su sesión.

    La renovación miraba el token y no a la persona: contestaba **200** con un
    acceso recién emitido para quien acababa de ser dado de baja, e igual para
    quien ya ni existía en la base.

    Nadie entraba con él ---la autenticación sí comprueba `is_active`, y todo
    respondía 401---, así que no era acceso indebido. Era una respuesta que
    dice «bien», que es la familia de fallo que más caro sale: la propia suite
    de navegador dio por viva una sesión guardada contra una base resembrada, y
    siete pruebas de aislamiento fallaron señalando al producto.

    Se contesta lo mismo que a un token caducado o falso, a propósito.
    Distinguirlos diría si esa cuenta llegó a existir.
    """
    con_ella_de_alta = sign_in(worker)

    # El contraste, primero: mientras está de alta, esto renueva. Sin él,
    # «rechaza a quien está de baja» y «rechaza a todo el mundo» se ven igual.
    assert (
        APIClient()
        .post("/api/auth/refresh/", {"refresh": con_ella_de_alta["refresh"]}, format="json")
        .status_code
        == 200
    )

    de_nuevo = sign_in(worker)
    with tenant_context(company.id):
        worker.is_active = False
        worker.save(update_fields=["is_active"])

    respuesta = APIClient().post(
        "/api/auth/refresh/", {"refresh": de_nuevo["refresh"]}, format="json"
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "session_expired"


@pytest.mark.django_db
def test_quien_ya_no_esta_en_la_base_tampoco(company, worker):
    """El mismo caso pero borrada, que es como quedan las sesiones tras sembrar.

    Es el que destapó todo: los ficheros de sesión de la suite guardaban tokens
    de personas que el resembrado había sustituido por otras con otro
    identificador, y la comprobación de «¿sigue valiendo?» ---que renueva
    contra el servidor a propósito, para no fiarse de la fecha--- contestaba
    que sí.
    """
    session = sign_in(worker)
    with tenant_context(company.id):
        User.objects.filter(pk=worker.pk).delete()

    respuesta = APIClient().post(
        "/api/auth/refresh/", {"refresh": session["refresh"]}, format="json"
    )
    assert respuesta.status_code == 409
