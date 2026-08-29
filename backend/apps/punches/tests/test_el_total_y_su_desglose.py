"""El total del saldo de descanso contra la suma de sus líneas.

**Lo devuelto se resta una sola vez, del total.** La decisión es correcta y está
razonada en el servidor: un descanso disfrutado no dice de qué fuente salda, y
repartirlo entre ellas exigiría una regla de imputación que nadie ha acordado.
Las fuentes dicen lo que **generan**; el saldo se calcula sobre la suma.

Lo que faltaba era que la pantalla lo dijera. Medido: con ocho horas disfrutadas
de veinticuatro, «Te quedan 16 h» iba encima de tres líneas que suman 24, y quien
las lee cuenta y no le sale.

Y en el extremo era peor. Con todo devuelto: «No queda descanso por recuperar»
encima de «8 h de horas extra, **hasta el 12 dic 2026**». Un plazo de algo ya
saldado no corre, y ahí parecía que sí.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.absences.models import AbsenceStatus, AbsenceType
from apps.absences.services import request_absence
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.punches.rest_debt import rest_debt
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)


@pytest.fixture
def empresa(db):
    compania = Tenant.objects.create(
        name="Cuadra SL", tax_id="B55555556", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(compania.id):
        reglas = WorkingTimeRules.for_company(compania)
        reglas.night_worked_compensation = WorkingTimeRules.NIGHT_REST
        reglas.save(update_fields=["night_worked_compensation"])
        from apps.absences.catalogue import seed_leave_types

        seed_leave_types(compania)
    return compania


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="cuadra@example.com", password=PASSWORD, tenant=empresa, first_name="Quien"
        )
        # Dos noches de ocho horas: dieciséis horas de deuda, de una sola fuente.
        for dia in (date(2026, 8, 10), date(2026, 8, 11)):
            entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=20)
            for momento, kind in (
                (entra, PunchType.IN),
                (entra + timedelta(hours=8), PunchType.OUT),
            ):
                Punch.objects.create(
                    tenant=empresa,
                    employee=persona,
                    timestamp=momento,
                    punch_type=kind,
                    interval=PunchInterval.WORK,
                )
        yield persona


def disfruta(empresa, quien, dia, horas=8):
    """Un día de descanso compensatorio ya aprobado, con su turno."""
    from apps.absences.models import LeaveType

    with tenant_context(empresa.id):
        Shift.objects.update_or_create(
            tenant=empresa,
            employee=quien,
            day=dia,
            defaults={"segments": [{"start": "09:00", "end": f"{9 + horas:02d}:00"}]},
        )
        absence = request_absence(
            employee=quien,
            company=empresa,
            absence_type=AbsenceType.PAID_LEAVE,
            leave_type=LeaveType.objects.get(code="es.compensatory_rest"),
            start_date=dia,
            end_date=dia,
            requested_by=quien,
        )
        absence.status = AbsenceStatus.APPROVED
        absence.save(update_fields=["status"])


def saldo(empresa, quien):
    with tenant_context(empresa.id):
        return rest_debt(employee=quien, company=empresa, day=HOY)


@pytest.mark.django_db
def test_sin_nada_devuelto_el_total_es_la_suma(empresa, quien):
    """El caso que hacía que esto no se viera: sin descansos disfrutados las dos
    cifras coinciden siempre, y la pantalla parecía cuadrar."""
    s = saldo(empresa, quien)

    assert s["settled_hours"] == 0
    assert s["remaining_hours"] == sum(f["owed_hours"] for f in s["sources"])


@pytest.mark.django_db
def test_con_algo_devuelto_el_total_es_menor_que_la_suma(empresa, quien):
    """**El sinsentido.** Y es correcto: las líneas dicen lo generado.

    Lo que la pantalla tiene que hacer es decir la diferencia, no repartirla: la
    API da las dos cifras y `settled_hours` es la que la explica.
    """
    disfruta(empresa, quien, HOY - timedelta(days=2))
    s = saldo(empresa, quien)

    generado = sum(f["owed_hours"] for f in s["sources"])
    assert generado == 16
    assert s["settled_hours"] == 8
    assert s["remaining_hours"] == 8
    # La diferencia entre el total y sus líneas **es** lo devuelto: sin esta
    # igualdad la frase de la pantalla estaría explicando otra cosa.
    assert generado - s["remaining_hours"] == s["settled_hours"]


@pytest.mark.django_db
def test_devuelto_todo_el_total_baja_a_cero_y_las_lineas_siguen(empresa, quien):
    """El extremo: la pantalla decía «no queda nada» encima de las líneas con sus
    plazos. La API sigue dando el desglose ---es cierto, se generó--- y es la
    pantalla la que deja de enseñarlo cuando no hay nada que disfrutar."""
    disfruta(empresa, quien, HOY - timedelta(days=2))
    disfruta(empresa, quien, HOY - timedelta(days=5))
    s = saldo(empresa, quien)

    assert s["remaining_hours"] == 0
    assert s["settled_hours"] == 16
    assert sum(f["owed_hours"] for f in s["sources"]) == 16


@pytest.mark.django_db
def test_devolver_de_mas_no_deja_el_saldo_en_negativo(empresa, quien):
    """Disfrutar más de lo debido pasa ---el convenio puede dar descansos que el
    producto no cuenta--- y el saldo se queda en cero, no en negativo. Un saldo
    negativo se leería como «debes horas de descanso», que es lo contrario."""
    for atras in (2, 5, 8):
        disfruta(empresa, quien, HOY - timedelta(days=atras))
    s = saldo(empresa, quien)

    assert s["settled_hours"] == 24
    assert s["remaining_hours"] == 0, "el saldo no puede bajar de cero"
