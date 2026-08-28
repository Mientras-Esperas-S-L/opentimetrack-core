"""Los días de vacaciones que el convenio suma por antigüedad.

**No salen del Estatuto.** El art. 38.1 fija treinta días naturales al año y no
dice ni una palabra de la antigüedad: estos días los da el convenio. Por eso la
escala la declara la empresa y vive en sus reglas, no en el marco legal del país
---donde están las cifras que la ley impone y que nadie puede bajar---.

Y hay un caso que decide el diseño: **`contract_start` puede estar vacío.** El
campo lo admite a propósito ---«ya estaba en marcha cuando la empresa empezó
aquí»--- y esa persona puede llevar veinte años. Tratar el hueco como cero años
le quitaría sus días justo a quien más antigüedad tiene, y el saldo no diría nada
raro: enseñaría los veintitrés de siempre. Así que no se estima, no se suma, y se
avisa.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.services import seniority_days, vacation_balance
from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
MIRANDO = date(2026, 8, 24)
AL_AÑO = 22

#: A los cinco años, un día más; a los quince, dos.
ESCALA = [{"years": 5, "extra_days": 1}, {"years": 15, "extra_days": 2}]


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd",
        tax_id="B11111111",
        time_zone="Europe/Madrid",
        country="ES",
        annual_leave_days=AL_AÑO,
        leave_days_are_working_days=False,
    )


def con_escala(company, escala=ESCALA):
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.seniority_leave = escala
        reglas.save(update_fields=["seniority_leave"])


def alguien(company, *, email, empezo):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Quien",
        contract_start=empezo,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("años", "extra"),
    [(0, 0), (4, 0), (5, 1), (14, 1), (15, 2), (30, 2)],
)
def test_la_escala_del_convenio(company, años, extra):
    """Los tramos y sus bordes: «a partir de cinco» incluye el quinto año."""
    con_escala(company)
    with tenant_context(company.id):
        quien = alguien(
            company, email=f"a{años}@example.com", empezo=MIRANDO - timedelta(days=365 * años + 1)
        )
        dias, servidos, sin_saber = seniority_days(quien, company, MIRANDO)

        assert dias == extra
        assert servidos == años
        assert sin_saber is False


@pytest.mark.django_db
def test_sin_escala_declarada_no_suma_nada(company):
    """**El contraste de todo lo demás.**

    Estos días no los da la ley. Sin convenio que los conceda, sumarlos sería
    regalar vacaciones que nadie ha pactado, y encima con cargo a la empresa.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="sin@example.com", empezo=date(2000, 1, 1))
        assert seniority_days(quien, company, MIRANDO) == (0.0, None, False)


@pytest.mark.django_db
def test_sin_fecha_de_contrato_no_se_estima_y_se_dice(company):
    """**La decisión que evita quitarle días a quien más lleva.**

    El campo admite estar vacío para quien ya estaba cuando la empresa empezó a
    usar el producto, que es justamente el perfil con más antigüedad. Contarle
    cero años le daría el saldo básico sin que nada pareciera fuera de sitio.
    """
    con_escala(company)
    with tenant_context(company.id):
        quien = alguien(company, email="sinfecha@example.com", empezo=None)
        dias, servidos, sin_saber = seniority_days(quien, company, MIRANDO)

        assert dias == 0
        assert servidos is None
        assert sin_saber is True, "hay escala y no se ha podido aplicar: eso se dice"


@pytest.mark.django_db
def test_el_saldo_los_suma_y_los_explica(company):
    """«22 + 1 por antigüedad» es una frase que alguien puede comprobar; «23» no.

    Y aquí se ve una decisión que no es obvia: los años se cuentan **al final del
    periodo de cómputo**, no a día de hoy. Quien entró el 1 de enero de 2015 lleva
    once años en agosto de 2026 y doce el 31 de diciembre, que es cuando se
    devengan las vacaciones de 2026. Medirlo hoy haría que el saldo de un periodo
    cambiara solo al cumplir años dentro de él.
    """
    con_escala(company)
    with tenant_context(company.id):
        quien = alguien(company, email="saldo@example.com", empezo=date(2015, 1, 1))
        saldo = vacation_balance(quien, company, MIRANDO)

        assert saldo.seniority_years == 12, "al cierre del periodo, no a día de hoy"
        # Doce años: le toca el tramo de cinco, no el de quince.
        assert saldo.seniority_days == 1
        assert saldo.full_year == AL_AÑO + 1
        assert saldo.entitled == AL_AÑO + 1


@pytest.mark.django_db
def test_el_tramo_alto_cuando_de_verdad_le_toca(company):
    """El contraste del anterior: con veintiún años sí entra el tramo de quince.

    Sin esta, la prueba de arriba pasaría igual con una escala que ignorase el
    segundo tramo entero.
    """
    con_escala(company)
    with tenant_context(company.id):
        quien = alguien(company, email="veterana@example.com", empezo=date(2005, 1, 1))
        saldo = vacation_balance(quien, company, MIRANDO)

        assert saldo.seniority_days == 2
        assert saldo.full_year == AL_AÑO + 2


@pytest.mark.django_db
def test_los_extra_se_prorratean_como_los_demas(company):
    """Quien entra a mitad de año devenga la parte que le toca, también de estos.

    Sumarlos después del prorrateo daría el día entero a quien trabajó medio año,
    que es la incoherencia contraria a la que arregló el devengo proporcional.
    """
    con_escala(company, [{"years": 0, "extra_days": 2}])
    with tenant_context(company.id):
        quien = alguien(company, email="mitad@example.com", empezo=date(2026, 7, 1))
        saldo = vacation_balance(quien, company, MIRANDO)

        # Veinticuatro al año por los 184 días que van del 1 de julio al 31 de
        # diciembre: 12,1, y **al alza**, que es como se prorratea aquí ---a la
        # baja el peor caso es incumplir un mínimo legal---.
        assert saldo.full_year == 24
        assert saldo.entitled == 13

        # Y el contraste: sin los dos días de antigüedad serían 22 al año y once
        # devengados. Los extra se prorratean, no se regalan enteros.
        con_escala(company, [])
        assert vacation_balance(quien, company, MIRANDO).entitled == 12


@pytest.mark.django_db
def test_los_tramos_se_ordenan_aunque_lleguen_al_reves(company):
    """La empresa escribe su convenio en el orden que quiera.

    Tomar el último de la lista en vez del tramo más alto alcanzado daría un día
    a quien lleva veinte años porque el tramo de cinco estaba escrito al final.
    """
    con_escala(company, [{"years": 15, "extra_days": 2}, {"years": 5, "extra_days": 1}])
    with tenant_context(company.id):
        quien = alguien(company, email="orden@example.com", empezo=date(2000, 1, 1))
        assert seniority_days(quien, company, MIRANDO)[0] == 2


@pytest.mark.django_db
def test_se_avisa_de_quien_no_tiene_fecha(company):
    """Un dato que falta y que solo la empresa puede poner."""
    con_escala(company)
    with tenant_context(company.id):
        alguien(company, email="avisa@example.com", empezo=None)
        codigos = [
            f.code
            for f in review_roster(company=company, first=MIRANDO, last=MIRANDO + timedelta(days=6))
        ]
        assert "seniority_without_a_start_date" in codigos


@pytest.mark.django_db
def test_sin_escala_no_se_avisa_de_la_fecha(company):
    """El contraste del anterior: sin convenio que los dé, la fecha no hace falta.

    Media plantilla puede no tener fecha de contrato por razones perfectamente
    normales, y avisar de todas en una empresa sin días por antigüedad sería
    ruido para siempre.
    """
    with tenant_context(company.id):
        alguien(company, email="silencio@example.com", empezo=None)
        codigos = [
            f.code
            for f in review_roster(company=company, first=MIRANDO, last=MIRANDO + timedelta(days=6))
        ]
        assert "seniority_without_a_start_date" not in codigos
