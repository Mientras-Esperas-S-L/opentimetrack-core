"""Una empresa recién dada de alta ya tiene sus permisos.

El fallo: no los tenía. Se creaba la empresa, se creaba su administradora, y el
catálogo se quedaba en **cero**. El desplegable de «Qué pides» salía vacío y
nadie podía pedir un matrimonio, un fallecimiento ni una hospitalización --- todo
el art. 37.3 quedaba fuera del producto.

Y no había manera de arreglarlo desde dentro: el endpoint que siembra el
catálogo existía, y no lo llamaba ninguna pantalla. Solo lo usaba el comando de
datos de demostración, o sea que funcionaba en desarrollo y en ningún sitio más
--- que es la forma más cara de que algo esté roto, porque parece que está bien.

Aquí también se contrasta el catálogo contra el articulado, que es lo único que
convierte «hay treinta y dos filas» en «están los que la ley da».
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.absences.models import LeaveType
from apps.common.models import tenant_context
from apps.tenants.models import Tenant

ALTA = {
    "company_name": "Jardines del Norte S.L.",
    "tax_id": "B12312312",
    "country": "ES",
    "time_zone": "Europe/Madrid",
    "email": "jefa@norte.example",
    "password": "una-contrasena-suficientemente-larga",
    "first_name": "Luisa",
    "last_name": "Marín",
}


@pytest.fixture
def alta(db):
    respuesta = APIClient().post("/api/auth/register/", ALTA, format="json")
    assert respuesta.status_code == 201, respuesta.data
    return Tenant.objects.get(tax_id=ALTA["tax_id"])


def catalogo(empresa) -> dict[str, LeaveType]:
    with tenant_context(empresa.id):
        return {fila.code: fila for fila in LeaveType.objects.all()}


@pytest.mark.django_db
def test_el_catalogo_llega_con_la_empresa(alta):
    assert catalogo(alta), "una empresa nueva se quedaba sin un solo permiso"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("code", "articulo", "cuantos", "unidad"),
    [
        ("es.marriage", "Art. 37.3.a ET", 15, "DAYS_CALENDAR"),
        ("es.family_illness", "Art. 37.3.b ET", 5, "DAYS_CALENDAR"),
        ("es.bereavement", "Art. 37.3.b bis ET", 2, "DAYS_CALENDAR"),
        ("es.moving_house", "Art. 37.3.c ET", 1, "DAYS_CALENDAR"),
    ],
    ids=["matrimonio", "hospitalización", "fallecimiento", "mudanza"],
)
def test_los_permisos_con_numero_traen_el_del_articulo(alta, code, articulo, cuantos, unidad):
    """Las letras importan tanto como los números.

    El RDL 5/2023 partió la antigua letra b en dos: subió la hospitalización de
    dos días a cinco y sacó el fallecimiento a una letra nueva, «b bis», sin
    correr las demás. Un catálogo que citara «37.3.b» para el fallecimiento
    estaría mandando a quien lo lea al artículo equivocado, y ahí leería cinco
    días donde tiene dos.
    """
    fila = catalogo(alta)[code]

    assert fila.basis == articulo
    assert float(fila.amount) == cuantos
    assert fila.unit == unidad


@pytest.mark.django_db
def test_el_fallecimiento_dobla_con_desplazamiento(alta):
    """«Cuando con tal motivo necesite hacer un desplazamiento, cuatro días.»

    Se guarda como el extra, no como el total: quien no se desplaza tiene dos, y
    un catálogo que pusiera cuatro a secas le regalaría dos días a la mitad de
    los casos y dejaría sin forma de distinguirlos.
    """
    fila = catalogo(alta)["es.bereavement"]

    assert float(fila.extra_when_travelling) == 2
    assert float(fila.amount) + float(fila.extra_when_travelling) == 4


@pytest.mark.django_db
@pytest.mark.parametrize(
    "code",
    ["es.public_duty", "es.union_duties", "es.prenatal"],
    ids=["deber inexcusable", "funciones sindicales", "exámenes prenatales"],
)
def test_los_del_tiempo_indispensable_no_llevan_tope(alta, code):
    """«Por el tiempo indispensable» no es un número, y ponerle uno sería
    inventarse un límite que la ley no da."""
    assert catalogo(alta)[code].amount is None


@pytest.mark.django_db
def test_volver_a_sembrar_no_pisa_lo_que_la_empresa_cambió(alta):
    """El convenio mejora cualquiera de estos, y esa edición es la que manda.

    Es la razón entera de que el catálogo se copie en vez de leerse del marco:
    si se leyera vivo, corregir una cifra nuestra reescribiría en silencio algo
    que alguien negoció.
    """
    with tenant_context(alta.id):
        suyo = LeaveType.objects.get(code="es.marriage")
        suyo.amount = 18  # su convenio da tres días más
        suyo.save(update_fields=["amount"])

        cliente = APIClient()
        cliente.force_authenticate(user=alta.users.first())
        respuesta = cliente.post("/api/leave-types/seed/")

        assert respuesta.status_code == 200
        assert float(LeaveType.objects.get(code="es.marriage").amount) == 18


@pytest.mark.django_db
def test_quien_pide_ve_el_catálogo_desde_el_primer_dia(alta):
    """El contraste que importa: no que existan las filas, sino que lleguen a
    quien tiene que elegir una."""
    with tenant_context(alta.id):
        cliente = APIClient()
        cliente.force_authenticate(user=alta.users.first())
        respuesta = cliente.get("/api/leave-types/")

    assert respuesta.status_code == 200
    filas = respuesta.json()["results"]
    assert any("Matrimonio" in fila["name"] for fila in filas), [f["name"] for f in filas]
