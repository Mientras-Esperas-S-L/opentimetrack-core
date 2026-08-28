"""Buscar por nombre sin poner los acentos.

Nadie teclea «García» con tilde buscando a García, y hasta este arreglo eso
devolvía **cero**: `?search=garcia` no encontraba a Ana García, ni `ibanez` a
Rocío Ibáñez. Con una plantilla española eso es la mitad de los apellidos.

Salió por una prueba de navegador que fallaba una vez de cada tantas ---la del
buscador de personas, que teclea «ibanez»--- y que pasaba al ejecutarla sola.
La razón de que fuera intermitente resultó ser lo interesante: el navegador
recorta la lista por su cuenta y **eso** sí ignora los acentos, así que mientras
la respuesta anterior siguiera en pantalla la encontraba igual. Solo cuando la
lista del servidor llegaba antes de teclear se veía el cero. En cuanto la
plantilla no cabe en una página, eso deja de ser intermitente y pasa siempre.

Los dos sentidos, que es la mitad que se olvida: quitar los acentos solo de la
columna arregla `garcia` y rompe `García`, que es cambiar un fallo por el
contrario.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def plantilla(empresa):
    with tenant_context(empresa.id):
        admin = User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Admin",
            last_name="Suárez",
            role=Role.ADMIN,
        )
        User.objects.create_user(
            email="ana@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            last_name="García",
        )
        User.objects.create_user(
            email="rocio@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Rocío",
            last_name="Ibáñez",
        )
        # Sin un solo acento: el contraste que distingue «busca bien» de
        # «devuelve la plantilla entera pase lo que pase».
        User.objects.create_user(
            email="hugo@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Hugo",
            last_name="Bermejo",
        )
        yield admin


def buscar(admin, aguja, ruta="/api/employees/"):
    client = APIClient()
    client.force_authenticate(user=admin)
    respuesta = client.get(ruta, {"search": aguja})
    assert respuesta.status_code == 200, respuesta.json()
    return sorted(fila.get("email") or fila.get("name") for fila in respuesta.json()["results"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "aguja",
    ["garcia", "García", "GARCIA", "garcía", "Garcia"],
    ids=["sin tilde", "con tilde", "mayúsculas sin tilde", "minúsculas con tilde", "capitalizado"],
)
def test_un_apellido_con_tilde_se_encuentra_se_escriba_como_se_escriba(empresa, plantilla, aguja):
    with tenant_context(empresa.id):
        assert buscar(plantilla, aguja) == ["ana@example.com"]


@pytest.mark.django_db
@pytest.mark.parametrize("aguja", ["ibanez", "Ibáñez", "ibañez", "IBANEZ"])
def test_la_ene_con_virgulilla_tambien(empresa, plantilla, aguja):
    """La eñe se descompone igual que una tilde, y nadie la busca con ella."""
    with tenant_context(empresa.id):
        assert buscar(plantilla, aguja) == ["rocio@example.com"]


@pytest.mark.django_db
def test_lo_que_no_esta_sigue_sin_estar(empresa, plantilla):
    """El contraste. Sin esto, un filtro que no filtrase nada pasaría entero.

    Y de paso: quien no tiene acentos se sigue encontrando, que es lo que estaba
    bien antes y no se puede romper al arreglar lo otro.
    """
    with tenant_context(empresa.id):
        assert buscar(plantilla, "bermejo") == ["hugo@example.com"]
        assert buscar(plantilla, "zzzz") == []


@pytest.mark.django_db
def test_vale_para_los_demas_buscadores(empresa, plantilla):
    """No es cosa del buscador de personas: es el `search` de toda la API.

    Los departamentos y los centros se llaman «Almacén», «Jardinería» o
    «Dirección», y se buscan igual de mal.
    """
    with tenant_context(empresa.id):
        Department.objects.create(tenant=empresa, name="Jardinería")
        Workplace.objects.create(tenant=empresa, name="Almacén")

        assert buscar(plantilla, "jardineria", "/api/departments/") == ["Jardinería"]
        assert buscar(plantilla, "almacen", "/api/workplaces/") == ["Almacén"]


@pytest.mark.django_db
def test_los_fichajes_se_buscan_por_quien_los_hizo(empresa, plantilla):
    """`?search=` en el listado de fichajes no filtraba: contestaba 200 con todo.

    El filtro es global, así que el parámetro se acepta en los once listados de
    la API; pero DRF solo busca donde hay `search_fields` declarados, y aquí no
    los había. **Siete de los once estaban así.**

    Lo tapó durante meses una persona con casi mil fichajes en la demostración:
    llenaba ella sola la primera página, la prueba de navegador miraba los
    primeros resultados, salían todos suyos y parecía que el filtro funcionaba.
    Se destapó al resembrar los datos con los fichajes repartidos.
    """
    with tenant_context(empresa.id):
        hugo = User.objects.get(email="hugo@example.com")
        rocio = User.objects.get(email="rocio@example.com")
        for quien in (hugo, rocio):
            Punch.objects.create(
                tenant=empresa,
                employee=quien,
                punch_type=PunchType.IN,
                timestamp=datetime(2026, 9, 1, 7, 0, tzinfo=UTC),
            )

        client = APIClient()
        client.force_authenticate(user=plantilla)
        respuesta = client.get("/api/punches/", {"search": "bermejo"})
        assert respuesta.status_code == 200, respuesta.json()
        filas = respuesta.json()["results"]

        # El contraste, que es el que faltaba: sin él, «devuelve la empresa
        # entera» y «filtra bien» dan los dos una lista no vacía.
        assert len(filas) == 1, f"trajo {len(filas)} fichajes, y solo uno es de Bermejo"
        assert {fila["employee"] for fila in filas} == {str(hugo.id)}

        # Y sin acentos, que es lo que este fichero defiende: el apellido de
        # Rocío se teclea sin la eñe.
        sin_tilde = client.get("/api/punches/", {"search": "ibanez"})
        assert {fila["employee"] for fila in sin_tilde.json()["results"]} == {str(rocio.id)}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ruta",
    ["/api/holidays/", "/api/leave-types/", "/api/shifts/", "/api/shift-patterns/"],
)
def test_el_listado_que_no_busca_por_texto_lo_dice(empresa, plantilla, ruta):
    """Pedir un recorte y recibir la tabla entera con un 200 es peor que un error.

    Se parece a una respuesta correcta, así que quien integra no lo mira. Y en
    un producto cuyo objeto es el registro de jornada, entregar de más es
    entregar el registro de quien no se preguntó ---lo que el art. 34.9 acota---.

    Estos cuatro listados no buscan por texto, y ahora lo dicen en vez de
    callarse. Si algún día han de buscar, se les declaran los campos y esta
    prueba lo señala sola: la fila se cae de la lista.
    """
    with tenant_context(empresa.id):
        client = APIClient()
        client.force_authenticate(user=plantilla)

        respuesta = client.get(ruta, {"search": "lo que sea"})
        assert respuesta.status_code == 400, respuesta.json()
        assert "search" in str(respuesta.json())

        # El contraste. Sin el parámetro el listado responde como siempre: lo
        # que se rechaza es la búsqueda, no el listado.
        assert client.get(ruta).status_code == 200
