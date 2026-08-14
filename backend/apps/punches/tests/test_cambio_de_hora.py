"""Las dos noches del año que no duran veinticuatro horas.

En España los relojes se adelantan el último domingo de marzo ---ese día tiene
23 horas--- y se atrasan el último de octubre, que tiene 25. Para casi todo el
producto da igual. Para un turno de noche no: quien entra a las 22:00 y sale a
las 06:00 trabaja siete horas en marzo y nueve en octubre.

**Los números ya eran correctos** y estas pruebas lo fijan primero, porque es lo
que uno duda al mirar esto. Los fichajes guardan instantes reales, así que la
jornada sale de siete y de nueve horas como debe; y el cuadrante dice ocho, que
también es correcto porque es lo que se planificó en reloj de pared.

Lo que faltaba era la explicación. La noche de octubre, toda la plantilla de
noche aparece en la cola de horas extra con sesenta minutos, y quien tiene que
autorizarlas veía una docena de filas idénticas sin ningún motivo a la vista.
Esa hora es real y la ley va por el tiempo efectivamente trabajado, así que no
hay cifra que corregir: hay que decir de dónde sale. Qué se hace después con
ella es de la empresa.

La trampa que casi se lleva el módulo por delante está anotada en
`apps.common.dst`: restar dos `datetime` con el **mismo** `tzinfo` es aritmética
de reloj de pared, no de tiempo real, así que la primera versión devolvía 24
horas los 365 días del año y parecía correcta.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.common.dst import change_across, clock_change_minutes, local_day_hours
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.punches.services import build_day_status
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: 2026: los relojes se adelantan el 29 de marzo y se atrasan el 25 de octubre.
PRIMAVERA = date(2026, 3, 28)  # el turno empieza la víspera
OTONO = date(2026, 10, 24)
NORMAL = date(2026, 9, 8)


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Noche SL", tax_id="B11111111", time_zone="Europe/Madrid")


def _turno_de_noche(empresa, dia, entra_utc, sale_utc, correo):
    quien = User.objects.create_user(
        email=correo, password=PASSWORD, tenant=empresa, first_name="Noc"
    )
    Shift.objects.create(
        tenant=empresa, employee=quien, day=dia, segments=[{"start": "22:00", "end": "06:00"}]
    )
    for cuando, tipo in ((entra_utc, PunchType.IN), (sale_utc, PunchType.OUT)):
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type=tipo,
            interval=PunchInterval.WORK,
            timestamp=cuando,
        )
    return quien


@pytest.mark.django_db
def test_la_noche_que_los_relojes_se_adelantan_son_siete_horas(empresa):
    with tenant_context(empresa.id):
        quien = _turno_de_noche(
            empresa,
            PRIMAVERA,
            datetime(2026, 3, 28, 21, tzinfo=UTC),  # 22:00 CET
            datetime(2026, 3, 29, 4, tzinfo=UTC),  # 06:00 CEST
            "marzo@example.com",
        )
        estado = build_day_status(quien, empresa, PRIMAVERA)

    assert estado.worked_seconds == 7 * 3600, "el registro no cuenta el tiempo real"


@pytest.mark.django_db
def test_y_la_que_se_atrasan_son_nueve(empresa):
    with tenant_context(empresa.id):
        quien = _turno_de_noche(
            empresa,
            OTONO,
            datetime(2026, 10, 24, 20, tzinfo=UTC),  # 22:00 CEST
            datetime(2026, 10, 25, 5, tzinfo=UTC),  # 06:00 CET
            "octubre@example.com",
        )
        estado = build_day_status(quien, empresa, OTONO)

    assert estado.worked_seconds == 9 * 3600


@pytest.mark.django_db
def test_una_noche_cualquiera_son_ocho(empresa):
    """El contraste. Sin él, las dos de arriba pasarían igual si el cálculo
    estuviera roto de una forma que diera casualmente 7 y 9."""
    with tenant_context(empresa.id):
        quien = _turno_de_noche(
            empresa,
            NORMAL,
            datetime(2026, 9, 8, 20, tzinfo=UTC),
            datetime(2026, 9, 9, 4, tzinfo=UTC),
            "normal@example.com",
        )
        estado = build_day_status(quien, empresa, NORMAL)

    assert estado.worked_seconds == 8 * 3600


@pytest.mark.django_db
def test_la_cola_de_horas_extra_dice_que_hubo_cambio_de_hora(empresa):
    """El hallazgo. La cifra estaba bien y no había forma de saber de dónde salía."""
    from apps.punches.overtime import pending_overtime

    with tenant_context(empresa.id):
        _turno_de_noche(
            empresa,
            OTONO,
            datetime(2026, 10, 24, 20, tzinfo=UTC),
            datetime(2026, 10, 25, 5, tzinfo=UTC),
            "octubre@example.com",
        )
        filas = pending_overtime(company=empresa, first=OTONO, last=OTONO)

    assert filas, "esa noche tiene que salir en la cola: son nueve horas contra ocho"
    assert filas[0]["minutes"] == 60
    assert filas[0]["clock_change_minutes"] == -60, "la cola no explica de dónde sale la hora"


@pytest.mark.django_db
def test_y_una_hora_extra_normal_no_lleva_esa_marca(empresa):
    """El contraste que impide que el aviso salga siempre y deje de leerse."""
    from apps.punches.overtime import pending_overtime

    with tenant_context(empresa.id):
        _turno_de_noche(
            empresa,
            NORMAL,
            datetime(2026, 9, 8, 20, tzinfo=UTC),
            datetime(2026, 9, 9, 5, tzinfo=UTC),  # nueve horas de verdad
            "extra@example.com",
        )
        filas = pending_overtime(company=empresa, first=NORMAL, last=NORMAL)

    assert filas and filas[0]["minutes"] == 60
    assert filas[0]["clock_change_minutes"] == 0


@pytest.mark.django_db
def test_cuanto_dura_cada_dia(empresa):
    """La pieza de abajo, con las dos fechas de 2026 y un día corriente.

    Y con Canarias, que cambia a la vez que la Península pero a otra hora local:
    si el cálculo se hiciera sobre horas locales en vez de sobre instantes, una
    de las dos saldría mal.
    """
    canarias = Tenant.objects.create(
        name="Canarias SL", tax_id="B22222222", time_zone="Atlantic/Canary"
    )

    for donde in (empresa, canarias):
        assert local_day_hours(date(2026, 3, 29), donde) == 23
        assert local_day_hours(date(2026, 10, 25), donde) == 25
        assert local_day_hours(date(2026, 9, 8), donde) == 24
        assert clock_change_minutes(date(2026, 3, 29), donde) == -60
        assert clock_change_minutes(date(2026, 9, 8), donde) == 0


@pytest.mark.django_db
def test_el_cambio_se_mide_en_el_tramo_y_no_en_el_dia(empresa):
    """La distinción que hace que esto sirva de algo.

    El turno empieza el 28 y el reloj cambia la madrugada del 29. Preguntando
    por «el cambio del día del turno» sale cero justo en el caso que importa,
    porque la jornada cuenta en el día en que empieza.
    """
    assert clock_change_minutes(PRIMAVERA, empresa) == 0

    entra = datetime(2026, 3, 28, 21, tzinfo=UTC)
    sale = datetime(2026, 3, 29, 4, tzinfo=UTC)
    with tenant_context(empresa.id):
        assert change_across(entra, sale, empresa) == 60
        # Y con los instantes tal cual salen de la base, en UTC: es el caso real,
        # y el que devolvía cero cuando `change_across` no recibía la zona.
        assert change_across(entra, sale, empresa) == 60
