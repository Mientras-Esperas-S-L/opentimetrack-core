"""Cancelar la solicitud de otra persona la borraba de la base.

`cancel_absence` hacía `delete()`. Y cancelar **la solicitud de otra persona**
está permitido ---lo hace quien la gestiona--- así que un responsable podía hacer
desaparecer la petición de alguien: medido, la fila no quedaba ni en
`objects_all_tenants`, y el rastro no registraba nada.

Lo que eso deja es que quien pidió sus vacaciones no puede demostrar que las
pidió, ni con qué fechas, ni quién quitó la petición. En las correcciones esto ya
estaba decidido en el otro sentido ---«una petición rechazada también es
historia»--- y aquí faltaba.

Ahora se marca `CANCELLED` y queda su asiento en el rastro con nombre y
apellidos. Lo que **no** cambia: una cancelada no consume saldo ni bloquea los
días, porque el saldo y el solapamiento cuentan solo lo aprobado y lo pendiente.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, LeavePeriod, LeaveType, LeaveUnit
from apps.absences.usage import leave_usage
from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Canceladas", tax_id="B90800001", time_zone="Europe/Madrid", country="ES"
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
    desde = date.today() + timedelta(days=dias)
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
def test_la_responsable_la_cancela_y_la_solicitud_sigue_ahi(
    mundo, django_capture_on_commit_callbacks
):
    cual, desde = pedir(mundo)

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = como(mundo["jefa"]).post(f"/api/absences/{cual}/cancel/")
    assert respuesta.status_code == 204

    with tenant_context(mundo["empresa"].id):
        quedo = Absence.objects.filter(pk=cual).first()

    assert quedo is not None, "la solicitud desaparecía de la base"
    assert quedo.status == AbsenceStatus.CANCELLED
    # Con las fechas que se pidieron, que es lo que se retiró.
    assert quedo.start_date == desde
    # Y con nombre y apellidos de quien la quitó.
    assert quedo.approved_by_id == mundo["jefa"].pk


@pytest.mark.django_db
def test_y_queda_en_el_rastro(mundo, django_capture_on_commit_callbacks):
    cual, desde = pedir(mundo)

    with django_capture_on_commit_callbacks(execute=True):
        como(mundo["jefa"]).post(f"/api/absences/{cual}/cancel/")

    with tenant_context(mundo["empresa"].id):
        anotado = AuditLog.objects.filter(
            tenant=mundo["empresa"], action=AuditAction.ABSENCE_CANCELLED
        ).first()

    assert anotado is not None, "cancelar la solicitud de otro no dejaba rastro"
    assert anotado.actor_id == mundo["jefa"].pk
    assert anotado.target_label == "Obrero Equis"
    # Las fechas, porque son lo que se retiró y sin ellas el asiento no dice qué.
    assert anotado.changes["from"] == str(desde)


@pytest.mark.django_db
def test_una_cancelada_no_consume_saldo(mundo, django_capture_on_commit_callbacks):
    cual, _ = pedir(mundo)
    with django_capture_on_commit_callbacks(execute=True):
        como(mundo["obrero"]).post(f"/api/absences/{cual}/cancel/")

    with tenant_context(mundo["empresa"].id):
        gasto = leave_usage(mundo["obrero"], mundo["vacaciones"], mundo["empresa"])

    assert gasto.used == 0.0, "una solicitud retirada seguía descontando días"


@pytest.mark.django_db
def test_ni_bloquea_esos_dias(mundo, django_capture_on_commit_callbacks):
    """Conservar la fila no puede convertirse en un solapamiento fantasma."""
    cual, desde = pedir(mundo)
    with django_capture_on_commit_callbacks(execute=True):
        como(mundo["obrero"]).post(f"/api/absences/{cual}/cancel/")

    otra_vez = como(mundo["obrero"]).post(
        "/api/absences/",
        {
            "leave_type": str(mundo["vacaciones"].pk),
            "absence_type": "VACATION",
            "start_date": desde.isoformat(),
            "end_date": (desde + timedelta(days=4)).isoformat(),
            "reason": "los mismos dias otra vez",
        },
        format="json",
    )
    assert otra_vez.status_code == 201, otra_vez.content


@pytest.mark.django_db
def test_una_ausencia_ajena_de_otro_departamento_no_se_cancela(mundo):
    with tenant_context(mundo["empresa"].id):
        oficina = Department.objects.create(tenant=mundo["empresa"], name="Oficina")
        ajena = User.objects.create_user(
            email="ajena@example.com",
            password=PASSWORD,
            tenant=mundo["empresa"],
            first_name="Ajena",
            last_name="DeOficina",
            role=Role.MANAGER,
            department=oficina,
        )
        oficina.managers.add(ajena)

    cual, _ = pedir(mundo)
    assert como(ajena).post(f"/api/absences/{cual}/cancel/").status_code == 404

    with tenant_context(mundo["empresa"].id):
        assert Absence.objects.get(pk=cual).status == AbsenceStatus.PENDING


@pytest.mark.django_db
def test_lo_ya_resuelto_no_se_cancela(mundo, django_capture_on_commit_callbacks):
    """Lo que ya valía: aprobada bloquea días y planes de otros."""
    cual, _ = pedir(mundo)
    with django_capture_on_commit_callbacks(execute=True):
        aprobada = como(mundo["jefa"]).post(f"/api/absences/{cual}/approve/")
    assert aprobada.status_code == 200

    respuesta = como(mundo["obrero"]).post(f"/api/absences/{cual}/cancel/")
    assert respuesta.status_code == 409
