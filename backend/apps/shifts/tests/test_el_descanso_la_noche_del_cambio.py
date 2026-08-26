"""El descanso entre jornadas la noche en que los relojes se mueven.

Un cuadrante guarda horas de reloj de pared: «acaba a las 22:00, empieza a las
10:00». Restar esos dos datetime da doce horas los 365 días del año --- son
naive y la resta no sabe de husos. La madrugada del último domingo de marzo,
entre esas dos horas de pared solo pasan **once**.

Ahí es donde importa. El suelo del art. 34.3 son doce horas de descanso entre
jornadas, así que un cuadrante que programe esas doce de pared la noche del
cambio deja a la persona con once reales, y hasta ahora nada avisaba: el aviso
se calculaba con la misma aritmética de pared que lo producía.

La noche de octubre va al revés ---trece horas--- y no incumple nada. Se prueba
también, porque un arreglo que empezara a avisar ahí sería peor que el defecto:
una advertencia falsa cada octubre, para toda la plantilla de noche a la vez.

La trampa está anotada en `apps.common.dst` desde que casi se lleva el módulo
por delante: restar dos `datetime` con el **mismo** `tzinfo` es aritmética de
reloj de pared, no de tiempo real.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from apps.common.dst import real_gap
from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: En 2026 los relojes se adelantan el domingo 29 de marzo y se atrasan el 25
#: de octubre. Se escriben las fechas y no se calculan: una fecha calculada mal
#: haría pasar la prueba por el sitio equivocado sin decirlo.
ADELANTAN = date(2026, 3, 29)
ATRASAN = date(2026, 10, 25)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Turnos de noche", tax_id="B55555555", time_zone="Europe/Madrid"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="noche@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Noche",
            last_name="Larga",
        )


def dos_turnos(company, quien, vispera: date, *, sale="22:00", entra="10:00"):
    """Uno que acaba por la noche y otro que empieza a la mañana siguiente."""
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company, employee=quien, day=vispera, segments=[{"start": "14:00", "end": sale}]
        )
        Shift.objects.create(
            tenant=company,
            employee=quien,
            day=vispera + timedelta(days=1),
            segments=[{"start": entra, "end": "18:00"}],
        )
        return review_roster(
            company=company, first=vispera, last=vispera + timedelta(days=1), employee=quien
        )


def descansos_cortos(hallazgos):
    return [h for h in hallazgos if h.code == "short_daily_rest"]


@pytest.mark.django_db
def test_doce_horas_de_reloj_son_once_cuando_el_reloj_se_adelanta(company, quien):
    """El caso: cumple sobre el papel y no cumple en la cama de nadie."""
    cortos = descansos_cortos(dos_turnos(company, quien, ADELANTAN - timedelta(days=1)))

    assert cortos, "doce horas de pared son once esa noche, y nada lo dijo"
    assert "11" in cortos[0].message, cortos[0].message
    # Y por qué. Quien lee el cuadrante ve 22:00 y 10:00 y cuenta doce: sin la
    # explicación, el aviso parece una cuenta mal hecha del programa y se
    # ignora justo la noche en que no hay que ignorarlo.
    assert "reloj" in cortos[0].message.lower() or "clock" in cortos[0].message.lower(), cortos[
        0
    ].message


@pytest.mark.django_db
def test_una_semana_normal_con_las_mismas_horas_no_avisa(company, quien):
    """El control. Sin esto, la de arriba pasaría igual con un aviso siempre.

    Mismas horas de pared, un fin de semana cualquiera: doce reales, y callar es
    lo correcto.
    """
    assert not descansos_cortos(dos_turnos(company, quien, date(2026, 5, 9)))


@pytest.mark.django_db
def test_la_noche_que_el_reloj_se_atrasa_no_inventa_un_incumplimiento(company, quien):
    """Trece horas reales. Avisar ahí sería peor que el defecto de partida."""
    assert not descansos_cortos(dos_turnos(company, quien, ATRASAN - timedelta(days=1)))


@pytest.mark.django_db
def test_y_sigue_avisando_de_un_descanso_corto_de_los_de_siempre(company, quien):
    """Ocho horas, sin cambio de hora de por medio: el aviso de toda la vida."""
    cortos = descansos_cortos(
        dos_turnos(company, quien, date(2026, 5, 11), sale="22:00", entra="06:00")
    )

    assert cortos, "un descanso de ocho horas ha dejado de avisar"
    assert "8" in cortos[0].message, cortos[0].message


@pytest.mark.django_db
def test_el_hueco_real_se_mide_en_las_dos_direcciones(company):
    """La pieza suelta, por si alguien la usa en otro sitio.

    Con la aritmética de pared las tres respuestas serían doce.
    """
    sale = datetime.combine(ADELANTAN - timedelta(days=1), time(22, 0))
    entra = datetime.combine(ADELANTAN, time(10, 0))
    assert real_gap(sale, entra, company).total_seconds() / 3600 == 11

    sale = datetime.combine(ATRASAN - timedelta(days=1), time(22, 0))
    entra = datetime.combine(ATRASAN, time(10, 0))
    assert real_gap(sale, entra, company).total_seconds() / 3600 == 13

    sale = datetime.combine(date(2026, 5, 9), time(22, 0))
    entra = datetime.combine(date(2026, 5, 10), time(10, 0))
    assert real_gap(sale, entra, company).total_seconds() / 3600 == 12
