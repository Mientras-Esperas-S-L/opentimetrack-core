"""Una entrada de soporte dura dos horas, se renueve o no.

Quien la abre fija el refresco a dos horas, pero la renovación llamaba a
`set_exp()` sin plazo y simplejwt le ponía el de una sesión normal: siete días.
Bastaba un refresco para que la puerta de «un rato» quedara abierta una semana.

Y la sesión es de la cuenta de soporte de la empresa, no de la de la instalación
que entró, así que desactivar esta no la cerraba.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.tenants.models import Tenant
from apps.tenants.platform_views import SUPPORT_SESSION
from apps.users.models import User

pytestmark = pytest.mark.django_db

INICIO = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


@pytest.fixture
def empresa():
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def plataforma():
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )


def entrar_como_soporte(plataforma, empresa) -> dict:
    api = APIClient()
    api.force_authenticate(user=plataforma)
    respuesta = api.post(f"/api/platform/companies/{empresa.id}/support/")
    assert respuesta.status_code == 200, respuesta.content
    return respuesta.json()


def renovar(refresco):
    return APIClient().post("/api/auth/refresh/", {"refresh": refresco}, format="json")


def test_renovar_no_alarga_la_entrada_mas_alla_de_las_dos_horas(plataforma, empresa):
    with freeze_time(INICIO):
        sesion = entrar_como_soporte(plataforma, empresa)
    final = INICIO + SUPPORT_SESSION

    with freeze_time(INICIO + timedelta(minutes=30)):
        renovada = renovar(sesion["refresh"])
        assert renovada.status_code == 200, renovada.content
        refresco = RefreshToken(renovada.json()["refresh"])
        acceso = AccessToken(renovada.json()["access"])
    assert refresco["exp"] == int(final.timestamp())
    assert acceso["exp"] <= int(final.timestamp())
    assert refresco["support_by"] == plataforma.email

    # Pasadas las dos horas, el refresco renovado ya no vale.
    with freeze_time(final + timedelta(minutes=1)):
        assert renovar(renovada.json()["refresh"]).status_code != 200


def test_el_acceso_renovado_tampoco_pasa_del_final(plataforma, empresa, settings):
    settings.SIMPLE_JWT = {**settings.SIMPLE_JWT, "ACCESS_TOKEN_LIFETIME": timedelta(hours=1)}
    with freeze_time(INICIO):
        sesion = entrar_como_soporte(plataforma, empresa)

    with freeze_time(INICIO + timedelta(minutes=110)):
        renovada = renovar(sesion["refresh"])
        assert renovada.status_code == 200, renovada.content
    acceso = AccessToken(renovada.json()["access"], verify=False)
    assert acceso["exp"] <= int((INICIO + SUPPORT_SESSION).timestamp())


def test_si_quien_entro_ya_no_esta_activo_no_se_renueva(plataforma, empresa):
    sesion = entrar_como_soporte(plataforma, empresa)
    plataforma.is_active = False
    plataforma.save()

    assert renovar(sesion["refresh"]).status_code != 200


def test_una_sesion_normal_sigue_renovandose_su_semana(empresa):
    persona = User.objects.create_user(
        email="ana@example.com", password="a-sufficiently-long-password", tenant=empresa
    )
    with freeze_time(INICIO):
        entrada = APIClient().post(
            "/api/auth/token/",
            {"email": persona.email, "password": "a-sufficiently-long-password"},
            format="json",
        )
    with freeze_time(INICIO + timedelta(days=1)):
        renovada = renovar(entrada.json()["refresh"])
        assert renovada.status_code == 200
    refresco = RefreshToken(renovada.json()["refresh"], verify=False)
    assert refresco["exp"] > int((INICIO + timedelta(days=6)).timestamp())
