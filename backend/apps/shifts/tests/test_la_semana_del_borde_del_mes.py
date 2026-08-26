"""Una semana a caballo de dos meses no cabía en ninguno de los dos.

El tope semanal es una propiedad de la semana, y quien revisa un cuadrante lo
revisa **mes a mes**. El chequeo exigía que la semana cupiera entera dentro del
periodo pedido y la descartaba si no, así que la semana del borde no se revisaba
nunca. Medido con cuarenta y cinco horas planificadas del 29 de junio al 5 de
julio de 2026, por encima de las cuarenta del art. 34.1:

| Quien revisa | Antes | Después |
|---|---|---|
| Junio | nada | avisa |
| Julio | nada | avisa |
| Los dos meses juntos | avisa | avisa |

El razonamiento de descartarla era bueno para el caso que tenía delante ---contar
media semana y avisar es peor que callar, porque quien lo lee va a buscar horas
que no están--- y no consideró la tercera opción: contar la semana **completa**.
Esos turnos están en la base, solo estaban fuera del rango pedido. `review_roster`
ya leía un día a cada lado por el descanso entre jornadas; ahora lee hasta el
lunes y el domingo de las semanas de los bordes.

Los demás chequeos no se enteran: todos filtran por `first`/`last` antes de
reportar, así que leer más días les da contexto y no les hace hablar de días que
nadie pidió --- y eso se prueba abajo.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: Lunes 29 de junio de 2026. Su semana acaba el domingo 5 de julio.
A_CABALLO = date(2026, 6, 29)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con cuadrante", tax_id="B18181818", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="turnos@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Turnos",
            last_name="Equis",
        )


def planifica(company, quien, lunes, horas="17:00"):
    """Cinco días desde ese lunes. De 08:00 a 17:00 son nueve horas: 45 a la semana."""
    with tenant_context(company.id):
        for dia in range(5):
            Shift.objects.create(
                tenant=company,
                employee=quien,
                day=lunes + timedelta(days=dia),
                segments=[{"start": "08:00", "end": horas}],
            )


def excesos(company, quien, primero, ultimo):
    with tenant_context(company.id):
        hallazgos = review_roster(company=company, first=primero, last=ultimo, employee=quien)
    return [h for h in hallazgos if h.code == "weekly_hours_exceeded"]


@pytest.mark.django_db
def test_quien_revisa_junio_ve_la_semana_que_se_va_a_julio(company, quien):
    planifica(company, quien, A_CABALLO)

    avisos = excesos(company, quien, date(2026, 6, 1), date(2026, 6, 30))

    assert len(avisos) == 1, avisos
    assert "45" in avisos[0].message, avisos[0].message


@pytest.mark.django_db
def test_y_quien_revisa_julio_tambien(company, quien):
    """La semana pertenece a los dos periodos, así que sale en los dos."""
    planifica(company, quien, A_CABALLO)

    assert len(excesos(company, quien, date(2026, 7, 1), date(2026, 7, 31))) == 1


@pytest.mark.django_db
def test_se_cuenta_entera_y_no_a_medias(company, quien):
    """Lo que se descartaba por miedo a contar media semana.

    Del 29 de junio al 30 son dos días ---18 horas--- y por debajo del tope. Si se
    contara solo la parte de junio no habría exceso ninguno, así que el aviso de
    45 demuestra que la semana se cuenta completa.
    """
    planifica(company, quien, A_CABALLO)

    avisos = excesos(company, quien, date(2026, 6, 1), date(2026, 6, 30))

    assert "45" in avisos[0].message
    assert "18" not in avisos[0].message


@pytest.mark.django_db
def test_una_semana_ajena_al_periodo_no_se_cuela(company, quien):
    """El control. Ampliar la carga no puede traer semanas que nadie pidió."""
    planifica(company, quien, date(2026, 3, 2))

    assert excesos(company, quien, date(2026, 6, 8), date(2026, 6, 14)) == []


@pytest.mark.django_db
def test_una_semana_dentro_del_tope_sigue_callando(company, quien):
    """El otro control: un aviso que sale siempre no lo lee nadie."""
    planifica(company, quien, date(2026, 6, 8), horas="16:00")

    assert excesos(company, quien, date(2026, 6, 1), date(2026, 6, 30)) == []


@pytest.mark.django_db
def test_la_semana_que_cruza_el_ano_se_cuenta_una_vez(company, quien):
    """El agrupado va por año **ISO**, que es lo que hace que esto funcione.

    El 29 de diciembre de 2025 es la semana 1 de 2026 en ISO, así que la semana
    del cambio de año es una y no dos mitades. Con el año natural saldrían dos
    avisos de 27 y 18 horas, ninguno por encima del tope.
    """
    planifica(company, quien, date(2025, 12, 29))

    avisos = excesos(company, quien, date(2025, 12, 1), date(2026, 1, 31))

    assert len(avisos) == 1, avisos
    assert "45" in avisos[0].message
