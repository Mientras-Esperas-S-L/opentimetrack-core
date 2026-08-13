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
