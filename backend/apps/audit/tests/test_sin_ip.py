"""El rastro de actividad no guarda direcciones IP. Ninguna.

Sustituye a `test_ip_ajena`, que comprobaba **a quién** se le enseñaba la IP de
cada línea. Aquella prueba nació de un caso real: con la sesión de un operario,
la línea de una corrección impuesta traía la IP de la responsable que se la
había hecho. Se tapó enseñándosela solo a quien administraba o a quien había
actuado.

Ahora ni se guarda, y el motivo es que la solución de entonces no llegaba al
fondo. Una IP es dato personal ---resuelto desde Breyer, y la AEPD lo trata
así---, y el RGPD pide poder borrarla si alguien lo pide (art. 17) y no
conservarla sin límite (art. 5.1.e). Esta tabla es inmutable: tres disparadores
hacen fallar UPDATE, DELETE y TRUNCATE. O sea que no es que borrarla fuera
trabajoso, es que la base de datos lo rechazaba. Las dos garantías se peleaban.

Cede la IP. El rastro tiene que decir quién hizo qué y cuándo, y eso lo dice el
actor. Para investigar un acceso raro están los registros del servidor web, que
sí caducan solos.

Se comprueba por las dos puntas ---la columna y lo que sirve la API--- porque
son dos formas distintas de que vuelva: alguien que añade el campo «porque hace
falta para depurar», y alguien que lo sirve desde otro sitio.
"""

from __future__ import annotations

import pytest
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditLog
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def jefa(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Luisa",
            role=Role.ADMIN,
        )


def test_la_columna_ya_no_existe(db):
    """En la tabla, no solo en el modelo.

    Quitarlo del modelo y dejar la columna llena dejaría los datos donde están
    y sin forma de sacarlos, que es exactamente el problema que esto viene a
    resolver. La migración tiene que haberla tirado.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_auditlog'"
        )
        columnas = {fila[0] for fila in cursor.fetchall()}

    # Contraste: si la consulta no devolviera nada, la comprobación de abajo
    # pasaría por el motivo equivocado.
    assert "action" in columnas, "no se está leyendo la tabla que se cree"
    assert "ip_address" not in columnas


def test_el_modelo_no_admite_el_campo(db):
    assert not any(f.name == "ip_address" for f in AuditLog._meta.get_fields())


@pytest.mark.django_db
def test_la_api_no_sirve_ninguna_ip(company, jefa):
    """Y a quien administra tampoco, que era quien sí la veía antes.

    Es la comprobación que importa: la versión anterior se la enseñaba a
    administración entera, así que una prueba hecha con un operario habría dado
    verde con la IP todavía puesta.
    """
    with tenant_context(company.id):
        AuditLog.objects.create(
            tenant=company,
            actor=jefa,
            actor_label="Luisa",
            action="login",
            note="Entró",
        )
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(jefa).access_token}")
        respuesta = cliente.get("/api/audit/")

    assert respuesta.status_code == 200
    filas = respuesta.json()["results"]
    assert filas, "sin filas esto no comprueba nada"
    assert "ip_address" not in filas[0]
    # Ni con otro nombre: lo que no puede salir es la dirección, se llame como
    # se llame el campo.
    assert not any("ip" in clave.lower() for clave in filas[0])


@pytest.mark.django_db
def test_y_el_rastro_sigue_diciendo_quien_y_cuando(company, jefa):
    """El contraste. Quitar la IP no puede llevarse por delante para lo que
    existe el registro, que es responder quién hizo qué."""
    with tenant_context(company.id):
        AuditLog.objects.create(
            tenant=company,
            actor=jefa,
            actor_label="Luisa",
            action="login",
            note="Entró",
        )
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(jefa).access_token}")
        fila = cliente.get("/api/audit/").json()["results"][0]

    assert fila["actor_label"] == "Luisa"
    assert fila["at"]
    assert fila["action"] == "login"
