"""Lo que se debe en descanso por horas extra, y hasta cuándo hay para devolverlo.

«Deberán ser compensadas mediante descanso dentro de los cuatro meses siguientes
a su realización» (art. 35.1 ET), en defecto de pacto en convenio.

El producto sabía desde el primer día **cómo** se salda cada hora extra ---con
dinero o con descanso, porque el art. 3.f del real decreto de registro obliga a
decirlo--- y no sabía **si** se había saldado. Es el patrón que más se repetía en
lo que quedaba del inventario: decir «esto se aparta de la regla» y no decir «y
quedan cuatro horas por devolver antes del 9 de septiembre».

Desde el 28/08 por la tarde el saldo es **agregado**: `rest_debt` suma lo que
generan todas las fuentes ---por ahora, las horas extra del art. 35.1 y el
festivo trabajado del art. 37.2--- y resta **una sola vez** lo devuelto. Un
descanso disfrutado salda deuda y no dice de cuál, así que repartirlo entre las
fuentes exigiría una regla de imputación que nadie ha acordado, y restarlo de cada
una lo contaría dos veces. Estas pruebas siguen midiendo la fuente del art. 35.1,
que es la única que tienen delante: sin festivos declarados como compensables con
descanso, la segunda no aporta nada.

Dos decisiones que se ven mejor aquí que en el código:

- **Se deriva, no se guarda.** La deuda está en los fichajes y lo devuelto en las
  ausencias. Un libro de apuntes aparte sería otro sitio donde la misma verdad
  puede quedarse vieja.
- **Un día entero de descanso vale lo que ese día tocaba trabajar**, leído del
  cuadrante. Y si no hay turno previsto, **no se estima**: se dice cuántos días
  quedaron sin convertir, porque una jornada inventada haría que un saldo
  pareciera devuelto sin estarlo.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from apps.absences.models import Absence, AbsenceStatus, LeaveType
from apps.common.models import tenant_context
from apps.punches.models import (
    HoursNature,
    OvertimeSettlement,
    Punch,
    PunchType,
)
from apps.punches.rest_debt import DESCANSO_COMPENSATORIO, rest_debt
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="extra@example.com", password=PASSWORD, tenant=company, first_name="Quien"
        )


@pytest.fixture
def descanso(company):
    with tenant_context(company.id):
        return LeaveType.objects.create(
            tenant=company,
            code=DESCANSO_COMPENSATORIO,
            name="Descanso compensatorio",
            family="PAID_LEAVE",
            basis="Art. 35.1 ET",
            unit="HOURS",
            period="EVENT",
        )


def extra(company, quien, dia, horas, *, settlement=OvertimeSettlement.REST):
    entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=16)
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra,
        punch_type=PunchType.IN,
        hours_nature=HoursNature.OVERTIME,
        overtime_settlement=settlement,
    )
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra + timedelta(hours=horas),
        punch_type=PunchType.OUT,
        hours_nature=HoursNature.OVERTIME,
        overtime_settlement=settlement,
    )


def devuelve(company, quien, tipo, dia, *, desde=None, hasta=None):
    """Un descanso compensatorio: por horas si se dan, o el día entero."""
    return Absence.objects.create(
        tenant=company,
        employee=quien,
        leave_type=tipo,
        start_date=dia,
        end_date=dia,
        start_time=time.fromisoformat(desde) if desde else None,
        end_time=time.fromisoformat(hasta) if hasta else None,
        status=AbsenceStatus.APPROVED,
    )


@pytest.mark.django_db
def test_sin_horas_extra_no_hay_saldo(company, quien):
    """**El contraste de todo lo demás.**

    Un saldo a cero de algo que no ha pasado nunca ocupa sitio en la pantalla y
    no dice nada. Se contesta `None` y no se enseña.
    """
    with tenant_context(company.id):
        assert rest_debt(employee=quien, company=company, day=HOY) is None


@pytest.mark.django_db
def test_las_horas_extra_pagadas_no_deben_descanso(company, quien):
    """Las que se pagan no se devuelven, y el registro sabe cuál es cuál.

    Sin esta distinción, cualquier hora extra generaría una deuda de descanso
    que nadie tiene, y el aviso saltaría en empresas que pagan todas sus extras.
    """
    with tenant_context(company.id):
        extra(company, quien, HOY - timedelta(days=10), 4, settlement=OvertimeSettlement.PAID)
        assert rest_debt(employee=quien, company=company, day=HOY) is None


@pytest.mark.django_db
def test_lo_que_se_debe_y_lo_que_queda(company, quien, descanso):
    """Cuatro horas hechas, hora y media devuelta, quedan dos y media."""
    with tenant_context(company.id):
        extra(company, quien, HOY - timedelta(days=10), 4)
        devuelve(company, quien, descanso, HOY - timedelta(days=2), desde="09:00", hasta="10:30")

        saldo = rest_debt(employee=quien, company=company, day=HOY)
        assert saldo["owed_hours"] == 4
        assert saldo["settled_hours"] == 1.5
        assert saldo["remaining_hours"] == 2.5
        assert saldo["sources"][0]["citation"] == "Art. 35.1 ET"


@pytest.mark.django_db
def test_dice_hasta_cuando_hay_para_devolverlo(company, quien):
    """La fecha es la mitad del asunto: «quedan 4 h **antes del 9 de septiembre**».

    Sale de lo **más antiguo** que sigue sin devolverse, que es lo que vence
    primero. Tomar la más reciente daría un plazo más largo del real y llegaría
    tarde justo a lo que más corría.
    """
    with tenant_context(company.id):
        extra(company, quien, date(2026, 5, 12), 3)
        extra(company, quien, date(2026, 8, 20), 2)

        saldo = rest_debt(employee=quien, company=company, day=HOY)
        # 12 de mayo más 120 días.
        assert saldo["due_on"] == "2026-09-09"


@pytest.mark.django_db
def test_lo_que_se_pasó_de_plazo_se_cuenta_aparte(company, quien):
    """Fuera de plazo ya no es «pendiente»: es un incumplimiento consumado.

    Sumarlo a lo que queda por devolver escondería que el plazo pasó, que es
    justo lo que hay que decir.
    """
    with tenant_context(company.id):
        extra(company, quien, HOY - timedelta(days=200), 5)
        extra(company, quien, HOY - timedelta(days=10), 3)

        saldo = rest_debt(employee=quien, company=company, day=HOY)
        assert saldo["overdue_hours"] == 5
        assert saldo["owed_hours"] == 3


@pytest.mark.django_db
def test_un_dia_entero_vale_lo_que_ese_dia_tocaba(company, quien, descanso):
    """Ocho horas extra se devuelven con un día libre, y el día vale su turno.

    `Absence.hours` contesta cero para los días completos ---y hace bien: cuánto
    dura un día depende del turno, del contrato y de la persona---, así que sin
    leer el cuadrante un día entero de descanso no devolvería nada.
    """
    with tenant_context(company.id):
        libre = HOY - timedelta(days=3)
        Shift.objects.create(
            tenant=company,
            employee=quien,
            day=libre,
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        extra(company, quien, HOY - timedelta(days=10), 8)
        devuelve(company, quien, descanso, libre)

        saldo = rest_debt(employee=quien, company=company, day=HOY)
        assert saldo["settled_hours"] == 8
        assert saldo["remaining_hours"] == 0
        assert saldo["unconverted_days"] == 0


@pytest.mark.django_db
def test_un_dia_sin_turno_no_se_estima(company, quien, descanso):
    """**La decisión que evita un saldo falsamente saldado.**

    Sin turno previsto no hay de dónde sacar cuánto dura ese día. Ponerle una
    jornada tipo daría por devueltas ocho horas que quizá fueran cuatro, y el
    saldo diría cero teniendo deuda. Se cuentan los días y se dicen.
    """
    with tenant_context(company.id):
        extra(company, quien, HOY - timedelta(days=10), 8)
        devuelve(company, quien, descanso, HOY - timedelta(days=3))

        saldo = rest_debt(employee=quien, company=company, day=HOY)
        assert saldo["settled_hours"] == 0
        assert saldo["remaining_hours"] == 8
        assert saldo["unconverted_days"] == 1


@pytest.mark.django_db
def test_una_solicitud_sin_aprobar_no_devuelve_nada(company, quien, descanso):
    """Pedir un descanso no es haberlo disfrutado.

    Contarlo como devuelto haría desaparecer la deuda con solo pedir el día, y
    quien mirara el saldo vería cero mientras el plazo sigue corriendo.
    """
    with tenant_context(company.id):
        extra(company, quien, HOY - timedelta(days=10), 4)
        pendiente = devuelve(
            company, quien, descanso, HOY - timedelta(days=2), desde="09:00", hasta="13:00"
        )
        pendiente.status = AbsenceStatus.PENDING
        pendiente.save(update_fields=["status"])

        saldo = rest_debt(employee=quien, company=company, day=HOY)
        assert saldo["settled_hours"] == 0
        assert saldo["remaining_hours"] == 4


@pytest.mark.django_db
def test_un_cero_apaga_la_cuenta(company, quien):
    """Para el convenio que remita a un cómputo distinto.

    Forzar los cuatro meses del artículo sobre un convenio que dice otra cosa
    sería decir algo falso con aire de dato.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.overtime_rest_days = 0
        reglas.save(update_fields=["overtime_rest_days"])

        extra(company, quien, HOY - timedelta(days=10), 4)
        assert rest_debt(employee=quien, company=company, day=HOY) is None


@pytest.mark.django_db
def test_un_plazo_de_convenio_mas_largo_cambia_la_cuenta(company, quien):
    """El contraste del anterior: el plazo del convenio manda de verdad.

    Con doscientos días, lo hecho hace ciento cincuenta sigue **en plazo**; con
    los ciento veinte del artículo estaría vencido. Si el campo no se leyera,
    los dos casos darían lo mismo.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.overtime_rest_days = 200
        reglas.save(update_fields=["overtime_rest_days"])

        extra(company, quien, HOY - timedelta(days=150), 6)
        saldo = rest_debt(employee=quien, company=company, day=HOY)
        assert saldo["overdue_hours"] == 0
        assert saldo["owed_hours"] == 6
        assert saldo["sources"][0]["days"] == 200
