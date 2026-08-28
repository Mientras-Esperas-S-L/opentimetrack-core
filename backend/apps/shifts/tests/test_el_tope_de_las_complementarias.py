"""El tope de horas complementarias del art. 12.5.c, y sobre qué periodo va.

El aviso de `_check_weekly_hours` llevaba tiempo diciendo que las horas por
encima del contrato «cuentan para su propio límite». **Ese límite no lo llevaba
nadie.** Era una promesa que el producto hacía en pantalla y no cumplía.

El enunciado del inventario decía «el tope **mensual** del 30 % no se acumula», y
contaba mal dos veces:

1. **No es mensual.** El art. 12.5.c habla del «treinta por ciento de las horas
   ordinarias de trabajo objeto del contrato», y el objeto se pacta por semana,
   por mes o por año (art. 12.1). Un contrato de 800 horas al año tiene 240
   complementarias **al año**, no 20 al mes. Repartirlas por meses inventaría un
   límite que nadie pactó, que es lo mismo que este proyecto ya se negó a hacer
   en `agreed_hours` --- dividir 1700 horas anuales entre 52 da un número que no
   está en ningún contrato.

2. **No había nada que acumular.** El campo `hours_nature` existe y la API lo
   acepta, pero ninguna pantalla lo manda: la marca no la escribe nadie. La
   cuenta se deriva, que además es como las define el art. 12.5.a --- las
   realizadas como adición a las ordinarias pactadas ---.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.complementary import complementary_used
from apps.punches.models import Punch, PunchType
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import HoursPeriod, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"

#: Lunes 3 de agosto de 2026, y su domingo.
LUNES = date(2026, 8, 3)
DOMINGO = LUNES + timedelta(days=6)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Parcial SL", tax_id="B19191919", time_zone="Europe/Madrid", country="ES"
    )


def alguien(company, *, email, regime, hours, period):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Parcial",
        last_name="Uno",
        regime=regime,
        contracted_hours=hours,
        contracted_period=period,
    )


def trabaja(company, quien, day, horas):
    """Un día de trabajo de la duración pedida, entrada y salida."""
    entra = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=6)
    Punch.objects.create(tenant=company, employee=quien, timestamp=entra, punch_type=PunchType.IN)
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra + timedelta(hours=horas),
        punch_type=PunchType.OUT,
    )


def codigos(company, first, last):
    return [f.code for f in review_roster(company=company, first=first, last=last)]


@pytest.mark.django_db
def test_pasarse_del_treinta_por_ciento_avisa(company):
    """20 h a la semana admiten 6 complementarias. Trabaja 28: son 8."""
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="semanal@example.com",
            regime=WorkingTimeRegime.PART_TIME,
            hours=20,
            period=HoursPeriod.WEEK,
        )
        for offset in range(4):
            trabaja(company, quien, LUNES + timedelta(days=offset), 7)

        cuenta = complementary_used(employee=quien, company=company, day=DOMINGO)
        assert cuenta["worked_hours"] == 28
        assert cuenta["complementary_hours"] == 8
        assert cuenta["cap_hours"] == 6
        assert cuenta["over_the_cap"] is True

        assert "complementary_hours_cap" in codigos(company, LUNES, DOMINGO)


@pytest.mark.django_db
def test_quedarse_por_debajo_no_avisa(company):
    """El contraste. Sin él, «avisa al pasarse» y «avisa siempre» se ven igual.

    24 h contra 20 son 4 complementarias, y caben en las 6 que permite el 30 %.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="justito@example.com",
            regime=WorkingTimeRegime.PART_TIME,
            hours=20,
            period=HoursPeriod.WEEK,
        )
        for offset in range(4):
            trabaja(company, quien, LUNES + timedelta(days=offset), 6)

        cuenta = complementary_used(employee=quien, company=company, day=DOMINGO)
        assert cuenta["complementary_hours"] == 4
        assert cuenta["over_the_cap"] is False

        assert "complementary_hours_cap" not in codigos(company, LUNES, DOMINGO)


@pytest.mark.django_db
def test_un_contrato_anual_no_se_mide_por_meses(company):
    """**La prueba que fija la lectura del artículo.**

    800 horas al año admiten 240 complementarias al año. Quien las tiene puede
    trabajar 100 horas en una semana de agosto sin haberse pasado de nada: le
    quedan 940 de las 1.040 que su contrato permite en total.

    Si el tope se hubiera repartido por meses ---las «20 al mes» del enunciado
    del inventario--- esto avisaría, y avisaría de un límite que no existe: el
    contrato anual es justamente el que deja concentrar el trabajo en la
    temporada. Es el error que este proyecto ya evitó una vez al negarse a
    convertir 1700 horas anuales en una cifra semanal.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="anual@example.com",
            regime=WorkingTimeRegime.PART_TIME,
            hours=800,
            period=HoursPeriod.YEAR,
        )
        for offset in range(5):
            trabaja(company, quien, LUNES + timedelta(days=offset), 20)

        cuenta = complementary_used(employee=quien, company=company, day=DOMINGO)
        assert cuenta["period"] == HoursPeriod.YEAR
        assert cuenta["worked_hours"] == 100
        assert cuenta["cap_hours"] == 240
        # Cien horas están muy por debajo de las 800 pactadas para el año, así
        # que ni siquiera hay complementarias todavía.
        assert cuenta["complementary_hours"] == 0
        assert cuenta["over_the_cap"] is False

        assert "complementary_hours_cap" not in codigos(company, LUNES, DOMINGO)


@pytest.mark.django_db
def test_a_jornada_completa_la_figura_no_existe(company):
    """Las complementarias son del art. 12: fuera del tiempo parcial no las hay.

    Quien está a jornada completa y trabaja de más hace horas
    **extraordinarias**, que tienen su propio tope y su propia decisión. Aplicar
    aquí el 30 % le pondría un límite inventado y, peor, lo llamaría por el
    nombre de otra cosa.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="completa@example.com",
            regime=WorkingTimeRegime.FULL_TIME,
            hours=40,
            period=HoursPeriod.WEEK,
        )
        for offset in range(6):
            trabaja(company, quien, LUNES + timedelta(days=offset), 10)

        assert complementary_used(employee=quien, company=company, day=DOMINGO) is None
        assert "complementary_hours_cap" not in codigos(company, LUNES, DOMINGO)


@pytest.mark.django_db
def test_quien_no_tiene_cuadrante_tambien_se_revisa(company):
    """El agujero que este chequeo no podía repetir.

    Las demás comprobaciones leen el cuadrante, y quien no tiene turnos
    planificados no tenía **ninguna**. Es justo quien más fácilmente se pasa sin
    que nadie mire, así que las personas de este aviso salen del registro.

    La prueba lo fija sin crear ni un turno: si algún día alguien reescribe esto
    para recorrer el cuadrante, se pone roja.
    """
    from apps.shifts.models import Shift

    with tenant_context(company.id):
        quien = alguien(
            company,
            email="sin-cuadrante@example.com",
            regime=WorkingTimeRegime.PART_TIME,
            hours=10,
            period=HoursPeriod.WEEK,
        )
        for offset in range(3):
            trabaja(company, quien, LUNES + timedelta(days=offset), 8)

        assert not Shift.objects.filter(employee=quien).exists()
        assert "complementary_hours_cap" in codigos(company, LUNES, DOMINGO)


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company):
    """Nadie de otra empresa sale en este aviso, y hay dos capas que lo impiden.

    `User.objects` **no** acota por empresa ---su propio docstring lo dice:
    «Manager without tenant filtering», porque al entrar todavía no se sabe de
    qué empresa es quien entra---, así que la persona de al lado sí llega a
    entrar en la lista de candidatas. El guard de aislamiento lo señaló, y por
    eso la consulta lleva un `tenant=` explícito.

    Lo comprobado, que conviene no confundir con lo supuesto: **quitando ese
    `tenant=` esta prueba sigue pasando**. La fuga la corta más adentro
    `Punch.objects`, que sí filtra por contexto, de modo que los fichajes ajenos
    no se ven y no hay nada que sumar. El `tenant=` es la defensa explícita y la
    de dentro es la que hoy hace el trabajo.

    Lo que la prueba fija es el resultado, no cuál de las dos lo consigue: si un
    día se toca cualquiera de ellas y alguien ajeno acaba en un aviso, se pone
    roja. La vecina está en el peor caso posible: mismo régimen, mismas fechas y
    pasadísima del tope.
    """
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B20202020", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        suya = alguien(
            vecina,
            email="suya@vecina.example",
            regime=WorkingTimeRegime.PART_TIME,
            hours=10,
            period=HoursPeriod.WEEK,
        )
        for offset in range(5):
            trabaja(vecina, suya, LUNES + timedelta(days=offset), 9)

    with tenant_context(company.id):
        propia = alguien(
            company,
            email="propia@example.com",
            regime=WorkingTimeRegime.PART_TIME,
            hours=10,
            period=HoursPeriod.WEEK,
        )
        for offset in range(5):
            trabaja(company, propia, LUNES + timedelta(days=offset), 9)

        avisos = review_roster(company=company, first=LUNES, last=DOMINGO)
        de_quien = {f.employee_id for f in avisos if f.code == "complementary_hours_cap"}

        # El contraste va dentro: si no saliera **ninguno**, esta prueba pasaría
        # con el aviso roto y no diría nada del aislamiento.
        assert propia.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suya.id not in de_quien
