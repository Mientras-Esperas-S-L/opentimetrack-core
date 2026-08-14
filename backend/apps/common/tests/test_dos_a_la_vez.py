"""Dos personas decidiendo lo mismo a la vez. Solo una puede ganar.

Toda decisión de este producto ---aprobar una ausencia, resolver una corrección,
confirmar una recuperación--- es una transición que solo puede ocurrir una vez. Y
todas se comprobaban igual: mirando el estado del objeto **que la petición ya
tenía cargado en memoria**.

Eso no protege de nada cuando dos responsables pulsan a la vez. Cada petición
cargó su copia antes de que ninguna escribiera, así que las dos ven «pendiente»,
las dos pasan la comprobación y las dos escriben.

Lo que salía en la ausencia, y es peor que un simple duplicado: la aprueba una,
la rechaza la otra, y la fila queda en `REJECTED` **con `approved_by` puesto**.
Un registro que se contradice a sí mismo, más una entrada de aprobación y otra
de rechazo en el rastro para la misma solicitud. En un producto cuyo valor es
sostener su registro delante de una inspección, eso no es un detalle de
concurrencia.

## Sin hilos, y a propósito

La carrera se reproduce cargando dos instancias del mismo registro **antes** de
que ninguna escriba, que es exactamente lo que hacen dos peticiones simultáneas
con `get_object()`. Es determinista, no depende del planificador del sistema y
no necesita `transaction=True` ---que aquí ni siquiera se puede usar: el
desmontaje vacía las tablas con TRUNCATE y el rastro de auditoría lo rechaza---.

Lo que **no** cubre esta forma es el bloqueo real de PostgreSQL entre dos
transacciones de verdad. Lo cubre lo suficiente: si el código vuelve a mirar la
copia en memoria, estas pruebas se ponen rojas.

## Lo que se dejó como estaba

Las horas extra usan `update_or_create` y se pueden volver a decidir por diseño
---la cifra que se autoriza es la que es cierta en el momento de decir que sí---,
así que una segunda decisión no es una carrera perdida sino una decisión nueva, y
que el rastro guarde las dos es correcto.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.models import Absence, AbsenceStatus
from apps.absences.services import approve_absence, cancel_absence, reject_absence
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def gente(db):
    empresa = Tenant.objects.create(
        name="A la vez SL", tax_id="B10000010", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        yield {
            "empresa": empresa,
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Luisa",
                role=Role.ADMIN,
            ),
            "jefe": User.objects.create_user(
                email="jefe@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Andrés",
                role=Role.ADMIN,
            ),
            "curro": User.objects.create_user(
                email="curro@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Curro",
            ),
        }


def _solicitud(gente) -> Absence:
    hoy = date.today()
    return Absence.objects.create(
        tenant=gente["empresa"],
        employee=gente["curro"],
        start_date=hoy + timedelta(days=30),
        end_date=hoy + timedelta(days=31),
        status=AbsenceStatus.PENDING,
    )


def _dos_vistas(solicitud) -> tuple[Absence, Absence]:
    """Lo que ven dos peticiones que cargaron a la vez, antes de que nadie escriba."""
    return Absence.objects.get(pk=solicitud.pk), Absence.objects.get(pk=solicitud.pk)


@pytest.mark.django_db
def test_aprobar_y_rechazar_a_la_vez_deja_una_sola_decision(gente):
    """El caso que lo trajo, con el estado final incoherente que producía."""
    with tenant_context(gente["empresa"].id):
        solicitud = _solicitud(gente)
        vista_a, vista_b = _dos_vistas(solicitud)

        approve_absence(vista_a, resolved_by=gente["jefa"])

        with pytest.raises(BusinessRuleError) as tarde:
            reject_absence(vista_b, resolved_by=gente["jefe"])

        solicitud.refresh_from_db()

    assert tarde.value.code == "already_resolved"
    assert solicitud.status == AbsenceStatus.APPROVED
    # La parte que se contradecía: quedaba REJECTED con approved_by puesto.
    assert solicitud.approved_by_id == gente["jefa"].id


@pytest.mark.django_db
def test_dos_aprobaciones_a_la_vez_tampoco(gente):
    """Aunque las dos digan lo mismo. El estado final coincidiría, pero el
    rastro tendría dos aprobaciones de una solicitud que solo se aprobó una vez,
    y las dos con actores distintos."""
    with tenant_context(gente["empresa"].id):
        solicitud = _solicitud(gente)
        vista_a, vista_b = _dos_vistas(solicitud)

        approve_absence(vista_a, resolved_by=gente["jefa"])
        with pytest.raises(BusinessRuleError):
            approve_absence(vista_b, resolved_by=gente["jefe"])


@pytest.mark.django_db
def test_cancelar_lo_que_acaban_de_aprobar_tampoco(gente):
    """La carrera entre la persona y quien decide.

    Retirar la solicitud en el mismo instante en que se aprueba dejaría unas
    vacaciones aprobadas y borradas a la vez, según cuál escribiera la última.
    """
    with tenant_context(gente["empresa"].id):
        solicitud = _solicitud(gente)
        vista_a, vista_b = _dos_vistas(solicitud)

        approve_absence(vista_a, resolved_by=gente["jefa"])
        with pytest.raises(BusinessRuleError):
            cancel_absence(vista_b, cancelled_by=gente["curro"])

        assert Absence.objects.filter(pk=solicitud.pk).exists(), "la retirada borró una aprobada"


@pytest.mark.django_db
def test_pero_una_sola_decision_sigue_funcionando(gente):
    """El contraste. Sin él, todo lo de arriba pasaría igual si el bloqueo se
    hubiera pasado de listo y ya no dejara resolver nada."""
    with tenant_context(gente["empresa"].id):
        solicitud = _solicitud(gente)
        resuelta = approve_absence(solicitud, resolved_by=gente["jefa"])

    assert resuelta.status == AbsenceStatus.APPROVED
    assert resuelta.approved_by_id == gente["jefa"].id


@pytest.mark.django_db
def test_y_una_recuperacion_tampoco_se_decide_dos_veces(gente):
    """El mismo patrón vivía en tres sitios; este es el tercero."""
    from apps.absences.recovery import confirm_recovery
    from apps.absences.models import RecoveredHoliday

    with tenant_context(gente["empresa"].id):
        hoy = date.today()
        # Unas vacaciones aprobadas y la baja que se las comió: es lo que
        # `detect_recoveries` anota, y la anotación apunta a las dos.
        vacaciones = Absence.objects.create(
            tenant=gente["empresa"],
            employee=gente["curro"],
            start_date=hoy + timedelta(days=40),
            end_date=hoy + timedelta(days=41),
            status=AbsenceStatus.APPROVED,
        )
        baja = Absence.objects.create(
            tenant=gente["empresa"],
            employee=gente["curro"],
            start_date=hoy + timedelta(days=40),
            end_date=hoy + timedelta(days=41),
            status=AbsenceStatus.APPROVED,
        )
        recuperacion = RecoveredHoliday.objects.create(
            tenant=gente["empresa"],
            employee=gente["curro"],
            holiday=vacaciones,
            sick_leave=baja,
            first_day=hoy + timedelta(days=40),
            last_day=hoy + timedelta(days=41),
            days=2,
            regime=RecoveredHoliday.Regime.EIGHTEEN_MONTHS,
            status=RecoveredHoliday.Status.PENDING,
        )
        vista_a = RecoveredHoliday.objects.get(pk=recuperacion.pk)
        vista_b = RecoveredHoliday.objects.get(pk=recuperacion.pk)

        confirm_recovery(
            recovery=vista_a, company=gente["empresa"], decided_by=gente["jefa"], accept=True
        )
        with pytest.raises(BusinessRuleError) as tarde:
            confirm_recovery(
                recovery=vista_b, company=gente["empresa"], decided_by=gente["jefe"], accept=False
            )

    assert tarde.value.code == "already_decided"
