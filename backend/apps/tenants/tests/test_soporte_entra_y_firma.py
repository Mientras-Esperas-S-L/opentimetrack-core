"""Soporte de la instalación entra en una empresa: invisible en sus listas, no en su registro.

Para ayudar o configurar cosas a quien no sabe. Administra como su administración,
pero no sale en Personas ni cuenta en ninguna cifra. Lo que hace sí sale en el
registro de actividad, como «Soporte» y con la cuenta de la instalación que entró:
un cambio en el registro de jornada sin autor no se sostiene ante la Inspección.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog, PlatformAction, PlatformAuditEntry
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com", password=PASSWORD, tenant=empresa, role=Role.ADMIN
        )
        ana = User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=empresa, first_name="Ana"
        )
    plataforma = User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )
    return {"empresa": empresa, "jefa": jefa, "ana": ana, "plataforma": plataforma}


def como(persona):
    cliente = APIClient()
    cliente.force_authenticate(user=persona)
    return cliente


def entrar(mundo):
    respuesta = como(mundo["plataforma"]).post(
        f"/api/platform/companies/{mundo['empresa'].id}/support/"
    )
    assert respuesta.status_code == 200, respuesta.content
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.json()['access']}")
    return cliente


@pytest.mark.django_db
def test_solo_la_instalacion_abre_la_puerta(mundo):
    url = f"/api/platform/companies/{mundo['empresa'].id}/support/"
    assert como(mundo["jefa"]).post(url).status_code == 403
    assert APIClient().post(url).status_code == 401


@pytest.mark.django_db
def test_entra_como_administracion_y_no_sale_en_las_listas(mundo):
    soporte = entrar(mundo)
    yo = soporte.get("/api/auth/me/").json()["user"]
    assert yo["is_support"] is True
    assert yo["role"] == "ADMIN"

    correos = {p["email"] for p in soporte.get("/api/employees/").json()["results"]}
    assert correos == {"jefa@example.com", "ana@example.com"}
    assert soporte.get(f"/api/employees/{yo['id']}/").status_code == 404
    # Ni para la propia empresa.
    lista = como(mundo["jefa"]).get("/api/employees/").json()["results"]
    assert all(not p["is_support"] for p in lista)

    admins = como(mundo["plataforma"]).get(f"/api/platform/companies/{mundo['empresa'].id}/admins/")
    assert [a["email"] for a in admins.json()["admins"]] == ["jefa@example.com"]

    cuenta = User.objects.get(is_support=True)
    assert cuenta not in User.objects.workforce()
    assert not cuenta.has_usable_password()


@pytest.mark.django_db
def test_lo_que_hace_queda_firmado_como_soporte(mundo, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        soporte = entrar(mundo)
    with django_capture_on_commit_callbacks(execute=True):
        cambio = soporte.patch(
            f"/api/employees/{mundo['ana'].id}/", {"first_name": "Ana María"}, format="json"
        )
    assert cambio.status_code == 200, cambio.content

    asientos = AuditLog.objects.filter(tenant=mundo["empresa"])
    entrada = asientos.get(action=AuditAction.SUPPORT_ENTERED)
    assert entrada.actor_label == "Soporte (plataforma@ejemplo.test)"
    hecho = asientos.get(action=AuditAction.PERSON_UPDATED)
    assert hecho.actor_label == "Soporte (plataforma@ejemplo.test)"
    assert PlatformAuditEntry.objects.filter(action=PlatformAction.SUPPORT_ENTERED).exists()


@pytest.mark.django_db
def test_soporte_no_ficha_ni_cuenta_como_la_ultima_administradora(mundo):
    entrar(mundo)
    cuenta = User.objects.get(is_support=True)
    with tenant_context(mundo["empresa"].id), pytest.raises(BusinessRuleError):
        register_punch(employee=cuenta, company=mundo["empresa"])

    # Con soporte dentro, la jefa sigue siendo la única administradora.
    quitar = como(mundo["jefa"]).patch(
        f"/api/employees/{mundo['jefa'].id}/", {"role": "EMPLOYEE"}, format="json"
    )
    assert quitar.status_code == 409


@pytest.mark.django_db
def test_una_empresa_desactivada_no_se_abre(mundo):
    mundo["empresa"].is_active = False
    mundo["empresa"].save()
    respuesta = como(mundo["plataforma"]).post(
        f"/api/platform/companies/{mundo['empresa'].id}/support/"
    )
    assert respuesta.status_code == 400
