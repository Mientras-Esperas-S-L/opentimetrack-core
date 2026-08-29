"""Las horas del art. 34.2 que se devuelven en descanso.

«Las diferencias derivadas de la distribución irregular de la jornada deberán
quedar compensadas en el plazo de doce meses desde que se produzcan», salvo que
el convenio diga otro plazo.

La cuenta ya estaba: `irregular_balance` dice desde la vuelta 158 cuántas horas
de un año vencido siguen sin compensar, por exceso y por defecto. Lo que faltaba
era **llevarlas a la cuenta de lo que se debe en descanso**, que es como se
devuelven las de exceso.

Dos decisiones que se ven mejor aquí que en el código:

- **Solo el exceso.** El saldo va en las dos direcciones y las dos hay que
  compensarlas, pero lo que se devuelve con descanso es haber trabajado de más.
  Haber trabajado de menos se compensa trabajando, y meterlo aquí en negativo
  restaría de lo que se debe por otras fuentes, que no tienen nada que ver.
- **Nace fuera de plazo.** `irregular_balance` mira un año **vencido**: si esas
  horas siguen ahí, el plazo del artículo ya pasó. Es la única fuente que entra
  directamente en lo vencido en vez de en lo pendiente.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.punches.rest_debt import rest_debt
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import HoursPeriod, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"
#: Igual que en las pruebas del saldo: con doce meses de plazo, el año que toca
#: cuadrar en agosto de 2026 es 2024.
MIRANDO = date(2026, 8, 28)
EL_AÑO = 2024


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Irregular SL", tax_id="B29292929", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.weekly_hours = 40
        reglas.save(update_fields=["weekly_hours"])
    return empresa


def alguien(company, *, email, horas=1700, periodo=HoursPeriod.YEAR):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Anual",
        regime=WorkingTimeRegime.FULL_TIME,
        contracted_hours=horas,
        contracted_period=periodo,
        contract_start=date(2020, 1, 1),
    )


def trabaja(company, quien, horas_totales, *, year=EL_AÑO):
    dia = date(year, 1, 8)
    restan = horas_totales
    while restan > 0:
        cuanto = min(8, restan)
        entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=6)
        Punch.objects.create(
            tenant=company, employee=quien, timestamp=entra, punch_type=PunchType.IN
        )
        Punch.objects.create(
            tenant=company,
            employee=quien,
            timestamp=entra + timedelta(hours=cuanto),
            punch_type=PunchType.OUT,
        )
        restan -= cuanto
        dia += timedelta(days=1)


def la_fuente(company, quien):
    with tenant_context(company.id):
        saldo = rest_debt(employee=quien, company=company, day=MIRANDO)
    if not saldo:
        return None
    return next((f for f in saldo["sources"] if f["source"] == "irregular"), None)


@pytest.mark.django_db
def test_las_horas_de_mas_se_deben_en_descanso(company):
    """Ochenta horas por encima de lo pactado en un año ya vencido."""
    with tenant_context(company.id):
        quien = alguien(company, email="exceso@example.com")
        trabaja(company, quien, 1780)

    fuente = la_fuente(company, quien)
    assert fuente["owed_hours"] == 80
    assert fuente["citation"] == "Art. 34.2 ET"
    assert fuente["year"] == EL_AÑO


@pytest.mark.django_db
def test_y_nacen_fuera_de_plazo(company):
    """El plazo del artículo ya pasó: por eso ese año es el que toca cuadrar.

    Contarlas como pendientes diría que aún hay tiempo, y no lo hay. Es la única
    fuente que entra directa en lo vencido.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="vencido@example.com")
        trabaja(company, quien, 1780)

        saldo = rest_debt(employee=quien, company=company, day=MIRANDO)

    fuente = next(f for f in saldo["sources"] if f["source"] == "irregular")
    assert fuente["overdue_hours"] == 80
    assert fuente["due_on"] is None
    assert saldo["overdue_hours"] >= 80


@pytest.mark.django_db
def test_haber_trabajado_de_menos_no_es_deuda_de_descanso(company):
    """**La decisión que evita restar de lo que se debe por otra cosa.**

    Cien horas por debajo de lo pactado también son una diferencia que compensar
    ---y el saldo del art. 34.2 lo dice--- pero se compensan trabajando, no
    descansando. En negativo aquí bajarían la deuda de horas extra, que no tiene
    ninguna relación.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="defecto@example.com")
        trabaja(company, quien, 1600)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_un_ano_cuadrado_no_debe_nada(company):
    """El contraste de todo lo demás: sin diferencia no hay deuda."""
    with tenant_context(company.id):
        quien = alguien(company, email="cuadra@example.com")
        trabaja(company, quien, 1700)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_con_jornada_semanal_no_se_cuenta(company):
    """El falso positivo que `irregular_balance` evita, y que aquí no puede volver.

    Con jornada semanal la referencia serían 40 por 52 = 2.080 horas, que no
    trabaja nadie: quien hizo 1.700 saldría con 380 de «deuda» que no debe, y
    ahora además aparecerían en la pantalla de lo que tiene que descansar.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="semanal@example.com", horas=40, periodo=HoursPeriod.WEEK)
        trabaja(company, quien, 1700)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_un_plazo_apagado_no_cuenta(company):
    """Si la empresa apaga el plazo, tampoco hay saldo que llevar aquí."""
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.irregular_settlement_months = 0
        reglas.save(update_fields=["irregular_settlement_months"])

        quien = alguien(company, email="apagado@example.com")
        trabaja(company, quien, 1780)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_se_suma_a_las_demas_fuentes(company):
    """Y lo devuelto sigue restándose una sola vez, del total.

    Es lo que la segunda fuente obligó a rediseñar y lo que la tercera tiene que
    respetar: cada fuente dice lo que **genera**, la resta va sobre la suma.
    """
    from apps.punches.models import HoursNature, OvertimeSettlement

    with tenant_context(company.id):
        quien = alguien(company, email="dos@example.com")
        trabaja(company, quien, 1780)

        entra = datetime.combine(MIRANDO - timedelta(days=10), datetime.min.time(), tzinfo=UTC)
        entra = entra.replace(hour=16)
        for momento, tipo in ((entra, PunchType.IN), (entra + timedelta(hours=4), PunchType.OUT)):
            Punch.objects.create(
                tenant=company,
                employee=quien,
                timestamp=momento,
                punch_type=tipo,
                hours_nature=HoursNature.OVERTIME,
                overtime_settlement=OvertimeSettlement.REST,
            )

        saldo = rest_debt(employee=quien, company=company, day=MIRANDO)

    assert {f["source"] for f in saldo["sources"]} == {"overtime", "irregular"}
    assert saldo["owed_hours"] == 84, "80 del art. 34.2 y 4 de horas extra"
