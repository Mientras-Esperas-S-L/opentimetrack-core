"""Un CSV que se entrega no puede ejecutarse al abrirlo.

Excel y LibreOffice evalúan como fórmula cualquier celda que empiece por `=`,
`+`, `-` o `@`. Las comillas del CSV no protegen: son sintaxis del fichero, el
programa las quita al leer y evalúa lo de dentro.

Aquí el destinatario es la Inspección o la gestoría, y parte del texto lo escribe
la persona trabajadora: la discrepancia del art. 4.b viaja al informe **por
diseño**, porque es el derecho que ese artículo protege, así que no se puede
sanear quitándola. Y el rastro de auditoría lleva `actor_label`, que en una
integración lo pone el conector.
"""

from __future__ import annotations

import io

import pytest

from apps.common.clock import local_today
from apps.common.csv_export import ARRANQUES_PELIGROSOS, EscritorSeguro, celda_segura
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.reports.services import build_report, to_csv
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
ATAQUE = '=HYPERLINK("http://ejemplo.invalido","pincha")'


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.mark.parametrize("arranque", ARRANQUES_PELIGROSOS)
def test_ninguna_celda_empieza_como_una_formula(arranque):
    assert celda_segura(f"{arranque}algo").startswith("'")


def test_lo_corriente_no_se_toca():
    """El apóstrofo se ve en un editor de texto, así que solo donde hace falta."""
    for normal in ("Ana García", "08:00", "2026-08-26", "", "Permiso por mudanza"):
        assert celda_segura(normal) == normal


def test_el_escritor_neutraliza_toda_la_fila():
    buffer = io.StringIO()
    EscritorSeguro(buffer, delimiter=";", lineterminator="\n").writerow(["Ana", ATAQUE, "08:00"])
    assert buffer.getvalue() == 'Ana;"\'=HYPERLINK(""http://ejemplo.invalido"",""pincha"")";08:00\n'


@pytest.mark.django_db
def test_el_informe_que_se_entrega_no_lleva_formulas(company):
    """Por el nombre, que es lo que más se ve, y de punta a punta."""
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="ana@example.com",
            password=PASSWORD,
            tenant=company,
            first_name=ATAQUE,
            last_name="García",
        )
        register_punch(employee=quien, company=company)
        hoy = local_today(company)
        informe = build_report(
            employee=quien, company=company, date_from=hoy, date_to=hoy
        )
        salida = to_csv(informe)

    for numero, linea in enumerate(salida.split("\n"), start=1):
        for celda in linea.split(";"):
            limpia = celda.strip('"')
            assert limpia[:1] not in ARRANQUES_PELIGROSOS, (
                f"la línea {numero} tiene una celda que Excel evaluaría: {celda!r}"
            )

    # Contraste: si el nombre no llegara al fichero, lo de arriba pasaría sin
    # comprobar nada.
    assert "HYPERLINK" in salida, "el nombre no llegó al informe: no se está midiendo"
