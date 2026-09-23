"""Cambiar la contraseña propia estando dentro.

No existía: la única forma era el enlace de «He olvidado mi contraseña», que
depende de que el correo salga. En producción no salía (23/09/2026), y quien
recibía una contraseña generada ---una cuenta de la instalación, el primer
administrador de una empresa--- no tenía forma de cambiarla.
"""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationScope, Tenant
from apps.users.models import Role, User
from apps.users.serializers import issue_tokens
from config.settings import base

pytestmark = pytest.mark.django_db

AHORA = "La-de-ahora-larga-1"
NUEVA = "Otra-bien-distinta-2"


@pytest.fixture
def jefa():
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    with tenant_context(empresa.id):
        return User.objects.create_user(
            email="jefa@acme.test", password=AHORA, tenant=empresa, role=Role.ADMIN
        )


@pytest.fixture
def instalacion():
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password=AHORA,
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )


def con_sesion(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return api


def cambiar(api, actual=AHORA, nueva=NUEVA):
    return api.post(
        "/api/auth/password/", {"current_password": actual, "new_password": nueva}, format="json"
    )


@pytest.mark.parametrize("quien", ["jefa", "instalacion"])
def test_cambia_la_suya_y_entra_con_la_nueva(quien, request):
    """También la cuenta de la instalación, que no tiene empresa."""
    user = request.getfixturevalue(quien)
    respuesta = cambiar(con_sesion(user))

    assert respuesta.status_code == 200, respuesta.data
    assert respuesta.data["access"] and respuesta.data["refresh"]
    user.refresh_from_db()
    assert user.check_password(NUEVA) and not user.check_password(AHORA)


def test_sin_la_de_ahora_no_la_cambia(jefa):
    """Un ordenador con la sesión abierta no basta para quedarse con la cuenta."""
    respuesta = cambiar(con_sesion(jefa), actual="no-es-esta-para-nada")
    assert respuesta.status_code == 400
    assert "current_password" in respuesta.data["error"]["details"]
    jefa.refresh_from_db()
    assert jefa.check_password(AHORA)


def test_una_debil_no_pasa(jefa):
    """Con los validadores de producción: los ajustes de desarrollo, que son los de
    las pruebas, los vacían, y sin esto la prueba daría por buena «123456789012»."""
    with override_settings(AUTH_PASSWORD_VALIDATORS=base.AUTH_PASSWORD_VALIDATORS):
        respuesta = cambiar(con_sesion(jefa), nueva="123456789012")
    assert respuesta.status_code == 400
    assert "new_password" in respuesta.data["error"]["details"]


def test_cierra_las_demas_sesiones(jefa):
    """Quien cambia su clave suele creer que se la han visto."""
    otra = RefreshToken.for_user(jefa)
    assert cambiar(con_sesion(jefa)).status_code == 200

    renovar = APIClient().post("/api/auth/refresh/", {"refresh": str(otra)}, format="json")
    assert renovar.status_code >= 400


def test_una_federada_no_tiene_contrasena_que_cambiar(jefa):
    jefa.oidc_sub = "sub-de-la-jefa"
    jefa.save(update_fields=["oidc_sub"])
    respuesta = cambiar(con_sesion(jefa))
    assert respuesta.status_code >= 400
    assert respuesta.data["error"]["code"] == "federated_account"


def test_una_aplicacion_no_cambia_la_contrasena_de_nadie(jefa):
    with tenant_context(jefa.tenant_id):
        app = Application.objects.create(
            tenant=jefa.tenant, name="GreenCity", scopes=[s.value for s in ApplicationScope]
        )
    sesion = issue_tokens(jefa, acting_application=app)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {sesion['access']}")
    assert cambiar(api).status_code == 403
    jefa.refresh_from_db()
    assert jefa.check_password(AHORA)
