"""La asesoría laboral: lee el registro de toda la empresa y no decide sobre él.

Antes solo cabía como administración, que edita fichajes y resuelve ausencias.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        ana = User.objects.create_user(email="ana@example.com", password=PASSWORD, tenant=empresa)
        jefa = User.objects.create_user(
            email="jefa@example.com", password=PASSWORD, tenant=empresa, role=Role.MANAGER
        )
        asesoria = User.objects.create_user(
            email="gestoria@example.com", password=PASSWORD, tenant=empresa, role=Role.ADVISOR
        )
        # Con departamentos en uso: a la asesoría no la acotan.
        otro = Department.objects.create(tenant=empresa, name="Almacén")
        otro.managers.add(jefa)
        ausencia = request_absence(
            employee=ana,
            company=empresa,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
        )
    return {"empresa": empresa, "ana": ana, "asesoria": asesoria, "ausencia": ausencia}


def como(persona):
    cliente = APIClient()
    cliente.force_authenticate(user=persona)
    return cliente


@pytest.mark.django_db
def test_lee_la_plantilla_y_las_ausencias_de_toda_la_empresa(mundo):
    cliente = como(mundo["asesoria"])
    assert cliente.get("/api/employees/").status_code == 200
    assert cliente.get(f"/api/employees/{mundo['ana'].id}/").status_code == 200
    assert cliente.get("/api/absences/").json()["count"] == 1
    assert cliente.get(f"/api/absences/{mundo['ausencia'].id}/").status_code == 200
    saldo = cliente.get("/api/absences/balance/", {"employee": str(mundo["ana"].id)})
    assert saldo.status_code == 200


@pytest.mark.django_db
def test_no_aprueba_ni_cambia_a_nadie(mundo):
    cliente = como(mundo["asesoria"])
    assert cliente.post(f"/api/absences/{mundo['ausencia'].id}/approve/").status_code == 403
    assert cliente.get("/api/absences/pending/").json() == []
    cambio = cliente.patch(f"/api/employees/{mundo['ana'].id}/", {"first_name": "X"}, format="json")
    assert cambio.status_code == 403
    pedir = cliente.post(
        "/api/absences/",
        {
            "absence_type": "VACATION",
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "employee": str(mundo["ana"].id),
        },
        format="json",
    )
    assert pedir.status_code == 409


@pytest.mark.django_db
def test_no_ficha(mundo):
    with tenant_context(mundo["empresa"].id), pytest.raises(BusinessRuleError) as error:
        register_punch(employee=mundo["asesoria"], company=mundo["empresa"])
    assert error.value.code == "advisor_does_not_clock"


@pytest.mark.django_db
def test_no_cuenta_en_la_plantilla(mundo):
    assert mundo["asesoria"] not in User.objects.workforce()
    assert mundo["ana"] in User.objects.workforce()
