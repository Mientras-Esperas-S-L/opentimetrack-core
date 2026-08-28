"""Las diferencias del art. 34.2 que ya tendrían que estar compensadas.

El artículo deja repartir la jornada de forma desigual y **no** deja que la
cuenta quede abierta: «las diferencias derivadas de la distribución irregular de
la jornada deberán quedar compensadas en el plazo de doce meses desde que se
produzcan», salvo que el convenio diga otro plazo.

Esto había estado **descartado a propósito**, y el descarte era bueno. Decía dos
cosas:

1. El plazo solo rige «en defecto de pacto», y el producto no sabía si lo había.
2. Para medirlo haría falta la distribución ordinaria contra la que comparar, y
   el cuadrante **es** la distribución.

La primera se resuelve preguntándolo: el plazo lo declara la empresa. La segunda
sigue en pie para el 10 % del párrafo primero ---que sigue sin calcularse--- y
**no alcanza a esto**, con una condición que es la mitad del asunto: **solo se
cuenta cuando la jornada se pactó por año**.

Una cifra anual ya viene neta de vacaciones y festivos. Una semanal no: 40 por 52
son 2.080 horas que no trabaja nadie, y restar eso de lo fichado convertiría las
vacaciones de cualquiera en una deuda de ciento y pico horas. Ese falso positivo
es el que estas pruebas fijan.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.irregular import irregular_balance
from apps.punches.models import Punch, PunchType
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import HoursPeriod, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"

#: Se mira desde aquí. Con doce meses de plazo, el año que toca cuadrar es 2024:
#: 2025 acabó en diciembre y tiene hasta diciembre de 2026.
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


def alguien(company, *, email, horas, periodo=HoursPeriod.YEAR, empezo=date(2020, 1, 1)):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Anual",
        last_name=email.split("@")[0],
        regime=WorkingTimeRegime.FULL_TIME,
        contracted_hours=horas,
        contracted_period=periodo,
        contract_start=empezo,
    )


def trabaja(company, quien, horas_totales, *, year=EL_AÑO):
    """Reparte esas horas en jornadas de ocho, desde enero de ese año."""
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


def codigos(company):
    return [
        f.code
        for f in review_roster(company=company, first=MIRANDO - timedelta(days=7), last=MIRANDO)
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("trabajadas", "avisa"),
    [(1700, False), (1780, True), (1600, True)],
    ids=["cuadra", "ochenta de más", "cien de menos"],
)
def test_el_saldo_del_ano_vencido(company, trabajadas, avisa):
    """Por exceso **y por defecto**: el artículo nombra las dos.

    Haber trabajado de menos también es una diferencia que compensar, y a quien
    la tiene le interesa saberlo antes de que se la reclamen de golpe.
    """
    with tenant_context(company.id):
        quien = alguien(company, email=f"anual{trabajadas}@example.com", horas=1700)
        trabaja(company, quien, trabajadas)

        saldo = irregular_balance(employee=quien, company=company, day=MIRANDO)
        assert saldo["year"] == EL_AÑO
        assert saldo["settled"] is not avisa
        assert ("irregular_hours_unsettled" in codigos(company)) is avisa


@pytest.mark.django_db
def test_con_jornada_semanal_no_se_contesta(company):
    """**El falso positivo que esta condición evita.**

    Con jornada semanal, la referencia sería 40 por 52 = 2.080 horas, y nadie
    trabaja eso: hay vacaciones, festivos y bajas de por medio. Quien trabajó
    1.700 horas ---una jornada perfectamente normal--- saldría con 380 horas de
    «deuda» que no debe.

    Se contesta `None` en vez de una resta que suma vacaciones como si fueran
    horas debidas.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="semanal@example.com", horas=40, periodo=HoursPeriod.WEEK)
        trabaja(company, quien, 1700)

        assert irregular_balance(employee=quien, company=company, day=MIRANDO) is None
        assert "irregular_hours_unsettled" not in codigos(company)


@pytest.mark.django_db
def test_el_ano_que_sigue_en_plazo_no_se_mira(company):
    """2025 no se toca hasta que pasen sus doce meses.

    Acusar de no haber compensado a quien está dentro del plazo es acusar a quien
    va en regla. Con el mismo desfase puesto en 2025 en vez de en 2024, no hay
    aviso.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="enplazo@example.com", horas=1700)
        trabaja(company, quien, 1780, year=2025)

        saldo = irregular_balance(employee=quien, company=company, day=MIRANDO)
        # Mira 2024, que está vacío: ahí el desfase es de las 1.700 enteras.
        assert saldo["year"] == EL_AÑO
        # Y el desfase de 2025 no cuenta todavía.
        assert saldo["worked_hours"] == 0


@pytest.mark.django_db
def test_un_plazo_de_cero_apaga_la_cuenta(company):
    """Hay convenios que remiten a un cómputo distinto del plazo.

    Forzar un número inventado sería peor que callar, así que un cero apaga la
    comprobación entera.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.irregular_settlement_months = 0
        reglas.save(update_fields=["irregular_settlement_months"])

        quien = alguien(company, email="apagado@example.com", horas=1700)
        trabaja(company, quien, 1780)

        assert irregular_balance(employee=quien, company=company, day=MIRANDO) is None
        assert "irregular_hours_unsettled" not in codigos(company)


@pytest.mark.django_db
def test_un_plazo_mas_largo_retrasa_la_cuenta(company):
    """El contraste del anterior: el plazo del convenio manda de verdad.

    Con veinticuatro meses, el año que toca cuadrar en 2026 es 2023 y no 2024.
    Si el plazo no se leyera, este saldo hablaría del año equivocado.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.irregular_settlement_months = 24
        reglas.save(update_fields=["irregular_settlement_months"])

        quien = alguien(company, email="dosanos@example.com", horas=1700)
        saldo = irregular_balance(employee=quien, company=company, day=MIRANDO)
        assert saldo["year"] == 2023
        assert saldo["months"] == 24


@pytest.mark.django_db
def test_quien_entro_a_mitad_de_ese_ano_no_se_compara(company):
    """Una cifra anual entera no se compara con medio año trabajado.

    Prorratearla sería inventar la parte que le tocaba, y ese invento se leería
    como un hecho.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="amitad@example.com", horas=1700, empezo=date(EL_AÑO, 7, 1))
        trabaja(company, quien, 800)
        assert irregular_balance(employee=quien, company=company, day=MIRANDO) is None


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company):
    """`User.objects` no acota por empresa, y aquí las personas salen de ahí."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B30303030", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        suyo = alguien(vecina, email="suyo@vecina.example", horas=1700)
        trabaja(vecina, suyo, 1780)

    with tenant_context(company.id):
        propio = alguien(company, email="propio@example.com", horas=1700)
        trabaja(company, propio, 1780)

        avisos = review_roster(company=company, first=MIRANDO - timedelta(days=7), last=MIRANDO)
        de_quien = {f.employee_id for f in avisos if f.code == "irregular_hours_unsettled"}

        assert propio.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suyo.id not in de_quien
