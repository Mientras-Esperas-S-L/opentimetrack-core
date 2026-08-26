"""El nombre de un fichero es una ruta para quien lo recibe.

El apellido de una persona acaba en la cabecera `Content-Disposition` y en la
entrada de un zip, y los dos sitios lo leen como camino. El apellido es texto
libre que escribe la administración de la empresa --- o un conector, por
`/api/app/people/`.

Y quien descomprime ese zip es la gestoría o la Inspección.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.descargas import nombre_de_persona, nombre_seguro
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
VENTANA = "date_from=2026-08-01&date_to=2026-08-31"


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
            last_name="Manda",
            role=Role.ADMIN,
        )


def como(persona):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(persona).access_token}")
    return cliente


# ------------------------------------------------------------------ el helper


@pytest.mark.parametrize(
    "entrada",
    ["../../../evil", "..", "/etc/passwd", 'con"comilla', "con\nsalto", "con:dos", "con\\barra"],
)
def test_nada_que_se_lea_como_ruta(entrada):
    salida = nombre_seguro(entrada)
    for prohibido in ("/", "\\", "..", '"', "\n", ":"):
        assert prohibido not in salida, f"{entrada!r} salió como {salida!r}"


def test_los_acentos_se_translitera_en_vez_de_perderse():
    """«Garc_a» no lo reconoce nadie; «Garcia», sí."""
    assert nombre_seguro("García Muñoz") == "Garcia_Munoz"


def test_lo_que_queda_vacio_usa_el_respaldo():
    assert nombre_seguro("..", respaldo="informe") == "informe"
    assert nombre_seguro("", respaldo="informe") == "informe"


# ------------------------------------------------------------------- el zip


@pytest.mark.django_db
def test_el_zip_no_lleva_rutas_dentro(company, jefa):
    with tenant_context(company.id):
        malo = User.objects.create_user(
            email="malo@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Nombre",
            last_name="../../../evil",
        )
        register_punch(employee=malo, company=company)

    respuesta = como(jefa).get(f"/api/reports/working-time/?scope=company&{VENTANA}&format=pdf")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(respuesta.content)) as paquete:
        nombres = paquete.namelist()
    assert nombres, "el zip vino vacío: no se está midiendo nada"
    for nombre in nombres:
        assert "/" not in nombre and ".." not in nombre, f"entrada con ruta: {nombre!r}"


@pytest.mark.django_db
def test_dos_personas_que_se_llaman_igual_no_se_pisan(company, jefa):
    """Sin identificador, la segunda entrada pisaba a la primera al
    descomprimir: se entregaba un informe menos de los que dice la carátula, y
    nada avisaba."""
    with tenant_context(company.id):
        for correo in ("ana1@example.com", "ana2@example.com"):
            quien = User.objects.create_user(
                email=correo,
                password=PASSWORD,
                tenant=company,
                first_name="Ana",
                last_name="García",
            )
            register_punch(employee=quien, company=company)

    respuesta = como(jefa).get(f"/api/reports/working-time/?scope=company&{VENTANA}&format=pdf")

    with zipfile.ZipFile(io.BytesIO(respuesta.content)) as paquete:
        nombres = paquete.namelist()
    assert len(nombres) == len(set(nombres)), f"dos entradas con el mismo nombre: {nombres}"


@pytest.mark.django_db
def test_sin_apellido_el_nombre_no_empieza_por_el_separador(company):
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="solo@example.com", password=PASSWORD, tenant=company, first_name="Jefa"
        )
    assert not nombre_de_persona(quien, extension="pdf").startswith("_")


# ------------------------------------------------------- la cabecera de descarga


@pytest.mark.django_db
def test_la_cabecera_no_se_rompe_con_una_comilla(company, jefa):
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="comilla@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            last_name='Pon"Comilla',
        )
        register_punch(employee=quien, company=company)

    respuesta = como(jefa).get(
        f"/api/reports/working-time/?employee={quien.id}&{VENTANA}&format=csv"
    )

    assert respuesta.status_code == 200
    cabecera = respuesta["Content-Disposition"]
    # Las comillas del nombre son las dos de la sintaxis y ninguna más.
    assert cabecera.count('"') == 2, f"la cabecera lleva comillas de más: {cabecera!r}"
