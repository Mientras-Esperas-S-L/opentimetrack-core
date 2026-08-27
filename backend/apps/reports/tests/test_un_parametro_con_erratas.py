"""Pedir el documento con un parámetro mal escrito no puede darte otro documento.

Los parámetros desconocidos se ignoran. En un listado eso es una molestia; en el
informe del art. 34.9 es otra cosa. Medido antes de arreglarlo:

    ?employe=<id de otra persona>      -> 200 con el registro de quien pregunta
    ?employee_id=<id>                  -> igual
    ?user=<id>                         -> igual
    ?date_form=2026-08-01              -> 200 con el periodo por defecto

Una letra de menos y el fichero que sale lleva otro nombre dentro. Un guion que
descargue la plantilla entera con la errata genera una carpeta de documentos que
no son de quien dicen ser.

Es el mismo razonamiento que `refuse_wrong_period_names`, escrito para `from` y
`to` y que se quedó en esos dos nombres: «lo que se pone a disposición de la
Inspección es el registro que se pidió, no otro».

La mitad de este fichero son los parámetros que **sí** existen: una lista blanca
mal escrita rompería el producto de una forma mucho más cara que el fallo.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
PERIODO = {"date_from": "2026-08-01", "date_to": "2026-08-26"}

ERRATAS = ["employe", "employee_id", "user", "date_form", "dateto", "formato"]


@pytest.fixture
def gente(db):
    empresa = Tenant.objects.create(name="Errata SL", tax_id="B24242424", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        # Administración, que es quien puede pedir el registro de otra persona.
        # Con `is_staff` a secas no basta: lo que manda es el rol.
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Je",
            last_name="Fa",
            role=Role.ADMIN,
        )
        otra = User.objects.create_user(
            email="otra@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ot",
            last_name="Ra",
        )
        register_punch(employee=otra, company=empresa)
        api = APIClient()
        api.force_authenticate(user=jefa)
        yield api, empresa, jefa, otra


@pytest.mark.parametrize("errata", ERRATAS)
@pytest.mark.django_db
def test_una_errata_se_rechaza(gente, errata):
    api, empresa, _jefa, otra = gente
    with tenant_context(empresa.id):
        r = api.get("/api/reports/working-time/", {errata: str(otra.id), **PERIODO})

    assert r.status_code == 400, (
        f"«{errata}» se ignoró y el informe salió igual: quien lo pidió recibe un "
        "documento que no es el que pidió, con otro nombre dentro"
    )
    assert errata in str(r.json()), r.json()


@pytest.mark.django_db
def test_el_mensaje_dice_cuáles_valen(gente):
    api, empresa, _jefa, otra = gente
    with tenant_context(empresa.id):
        r = api.get("/api/reports/working-time/", {"employe": str(otra.id), **PERIODO})

    texto = str(r.json())
    assert "employee" in texto and "date_from" in texto, (
        f"el error no dice qué se puede pedir: {texto}"
    )


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"format": "csv"},
        {"scope": "company"},
        {"department": ""},
    ],
)
@pytest.mark.django_db
def test_los_parametros_de_verdad_siguen_valiendo(gente, params):
    """El contraste. Una lista blanca a la que le falte un nombre rompe el
    producto de una forma mucho más cara que el fallo que viene a arreglar."""
    api, empresa, _jefa, _otra = gente
    with tenant_context(empresa.id):
        r = api.get("/api/reports/working-time/", {**PERIODO, **params})

    assert r.status_code == 200, f"{params} dejó de funcionar: {r.content[:200]}"


@pytest.mark.django_db
def test_el_empleado_pedido_es_el_que_sale(gente):
    """Lo que estaba en juego: que el documento sea de quien se pidió."""
    api, empresa, jefa, otra = gente
    with tenant_context(empresa.id):
        r = api.get(
            "/api/reports/working-time/",
            {"employee": str(otra.id), "format": "csv", **PERIODO},
        )
        texto = r.content.decode("utf-8")

    assert otra.get_full_name() in texto
    assert jefa.get_full_name() not in texto


@pytest.mark.django_db
def test_el_resumen_del_articulo_6_1_hace_lo_mismo(gente):
    api, empresa, _jefa, otra = gente
    with tenant_context(empresa.id):
        malo = api.get("/api/reports/payroll-summary/", {"employe": str(otra.id)})
        bueno = api.get("/api/reports/payroll-summary/", {"employee": str(otra.id)})
        con_dia = api.get("/api/reports/payroll-summary/", {"day": "2026-08-15"})

    assert malo.status_code == 400, "el resumen se traga la errata"
    assert bueno.status_code == 200, bueno.content[:200]
    assert con_dia.status_code == 200, con_dia.content[:200]
