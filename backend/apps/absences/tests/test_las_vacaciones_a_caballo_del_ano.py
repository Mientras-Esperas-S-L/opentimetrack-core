"""Unas vacaciones del 28 de diciembre al 5 de enero salen en los dos años.

El filtro por año de la lista iba por `start_date__year`, así que unas vacaciones
que empiezan el 28 de diciembre no aparecían al pedir el año siguiente ---donde
caen cinco de sus nueve días y donde está quien las busca, porque las está
disfrutando.

El saldo sí las repartía bien desde el principio: 4 días contra un año y 5 contra
el otro. Era solo la lista, y por eso no se notaba en ninguna cifra.

Mismo patrón que la semana del borde del mes de la vuelta 81: un periodo se filtra
por solape, nunca por uno de sus dos extremos.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.absences.models import LeavePeriod, LeaveType, LeaveUnit
from apps.absences.usage import leave_usage
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Nochevieja", tax_id="B85858585", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Cruza",
        )
        vacaciones = LeaveType.objects.create(
            tenant=empresa,
            name="Vacaciones",
            code="VAC",
            unit=LeaveUnit.DAYS_CALENDAR,
            period=LeavePeriod.YEAR,
            amount=30,
        )
        yield {"empresa": empresa, "quien": quien, "vacaciones": vacaciones}


def pedir(quien, tipo, desde, hasta):
    cliente = APIClient()
    cliente.force_authenticate(user=quien)
    respuesta = cliente.post(
        "/api/absences/",
        {
            "leave_type": str(tipo.pk),
            "absence_type": "VACATION",
            "start_date": desde,
            "end_date": hasta,
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.content
    return cliente


@pytest.mark.django_db
def test_salen_al_pedir_cualquiera_de_los_dos_anos(mundo):
    cliente = pedir(mundo["quien"], mundo["vacaciones"], "2026-12-28", "2027-01-05")

    for año in (2026, 2027):
        filas = cliente.get(f"/api/absences/?year={año}").json()["results"]
        assert len(filas) == 1, f"al pedir {año} no aparecían unas vacaciones que caen en {año}"


@pytest.mark.django_db
def test_pero_no_en_un_ano_que_no_tocan(mundo):
    """El solape no puede convertirse en «sale siempre»."""
    cliente = pedir(mundo["quien"], mundo["vacaciones"], "2026-12-28", "2027-01-05")

    assert cliente.get("/api/absences/?year=2025").json()["results"] == []
    assert cliente.get("/api/absences/?year=2028").json()["results"] == []


@pytest.mark.django_db
def test_y_el_saldo_sigue_repartiendo_los_dias_entre_los_dos(mundo):
    """Lo que ya estaba bien: cada año se lleva los días que le tocan, no los nueve."""
    pedir(mundo["quien"], mundo["vacaciones"], "2026-12-28", "2027-01-05")

    with tenant_context(mundo["empresa"].id):
        en_2026 = leave_usage(
            mundo["quien"], mundo["vacaciones"], mundo["empresa"], on=date(2026, 12, 31)
        )
        en_2027 = leave_usage(
            mundo["quien"], mundo["vacaciones"], mundo["empresa"], on=date(2027, 1, 15)
        )

    assert (en_2026.used, en_2027.used) == (4.0, 5.0)
