"""Dar de baja con `is_active: false` es la misma baja que la del botón.

La pantalla tiene dos caminos para dar de baja: el botón de cada fila, que va por
`DELETE`, y la baja en lote, que manda `PATCH {"is_active": false}` a cada
persona marcada. El primero pasaba por las reglas de la baja; el segundo solo
apagaba `is_active` y cerraba sesiones. Por el `PATCH`:

- la cuenta de soporte podía dar de baja a la única administradora, y la empresa
  quedaba sin nadie dentro capaz de administrarla;
- una administradora podía darse de baja a sí misma;
- la baja no dejaba fecha de fin de contrato ni su asiento en el registro, así
  que nada de lo que razona por fechas ---el cuadrante, las ausencias--- se
  enteraba.

Los códigos y la fecha se escriben aquí a mano, sin sacarlos del módulo que se
prueba.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog
from apps.common.clock import local_today
from apps.common.models import tenant_context
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


def como_soporte(mundo):
    respuesta = como(mundo["plataforma"]).post(
        f"/api/platform/companies/{mundo['empresa'].id}/support/"
    )
    assert respuesta.status_code == 200, respuesta.content
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.json()['access']}")
    return cliente


def baja(cliente, persona):
    return cliente.patch(f"/api/employees/{persona.id}/", {"is_active": False}, format="json")


def test_soporte_no_deja_a_la_empresa_sin_su_ultima_administradora(mundo):
    respuesta = baja(como_soporte(mundo), mundo["jefa"])

    assert respuesta.status_code == 409, respuesta.content
    assert respuesta.json()["error"]["code"] == "last_administrator"
    mundo["jefa"].refresh_from_db()
    assert mundo["jefa"].is_active is True
    assert mundo["jefa"].contract_end is None


def test_nadie_se_da_de_baja_a_si_mismo_por_la_ficha(mundo):
    otra = User.objects.create_user(
        email="otra@example.com", password=PASSWORD, tenant=mundo["empresa"], role=Role.ADMIN
    )

    respuesta = baja(como(otra), otra)

    assert respuesta.status_code == 409, respuesta.content
    assert respuesta.json()["error"]["code"] == "cannot_deactivate_yourself"
    otra.refresh_from_db()
    assert otra.is_active is True


def test_la_baja_por_la_ficha_deja_fecha_y_asiento(mundo, django_capture_on_commit_callbacks):
    ana = mundo["ana"]

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = baja(como(mundo["jefa"]), ana)

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["is_active"] is False
    ana.refresh_from_db()
    assert ana.is_active is False
    assert ana.contract_end == local_today(ana)
    asientos = AuditLog.objects.filter(tenant=mundo["empresa"], target_id=str(ana.id))
    assert list(asientos.values_list("action", flat=True)) == [AuditAction.PERSON_DEACTIVATED]


def test_si_viene_algo_mas_tambien_se_guarda_y_se_anota(mundo, django_capture_on_commit_callbacks):
    ana = mundo["ana"]

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = como(mundo["jefa"]).patch(
            f"/api/employees/{ana.id}/",
            {"is_active": False, "first_name": "Ana María"},
            format="json",
        )

    assert respuesta.status_code == 200, respuesta.content
    ana.refresh_from_db()
    assert (ana.is_active, ana.first_name) == (False, "Ana María")
    acciones = set(
        AuditLog.objects.filter(tenant=mundo["empresa"], target_id=str(ana.id)).values_list(
            "action", flat=True
        )
    )
    assert acciones == {AuditAction.PERSON_DEACTIVATED, AuditAction.PERSON_UPDATED}


def test_reactivar_sigue_igual(mundo, django_capture_on_commit_callbacks):
    ana = mundo["ana"]
    assert baja(como(mundo["jefa"]), ana).status_code == 200

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = como(mundo["jefa"]).patch(
            f"/api/employees/{ana.id}/", {"is_active": True}, format="json"
        )

    assert respuesta.status_code == 200, respuesta.content
    ana.refresh_from_db()
    assert ana.is_active is True
    assert AuditLog.objects.filter(
        tenant=mundo["empresa"], target_id=str(ana.id), action=AuditAction.PERSON_REACTIVATED
    ).exists()
