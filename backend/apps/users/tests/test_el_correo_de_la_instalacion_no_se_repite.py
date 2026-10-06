"""Una cuenta de la instalación y una persona de empresa no quedan activas con el mismo correo.

La regla solo la miraba el alta de cuentas de la instalación. Por el otro lado
---el alta de una empresa, el alta o el cambio de correo de una persona, las
reactivaciones, el empuje de una aplicación, el comando de la primera cuenta---
el choque se creaba sin que nadie dijera nada.

Entre empresas distintas el correo repetido sigue permitido: lo resuelve el
identificador fiscal.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

CORREO = "comun@example.com"
CLAVE = "a-sufficiently-long-password"


@pytest.fixture
def acme():
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def jefa(acme):
    with tenant_context(acme.id):
        return User.objects.create_user(
            email="jefa@acme.example", password=CLAVE, tenant=acme, role=Role.ADMIN
        )


def de_la_instalacion(correo=CORREO, **extra):
    return User.objects.create_user(
        email=correo, password=CLAVE, tenant=None, is_superuser=True, is_staff=True, **extra
    )


def como(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def de_acme(acme, correo=CORREO, **extra):
    with tenant_context(acme.id):
        return User.objects.create_user(email=correo, password=CLAVE, tenant=acme, **extra)


# ------------------------------------------------------- personas de empresa


def test_el_alta_de_empresa_no_usa_el_correo_de_la_instalacion():
    de_la_instalacion()
    respuesta = APIClient().post(
        "/api/auth/register/",
        {
            "company_name": "Nueva",
            "tax_id": "B99999999",
            "email": CORREO.upper(),
            "password": CLAVE,
            "first_name": "N",
            "last_name": "N",
        },
        format="json",
    )
    assert respuesta.status_code == 400
    assert "email" in respuesta.json()["error"]["details"]
    assert not Tenant.objects.filter(tax_id="B99999999").exists()


def test_el_alta_de_empresa_desde_la_instalacion_tampoco():
    yo = de_la_instalacion("yo@ejemplo.test")
    de_la_instalacion()
    respuesta = como(yo).post(
        "/api/platform/companies/",
        {
            "company_name": "Nueva",
            "tax_id": "B99999999",
            "email": CORREO,
            "first_name": "N",
            "last_name": "N",
        },
        format="json",
    )
    assert respuesta.status_code == 400


def test_el_alta_de_una_persona_no_usa_el_correo_de_la_instalacion(jefa):
    de_la_instalacion()
    respuesta = como(jefa).post(
        "/api/employees/", {"email": CORREO, "first_name": "P", "last_name": "Q"}, format="json"
    )
    assert respuesta.status_code == 400
    assert "email" in respuesta.json()["error"]["details"]


def test_ni_el_cambio_de_correo(acme, jefa):
    de_la_instalacion()
    alguien = de_acme(acme, correo="alguien@acme.example")
    respuesta = como(jefa).patch(f"/api/employees/{alguien.id}/", {"email": CORREO}, format="json")
    assert respuesta.status_code == 400


def test_ni_reactivar_a_quien_ya_lo_tenia(acme, jefa):
    alguien = de_acme(acme, is_active=False)
    de_la_instalacion()
    respuesta = como(jefa).patch(
        f"/api/employees/{alguien.id}/", {"is_active": True}, format="json"
    )
    assert respuesta.status_code == 400
    alguien.refresh_from_db()
    assert alguien.is_active is False


def test_entre_empresas_el_correo_sigue_pudiendo_repetirse(acme, jefa):
    globex = Tenant.objects.create(name="Globex", tax_id="B22222222")
    de_acme(globex)
    respuesta = como(jefa).post(
        "/api/employees/", {"email": CORREO, "first_name": "P", "last_name": "Q"}, format="json"
    )
    assert respuesta.status_code == 201, respuesta.content


def test_el_empuje_de_una_aplicacion_tampoco(acme):
    de_la_instalacion()
    with tenant_context(acme.id):
        aplicacion = Application.objects.create(
            tenant=acme, name="Gestión", scopes=[str(ApplicationScope.WRITE_PEOPLE)]
        )
        _credencial, secreto = ApplicationCredential.issue(aplicacion)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {secreto}")
    respuesta = api.put(
        "/api/app/people/EMP-1/", {"email": CORREO, "first_name": "P"}, format="json"
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "email_taken"
    assert not User.objects.filter(tenant=acme, email=CORREO).exists()


# ------------------------------------------------- cuentas de la instalación


def test_reactivar_una_cuenta_de_la_instalacion_mira_el_correo(acme):
    yo = de_la_instalacion("yo@ejemplo.test")
    vieja = de_la_instalacion(is_active=False)
    de_acme(acme)

    respuesta = como(yo).patch(f"/api/platform/admins/{vieja.id}/", {"is_active": True})
    assert respuesta.status_code == 400
    vieja.refresh_from_db()
    assert vieja.is_active is False


def test_la_contrasena_nueva_que_reactiva_tambien(acme):
    yo = de_la_instalacion("yo@ejemplo.test")
    vieja = de_la_instalacion(is_active=False)
    de_acme(acme)

    respuesta = como(yo).post(f"/api/platform/admins/{vieja.id}/password/")
    assert respuesta.status_code == 400
    vieja.refresh_from_db()
    assert vieja.is_active is False


def test_la_contrasena_nueva_de_una_activa_no_pregunta_nada(acme):
    """Si ya está activa no se reactiva nada, y bloquearla dejaría a alguien sin entrar."""
    yo = de_la_instalacion("yo@ejemplo.test")
    otra = de_la_instalacion("otra@ejemplo.test")
    respuesta = como(yo).post(f"/api/platform/admins/{otra.id}/password/")
    assert respuesta.status_code == 200, respuesta.content


def test_el_comando_de_la_primera_cuenta_tambien(acme):
    de_acme(acme)
    with pytest.raises(CommandError):
        call_command(
            "create_installation_admin", "--email", CORREO, "--first-name", "A", "--last-name", "B"
        )
    assert not User.objects.filter(email=CORREO, tenant__isnull=True).exists()


# ------------------------------------------- un choque que ya existía antes


def test_un_choque_de_antes_no_deja_la_ficha_sin_poder_editarse(acme, jefa):
    alguien = de_acme(acme)
    de_la_instalacion()
    respuesta = como(jefa).patch(
        f"/api/employees/{alguien.id}/", {"first_name": "Otro"}, format="json"
    )
    assert respuesta.status_code == 200, respuesta.content


def test_ni_deja_al_conector_sin_poder_actualizarla(acme):
    de_acme(acme, employee_id="EMP-1")
    de_la_instalacion()
    with tenant_context(acme.id):
        aplicacion = Application.objects.create(
            tenant=acme, name="Gestión", scopes=[str(ApplicationScope.WRITE_PEOPLE)]
        )
        _credencial, secreto = ApplicationCredential.issue(aplicacion)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {secreto}")
    respuesta = api.put(
        "/api/app/people/EMP-1/", {"email": CORREO, "first_name": "Otro"}, format="json"
    )
    assert respuesta.status_code == 200, respuesta.content
