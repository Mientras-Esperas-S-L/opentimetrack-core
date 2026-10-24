"""El motivo de un rechazo llega a quien pidió la ausencia.

«Por decidir» pedía el motivo al rechazar y decía «lo leerá la persona que lo
solicitó». No se guardaba en ninguna parte: la llamada no lo enviaba y el servidor
no tenía dónde ponerlo. El «no» llegaba sin explicación, y desde el calendario ni
siquiera se pedía.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.absences.models import LeavePeriod, LeaveType, LeaveUnit
from apps.common.clock import local_today
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Rechazadas", tax_id="B90800002", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        obras = Department.objects.create(tenant=empresa, name="Obras")
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.MANAGER,
            department=obras,
        )
        obras.managers.add(jefa)
        obrero = User.objects.create_user(
            email="obrero@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Obrero",
            last_name="Equis",
            department=obras,
        )
        vacaciones = LeaveType.objects.create(
            tenant=empresa,
            name="Vacaciones",
            code="VAC",
            unit=LeaveUnit.DAYS_CALENDAR,
            period=LeavePeriod.YEAR,
            amount=30,
        )
        yield {
            "empresa": empresa,
            "jefa": jefa,
            "obrero": obrero,
            "vacaciones": vacaciones,
        }


def como(quien):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente


def pedir(mundo, dias=60):
    desde = local_today(mundo["empresa"]) + timedelta(days=dias)
    respuesta = como(mundo["obrero"]).post(
        "/api/absences/",
        {
            "leave_type": str(mundo["vacaciones"].pk),
            "absence_type": "VACATION",
            "start_date": desde.isoformat(),
            "end_date": (desde + timedelta(days=4)).isoformat(),
            "reason": "las de verano",
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.content
    return respuesta.json()["id"], desde


@pytest.mark.django_db
def test_el_motivo_se_guarda_y_lo_ve_quien_la_pidio(mundo):
    cual, _desde = pedir(mundo)

    respuesta = como(mundo["jefa"]).post(
        f"/api/absences/{cual}/reject/", {"note": "Esa semana cerramos el parque"}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["resolution_note"] == "Esa semana cerramos el parque"
    suya = como(mundo["obrero"]).get(f"/api/absences/{cual}/").json()
    assert suya["status"] == "REJECTED"
    assert suya["resolution_note"] == "Esa semana cerramos el parque"


@pytest.mark.django_db
def test_sin_motivo_sigue_pudiendose_rechazar(mundo):
    cual, _desde = pedir(mundo)

    respuesta = como(mundo["jefa"]).post(f"/api/absences/{cual}/reject/")

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["resolution_note"] == ""
