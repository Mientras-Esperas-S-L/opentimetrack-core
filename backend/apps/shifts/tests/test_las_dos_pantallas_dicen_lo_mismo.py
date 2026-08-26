"""A la una de la madrugada, las dos mitades de la pantalla de fichar concuerdan.

`/punches/today/` y `/shifts/today/` alimentan la misma pantalla: la primera dice
qué se ha fichado, la segunda lo esperado contra lo trabajado. Una miraba la
**jornada** ---que es la unidad con la que mide el Estatuto, y el porqué está en
`apps.punches.workday`--- y la otra el **día natural**.

Para quien entra a las 22:00 y sale a las 06:00 no son lo mismo ninguna noche, y
medido daban esto a la una de la madrugada:

    /punches/today/   state=WORKING       worked=6398s
    /shifts/today/    state=NOT_STARTED   worked_minutes=0

La misma persona, el mismo instante. Es el fallo que `punches/services.py` dice
haber arreglado ---«a las tres de la mañana un turno de noche veía "sin empezar"
en su propia pantalla mientras estaba trabajando»--- sobreviviendo en el endpoint
hermano.

El tiempo va congelado a propósito: una prueba que solo dijera la verdad entre
medianoche y las dos de la madrugada es lo que dejó pasar esto.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def turno_de_noche(db):
    """Alguien que entró anoche a las 22:00 y sigue dentro."""
    company = Tenant.objects.create(
        name="Vigilancia Nocturna SL", tax_id="B66666666", time_zone="Europe/Madrid"
    )
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="sereno@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Sara",
            last_name="Sereno",
        )
        # 22:00 del 13 en Madrid == 20:00 UTC del 13.
        with freeze_time("2026-08-13 20:00:00"):
            register_punch(employee=quien, company=company)
        yield company, quien


def _cliente(quien):
    cliente = APIClient()
    cliente.force_authenticate(user=quien)
    return cliente


@pytest.mark.django_db
def test_a_la_una_las_dos_hablan_de_la_misma_jornada(turno_de_noche):
    company, quien = turno_de_noche

    # 01:00 del 14 en Madrid == 23:00 UTC del 13. Tres horas dentro.
    with freeze_time("2026-08-13 23:00:00"), tenant_context(company.id):
        cliente = _cliente(quien)
        fichajes = cliente.get("/api/punches/today/").json()
        turno = cliente.get("/api/shifts/today/").json()

    assert fichajes["state"] == "WORKING"
    assert turno["state"] == fichajes["state"], (
        "una mitad de la pantalla dice que está trabajando y la otra que no ha "
        f"empezado: {fichajes['state']} contra {turno['state']}"
    )
    assert turno["day"] == date(2026, 8, 13).isoformat(), (
        "la jornada empezó el 13 a las 22:00; a la una de la madrugada del 14 "
        "sigue siendo la del 13, no la de hoy"
    )
    assert turno["worked_minutes"] == fichajes["worked_seconds"] // 60, (
        "las dos cuentan lo mismo y tienen que decir lo mismo"
    )
    assert turno["worked_minutes"] == 180


@pytest.mark.django_db
def test_de_dia_siguen_concordando(turno_de_noche):
    """Que el arreglo no rompa el caso corriente, que es el de casi todo el mundo."""
    company, quien = turno_de_noche

    # 10:00 del 20 en Madrid: la jornada de la noche del 13 quedó abandonada
    # hace días, así que hoy es hoy y no hay nada abierto que arrastre.
    with freeze_time("2026-08-20 08:00:00"), tenant_context(company.id):
        turno = _cliente(quien).get("/api/shifts/today/").json()

    assert turno["day"] == date(2026, 8, 20).isoformat()
