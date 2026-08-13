"""Los filtros de la lista de personas, pedidos con identificadores de verdad.

Existe por un fallo que la API tuvo desde el principio y que nadie cazó:
`?department=` **rechazaba cualquier identificador**, incluso el correcto, con
«Escoja una opción válida».

El motivo es una trampa fina de `django-filter` con multiempresa: un filtro
generado desde `Meta.fields` construye su lista de opciones al **importar** el
módulo, y en ese momento no hay empresa en el contexto. Los gestores de un
`TenantOwnedModel` devuelven vacío sin empresa, así que la lista quedaba vacía
para siempre.

La prueba que no lo habría cazado es la evidente: pedir `?department=` con un
identificador inventado y comprobar que da 400. Da 400, sí --- **siempre** da
400. Por eso aquí se piden con el identificador bueno y se mira que responda y
que lo que devuelve sea justo lo pedido.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def mundo(company):
    with tenant_context(company.id):
        brigada = Department.objects.create(tenant=company, name="Brigada")
        oficina = Department.objects.create(tenant=company, name="Oficina")
        nave = Workplace.objects.create(tenant=company, name="Nave")

        admin = User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            role=Role.ADMIN,
        )
        User.objects.create_user(
            email="pepe@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Pepe",
            department=brigada,
            workplace=nave,
        )
        User.objects.create_user(
            email="lola@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Lola",
            department=oficina,
        )
        # Sin departamento a propósito: es el caso que la reorganización busca.
        User.objects.create_user(
            email="suelta@example.com", password=PASSWORD, tenant=company, first_name="Suelta"
        )
        yield {"admin": admin, "brigada": brigada, "oficina": oficina, "nave": nave}


def pedir(admin, consulta):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client.get(f"/api/employees/?{consulta}")


@pytest.mark.django_db
def test_filtrar_por_departamento_devuelve_solo_esa_gente(company, mundo):
    """El que estaba roto."""
    with tenant_context(company.id):
        respuesta = pedir(mundo["admin"], f"department={mundo['brigada'].id}")

    assert respuesta.status_code == 200, respuesta.json()
    correos = [fila["email"] for fila in respuesta.json()["results"]]
    assert correos == ["pepe@example.com"]


@pytest.mark.django_db
def test_filtrar_por_centro_devuelve_solo_esa_gente(company, mundo):
    with tenant_context(company.id):
        respuesta = pedir(mundo["admin"], f"workplace={mundo['nave'].id}")

    assert respuesta.status_code == 200, respuesta.json()
    assert [fila["email"] for fila in respuesta.json()["results"]] == ["pepe@example.com"]


@pytest.mark.django_db
def test_sin_departamento_es_su_propia_pregunta(company, mundo):
    """Con `?department=` vacío no se puede formular: da igual que no mandarlo."""
    with tenant_context(company.id):
        vacio = pedir(mundo["admin"], "department=")
        sueltas = pedir(mundo["admin"], "no_department=true")

    assert vacio.json()["count"] == 4, "un parámetro vacío no filtra, y así debe ser"

    # Ana también está suelta: administrar no es pertenecer a un departamento.
    correos = sorted(fila["email"] for fila in sueltas.json()["results"])
    assert correos == ["admin@example.com", "suelta@example.com"]


@pytest.mark.django_db
def test_un_departamento_de_otra_empresa_no_vale(db, company, mundo):
    """Y esto es lo que la lista de opciones sí tiene que impedir.

    Que se resuelva por petición no puede significar que acepte cualquier cosa:
    un identificador de otra empresa tiene que seguir siendo inválido, y por eso
    la comprobación no se puede sustituir por quitar el filtro y ya está.
    """
    otra = Tenant.objects.create(name="Vecina", tax_id="B22222222", time_zone="Europe/Madrid")
    with tenant_context(otra.id):
        ajeno = Department.objects.create(tenant=otra, name="Ajeno")

    with tenant_context(company.id):
        respuesta = pedir(mundo["admin"], f"department={ajeno.id}")

    assert respuesta.status_code == 400
    assert "department" in respuesta.json()["error"]["details"]
