"""Las dos noches del año que no duran veinticuatro horas, en el documento.

`apps/common/dst.py` lo explica: quien entra a las 22:00 y sale a las 06:00
trabaja **siete** horas la noche de marzo y **nueve** la de octubre. Los fichajes
guardan instantes reales, así que la cifra sale bien... en la pantalla.

En el informe no salía. `build_report` restaba dos horas **ya convertidas a la
zona local**, y dos `datetime` que comparten `tzinfo` se restan como reloj de
pared: de 22:00 a 06:00 daba ocho horas los 365 días del año. Medido:

    noche del 25 de octubre   real 9 h   pantalla 9 h   informe 8 h
    noche del 29 de marzo     real 7 h   pantalla 7 h   informe 8 h
    una noche cualquiera      real 8 h   pantalla 8 h   informe 8 h

Esto es el documento del art. 34.9, y la ley va por el tiempo efectivamente
trabajado: en octubre le quitaba una hora a quien la había trabajado, y en marzo
le atribuía una que no. Dos noches al año, toda la plantilla que hace noches.

La noche corriente está aquí a propósito: sin ella, las dos primeras pasarían
igual si el cálculo estuviera roto de otra manera.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.punches.services import build_day_status
from apps.reports.services import build_report, to_csv
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: En 2026 los relojes se adelantan el 29 de marzo y se atrasan el 25 de octubre.
#: El turno empieza la víspera, que es el día al que pertenece la jornada.
NOCHES = [
    # etiqueta, día de la jornada, entrada UTC, salida UTC, horas reales
    (
        "otoño",
        date(2026, 10, 24),
        datetime(2026, 10, 24, 20, tzinfo=UTC),
        datetime(2026, 10, 25, 5, tzinfo=UTC),
        9,
    ),
    (
        "primavera",
        date(2026, 3, 28),
        datetime(2026, 3, 28, 21, tzinfo=UTC),
        datetime(2026, 3, 29, 4, tzinfo=UTC),
        7,
    ),
    (
        "corriente",
        date(2026, 9, 8),
        datetime(2026, 9, 8, 20, tzinfo=UTC),
        datetime(2026, 9, 9, 4, tzinfo=UTC),
        8,
    ),
]


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Noche SL", tax_id="B11111111", time_zone="Europe/Madrid")


def _turno(empresa, dia, entra, sale, correo):
    quien = User.objects.create_user(
        email=correo, password=PASSWORD, tenant=empresa, first_name="Noc", last_name="Turno"
    )
    Shift.objects.create(
        tenant=empresa, employee=quien, day=dia, segments=[{"start": "22:00", "end": "06:00"}]
    )
    for cuando, tipo in ((entra, PunchType.IN), (sale, PunchType.OUT)):
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type=tipo,
            interval=PunchInterval.WORK,
            timestamp=cuando,
        )
    return quien


@pytest.mark.django_db
@pytest.mark.parametrize(("etiqueta", "dia", "entra", "sale", "horas"), NOCHES)
def test_el_informe_da_las_horas_reales(empresa, etiqueta, dia, entra, sale, horas):
    with tenant_context(empresa.id):
        quien = _turno(empresa, dia, entra, sale, f"{etiqueta}@example.com")
        informe = build_report(employee=quien, company=empresa, date_from=dia, date_to=dia)

    assert informe.rows[0].seconds == horas * 3600, (
        f"la noche de {etiqueta} son {horas} horas reales y el informe dice "
        f"{informe.rows[0].seconds / 3600}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(("etiqueta", "dia", "entra", "sale", "horas"), NOCHES)
def test_la_pantalla_y_el_documento_cuentan_igual(empresa, etiqueta, dia, entra, sale, horas):
    """Lo que el propio código dice de sí mismo: «la cifra en pantalla y la del
    documento son el mismo día». Lo decía y no se cumplía."""
    with tenant_context(empresa.id):
        quien = _turno(empresa, dia, entra, sale, f"{etiqueta}-par@example.com")
        pantalla = build_day_status(quien, empresa, dia)
        informe = build_report(employee=quien, company=empresa, date_from=dia, date_to=dia)

    assert informe.rows[0].seconds == pantalla.worked_seconds, (
        f"la noche de {etiqueta}: la pantalla dice {pantalla.worked_seconds / 3600} h "
        f"y el documento {informe.rows[0].seconds / 3600} h"
    )


@pytest.mark.django_db
def test_y_el_csv_que_se_entrega_lleva_esa_cifra():
    """El total del fichero, que es lo que acaba en manos de la Inspección."""
    company = Tenant.objects.create(name="Noche SL", tax_id="B22222222", time_zone="Europe/Madrid")
    dia = date(2026, 10, 24)
    with tenant_context(company.id):
        quien = _turno(
            company,
            dia,
            datetime(2026, 10, 24, 20, tzinfo=UTC),
            datetime(2026, 10, 25, 5, tzinfo=UTC),
            "csv@example.com",
        )
        texto = to_csv(build_report(employee=quien, company=company, date_from=dia, date_to=dia))

    assert "09:00" in texto, f"el CSV no lleva las nueve horas:\n{texto}"
    assert "Total;09:00" in texto.replace("\r", "")
