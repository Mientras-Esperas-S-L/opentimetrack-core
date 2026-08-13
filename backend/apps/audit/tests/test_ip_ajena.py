"""La IP de una línea del registro no es de quien la lee.

El registro se le enseña a cada persona con lo suyo ---lo que hizo y lo que le
hicieron--- y la segunda mitad trae líneas donde actuó otro. Con ellas venía la
dirección IP de ese otro: para saber quién le corrigió el fichaje ya está el
nombre, y lo demás es el dato personal de un compañero.

Salió probando la pantalla de Actividad con la sesión de un operario el
13/08/2026: la línea de una corrección impuesta traía la IP de la responsable.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
DESDE = "203.0.113.7"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def gente(company):
    with tenant_context(company.id):
        yield {
            "marta": User.objects.create_user(
                email="marta@example.com", password=PASSWORD, tenant=company, first_name="Marta"
            ),
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
            "admin": User.objects.create_user(
                email="admin@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Ana",
                role=Role.ADMIN,
            ),
        }


@pytest.fixture
def linea(company, gente):
    """La jefa le impone una corrección a Marta, desde su propia IP."""
    with tenant_context(company.id):
        yield AuditLog.objects.create(
            tenant=company,
            actor=gente["jefa"],
            actor_label="Luisa",
            action=AuditAction.CORRECTION_IMPOSED,
            target_type="user",
            target_id=gente["marta"].id,
            target_label="Marta",
            ip_address=DESDE,
        )


def lineas_de(persona):
    client = APIClient()
    client.force_authenticate(user=persona)
    return client.get("/api/audit/").json()["results"]


@pytest.mark.django_db
def test_el_sujeto_ve_la_linea_pero_no_la_ip_de_quien_actuo(company, gente, linea):
    with tenant_context(company.id):
        filas = lineas_de(gente["marta"])

    assert len(filas) == 1, "tiene que ver que le tocaron el fichaje"
    assert filas[0]["actor_label"] == "Luisa", "y quién fue"
    assert filas[0]["ip_address"] == "", "pero no desde dónde trabaja esa persona"


@pytest.mark.django_db
def test_quien_actuo_si_ve_la_suya(company, gente, linea):
    with tenant_context(company.id):
        filas = lineas_de(gente["jefa"])

    assert filas[0]["ip_address"] == DESDE


@pytest.mark.django_db
def test_la_administracion_las_ve_todas(company, gente, linea):
    """Es quien investiga un acceso raro, y sin la dirección no hay nada que ver."""
    with tenant_context(company.id):
        filas = lineas_de(gente["admin"])

    assert filas[0]["ip_address"] == DESDE


@pytest.mark.django_db
def test_el_fichero_descargado_aplica_el_mismo_criterio(company, gente, linea):
    """El CSV no pasa por el serializador, así que se comprueba aparte."""
    with tenant_context(company.id):
        client = APIClient()
        client.force_authenticate(user=gente["marta"])
        cuerpo = client.get("/api/audit/export/").content.decode()

    assert "Luisa" in cuerpo
    assert DESDE not in cuerpo
