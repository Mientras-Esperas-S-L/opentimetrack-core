"""El documento del art. 6.1 no es el del art. 34.9, y tiene que decirlo.

`/reports/payroll-summary/` devuelve tres cosas distintas según el formato. En
JSON contestaba el resumen que pide el art. 6.1 ---totales del periodo, régimen,
jornada pactada---, y en PDF y CSV entregaba **el registro diario completo**:
titulado «Registro de jornada», que es el nombre del documento del art. 34.9, en
un fichero llamado `resumen_…`.

O sea: la pantalla y el documento no decían lo mismo, y el papel que acompaña al
recibo de salarios se presentaba como otro papel.

El detalle diario se queda ---informa de más, no de menos---; lo que cambia es que
el documento diga qué es y lleve las dos cifras que lo hacen ser ese y no el
otro. El sistema ya las calculaba.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.reports.pdf import render_pdf
from apps.reports.services import build_report, to_csv
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
DIA = date(2026, 8, 14)


@pytest.fixture
def informe(db):
    empresa = Tenant.objects.create(name="Nomina SL", tax_id="B99999999", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="nomina@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            last_name="Nomina",
        )
        for hora, tipo in ((8, PunchType.IN), (16, PunchType.OUT)):
            Punch.objects.create(
                tenant=empresa,
                employee=quien,
                punch_type=tipo,
                interval=PunchInterval.WORK,
                timestamp=datetime(2026, 8, 14, hora - 2, tzinfo=UTC),
            )
        yield build_report(employee=quien, company=empresa, date_from=DIA, date_to=DIA)


def test_el_resumen_se_titula_resumen(informe):
    texto = to_csv(informe, para_nomina=True)
    primera = texto.splitlines()[0]

    assert "Summary" in primera or "Resumen" in primera, (
        f"el documento que acompaña al recibo de salarios se titula «{primera}»"
    )
    assert "6.1" in texto, "y tiene que decir de dónde sale la obligación"


def test_y_lleva_lo_que_lo_hace_ser_ese_documento(informe):
    """Régimen y jornada pactada: contra eso se miden las horas del periodo, y
    es lo que la respuesta en JSON ya devolvía mientras el fichero se lo callaba."""
    texto = to_csv(informe, para_nomina=True)

    assert informe.regime and informe.regime in texto, "falta el régimen"
    assert informe.contracted_hours and informe.contracted_hours in texto, (
        "falta la jornada pactada"
    )


def test_el_registro_del_articulo_34_9_no_cambia(informe):
    """El contraste, y es la mitad que importa: sin él, esto pasaría igual si el
    otro documento se hubiera convertido también en un resumen."""
    texto = to_csv(informe)
    primera = texto.splitlines()[0]

    assert "Summary" not in primera and "Resumen" not in primera, (
        f"el documento del art. 34.9 se ha vuelto un resumen: «{primera}»"
    )
    assert "6.1" not in texto
    assert informe.regime not in texto or informe.regime == ""


def test_el_pdf_hace_lo_mismo(informe):
    """Los bytes, no la extensión: un PDF empieza por `%PDF`."""
    resumen = render_pdf(informe, para_nomina=True)
    registro = render_pdf(informe)

    assert resumen.startswith(b"%PDF") and registro.startswith(b"%PDF")
    assert resumen != registro, "el resumen y el registro salían byte a byte iguales"
