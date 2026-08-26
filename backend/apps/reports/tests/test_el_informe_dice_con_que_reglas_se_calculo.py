"""Dos informes del mismo mes con cifras distintas tienen que ser explicables.

El cómputo lee las reglas de la empresa **de hoy**, así que cambiarlas reescribe
periodos ya cerrados. Medido en la vuelta 94, sobre un abril terminado:

- Marcar que la pausa cuenta como tiempo de trabajo lo llevaba de **7:00 a 8:00**
  horas.
- Bajar el tope de jornada abierta convertía un turno de noche bien fichado
  ---`2026-04-14;22:00;06:00;08:00`--- en `22:00;;00:00;entrada sin salida`: ocho
  horas trabajadas pasaban a cero y aparecía una incidencia que no había ocurrido.

Que esas reglas cambien es legítimo: salen del convenio. Que el cambio alcance al
pasado, no. Arreglarlo de verdad pide reglas con **fechas de vigencia**, y eso es
una decisión de producto ---¿desde cuándo aplica un convenio nuevo?--- que está
anotada en el cuaderno y no se decide desde una vuelta de auditoría.

Lo que sí se puede hacer sin decidir eso: que el documento diga bajo qué reglas se
emitió. No cambia ninguna cifra; hace que dos versiones del mismo mes se puedan
comparar en vez de contradecirse sin explicación. El huso ya se imprimía por el
mismo motivo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Con reglas", tax_id="B91300001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Ficha",
        )
        # Entra a las 08:00, pausa de 13:00 a 14:00, sale a las 17:00.
        entrada = datetime(2026, 4, 15, 6, 0, tzinfo=UTC)
        for tipo, horas, tramo in (
            ("IN", 0, "WORK"),
            ("OUT", 5, "WORK"),
            ("IN", 5, "BREAK"),
            ("OUT", 6, "BREAK"),
            ("IN", 6, "WORK"),
            ("OUT", 9, "WORK"),
        ):
            Punch.objects.create(
                tenant=empresa,
                employee=quien,
                punch_type=tipo,
                interval=tramo,
                timestamp=entrada + timedelta(hours=horas),
                source="WEB",
                time_zone="Europe/Madrid",
            )
        yield {"empresa": empresa, "jefa": jefa, "quien": quien}


def informe(mundo, formato="csv"):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=mundo["jefa"])
    respuesta = cliente.get(
        "/api/reports/working-time/"
        f"?date_from=2026-04-10&date_to=2026-04-20&employee={mundo['quien'].pk}&format={formato}"
    )
    assert respuesta.status_code == 200, respuesta.content
    return respuesta


@pytest.mark.django_db
def test_el_csv_dice_como_trata_la_pausa_y_cual_es_el_tope(mundo):
    texto = informe(mundo).content.decode("utf-8-sig", "replace")

    # En la cabecera, junto al periodo y al huso: es lo que explica la cifra.
    cabecera = texto.splitlines()[:6]
    assert any("16" in linea for linea in cabecera), (
        f"el tope de jornada abierta no sale en la cabecera: {cabecera}"
    )


@pytest.mark.django_db
def test_y_cambia_cuando_cambia_la_regla(mundo):
    """Lo que se imprime es la regla de verdad, no un texto fijo."""
    with tenant_context(mundo["empresa"].id):
        reglas = WorkingTimeRules.for_company(mundo["empresa"])
        reglas.max_open_hours = 9
        reglas.save(update_fields=["max_open_hours"])
        mundo["empresa"].refresh_from_db()

    cabecera = informe(mundo).content.decode("utf-8-sig", "replace").splitlines()[:6]
    assert any(";9" in linea for linea in cabecera), cabecera


@pytest.mark.django_db
def test_el_pdf_tambien(mundo):
    contenido = informe(mundo, formato="pdf").content
    assert contenido.startswith(b"%PDF-")

    import io as _io

    from pypdf import PdfReader

    texto = "".join(p.extract_text() or "" for p in PdfReader(_io.BytesIO(contenido)).pages)
    # El documento que se entrega es el PDF, así que es el que más lo necesita.
    assert "16" in texto


@pytest.mark.django_db
def test_las_cifras_no_las_cambia_esto(mundo):
    """Imprimir las reglas explica el resultado; no lo altera."""
    texto = informe(mundo).content.decode("utf-8-sig", "replace")
    fila = [linea for linea in texto.splitlines() if "2026-04-15" in linea]

    assert fila, "el día desapareció del informe"
    # Ocho horas de presencia menos una de pausa que no cuenta como trabajo.
    assert "07:00" in fila[0], fila[0]
