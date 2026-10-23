"""«¿Cuánto he trabajado esta semana, este mes, entre estas fechas?»

«Mi jornada» enseñaba días sueltos, mes a mes, y nada más: para saber las horas
de una semana había que sumarlas a mano, y para un periodo que cruzara dos meses,
ir y volver entre ellos. El informe ya sabía sumar cualquier periodo, pero solo
lo decía dentro de un PDF.

`?format=json` da esas mismas cifras en datos. Las mismas y no otras: la pantalla
que suma por su cuenta acaba diciendo una cosa y el documento otra.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.reports.services import build_report
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(
        name="Sumas", tax_id="B90400777", time_zone="Europe/Madrid", country="ES"
    )


def persona(empresa, email, role=Role.EMPLOYEE):
    with tenant_context(empresa.id):
        return User.objects.create_user(
            email=email, password=PASSWORD, tenant=empresa, first_name=email[:3], role=role
        )


def trabajo(empresa, quien, dia, horas):
    with tenant_context(empresa.id):
        with freeze_time(f"{dia} 06:00:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time(f"{dia} {6 + horas:02d}:00:00"):
            register_punch(employee=quien, company=empresa)


def pedir(quien, consulta):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente.get(f"/api/reports/working-time/?{consulta}")


@pytest.mark.django_db
def test_un_periodo_que_cruza_dos_meses_se_suma_entero(empresa):
    ana = persona(empresa, "ana@example.com")
    trabajo(empresa, ana, "2026-09-29", 8)
    trabajo(empresa, ana, "2026-09-30", 7)
    trabajo(empresa, ana, "2026-10-01", 6)

    respuesta = pedir(ana, "date_from=2026-09-28&date_to=2026-10-04&format=json")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total_seconds"] == 21 * 3600
    assert cuerpo["days"] == [
        {"day": "2026-09-29", "seconds": 8 * 3600},
        {"day": "2026-09-30", "seconds": 7 * 3600},
        {"day": "2026-10-01", "seconds": 6 * 3600},
    ]


@pytest.mark.django_db
def test_dice_lo_mismo_que_el_documento(empresa):
    ana = persona(empresa, "ana@example.com")
    trabajo(empresa, ana, "2026-10-05", 8)
    trabajo(empresa, ana, "2026-10-06", 9)

    cuerpo = pedir(ana, "date_from=2026-10-01&date_to=2026-10-31&format=json").json()

    with tenant_context(empresa.id):
        documento = build_report(
            employee=ana,
            company=empresa,
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
        )
    assert cuerpo["total_seconds"] == documento.total_seconds
    assert cuerpo["break_seconds"] == documento.total_break_seconds
    assert cuerpo["overtime_seconds"] == documento.total_overtime_seconds


@pytest.mark.django_db
def test_sin_formato_sigue_saliendo_el_pdf(empresa):
    ana = persona(empresa, "ana@example.com")
    trabajo(empresa, ana, "2026-10-05", 8)

    respuesta = pedir(ana, "date_from=2026-10-01&date_to=2026-10-31")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_las_cifras_de_otra_persona_piden_un_responsable(empresa):
    ana = persona(empresa, "ana@example.com")
    luis = persona(empresa, "luis@example.com")

    respuesta = pedir(luis, f"employee={ana.id}&format=json")

    assert respuesta.status_code == 400


@pytest.mark.django_db
def test_la_plantilla_entera_no_se_da_en_cifras(empresa):
    jefa = persona(empresa, "jefa@example.com", role=Role.ADMIN)

    respuesta = pedir(jefa, "scope=company&format=json")

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["message"]
