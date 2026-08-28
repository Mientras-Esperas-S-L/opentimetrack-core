"""El descanso que se debe por haber trabajado un festivo (art. 37.2).

El artículo hace los catorce días **retribuidos y no recuperables**, y trabajar
uno es perfectamente lícito: lo que genera es una compensación. Lo que el
artículo **no** dice es de qué tipo ni cuánta, y ahí manda el convenio.

De ahí las dos preguntas que contesta la empresa ---si compensa con descanso o
con dinero, y cuántas horas de descanso por hora trabajada--- y la decisión que
más importa de esta pieza: **sin declararlo, no se lleva ningún saldo**. No
habría de dónde sacar la cifra, y una inventada se leería como la del convenio.

Y la segunda decisión: **se cuenta lo fichado, no lo planificado**. El cuadrante
ya avisaba desde que se asigna el turno ---y hace bien, es cuando alguien puede
cambiarlo--- pero la compensación se debe por haber trabajado. Quien tenía turno
un festivo y estuvo de baja no ha ganado ningún descanso.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.punches.rest_debt import rest_debt
from apps.tenants.models import HolidayScope, PublicHoliday, Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)
#: Un festivo cualquiera dentro de la ventana que se mira.
EL_FESTIVO = date(2026, 8, 15)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        PublicHoliday.objects.create(
            tenant=empresa, day=EL_FESTIVO, name="La Asunción", scope=HolidayScope.NATIONAL
        )
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.holiday_worked_compensation = WorkingTimeRules.HOLIDAY_REST
        reglas.save(update_fields=["holiday_worked_compensation"])
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="festivo@example.com", password=PASSWORD, tenant=company, first_name="Quien"
        )


def trabaja(company, quien, dia, horas):
    entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=6)
    Punch.objects.create(tenant=company, employee=quien, timestamp=entra, punch_type=PunchType.IN)
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra + timedelta(hours=horas),
        punch_type=PunchType.OUT,
    )


def la_fuente(company, quien):
    with tenant_context(company.id):
        saldo = rest_debt(employee=quien, company=company, day=HOY)
    if not saldo:
        return None
    return next((f for f in saldo["sources"] if f["source"] == "holiday"), None)


@pytest.mark.django_db
def test_trabajar_un_festivo_genera_descanso(company, quien):
    """Ocho horas el 15 de agosto son ocho horas de descanso que devolver."""
    with tenant_context(company.id):
        trabaja(company, quien, EL_FESTIVO, 8)

    fuente = la_fuente(company, quien)
    assert fuente["owed_hours"] == 8
    assert fuente["citation"] == "Art. 37.2 ET"


@pytest.mark.django_db
def test_sin_declarar_como_se_compensa_no_se_lleva_saldo(company, quien):
    """**La decisión que más importa de esta pieza.**

    El art. 37.2 no dice cómo se compensa un festivo trabajado: lo fija el
    convenio. Sin que la empresa lo declare no hay de dónde sacar la cifra, y una
    inventada se leería como la del convenio.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.holiday_worked_compensation = ""
        reglas.save(update_fields=["holiday_worked_compensation"])
        trabaja(company, quien, EL_FESTIVO, 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_si_se_compensa_con_dinero_tampoco(company, quien):
    """El contraste del anterior, y no dicen lo mismo.

    Sin esto, «sin declarar» y «declarado como dinero» se verían igual: las dos
    harían pasar la prueba de arriba. Compensar en metálico es una de las dos
    salidas del artículo, y ahí no queda descanso que devolver ---lo que queda es
    un concepto de nómina, que está fuera de este producto---.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.holiday_worked_compensation = WorkingTimeRules.HOLIDAY_PAID
        reglas.save(update_fields=["holiday_worked_compensation"])
        trabaja(company, quien, EL_FESTIVO, 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_el_multiplicador_del_convenio_manda(company, quien):
    """Hay convenios que devuelven hora y media por hora trabajada en festivo.

    Forzar el uno por uno sobre un convenio que dice otra cosa sería quitarle a
    alguien la mitad de lo que le corresponde.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.holiday_rest_multiplier = 1.75
        reglas.save(update_fields=["holiday_rest_multiplier"])
        trabaja(company, quien, EL_FESTIVO, 8)

    fuente = la_fuente(company, quien)
    assert fuente["owed_hours"] == 14
    assert fuente["multiplier"] == 1.75


@pytest.mark.django_db
def test_un_dia_normal_no_debe_nada(company, quien):
    """El contraste de que lo que cuenta es el festivo y no el trabajo.

    Sin esto, un saldo que sumara **todas** las horas trabajadas pasaría igual la
    primera prueba de este fichero.
    """
    with tenant_context(company.id):
        trabaja(company, quien, EL_FESTIVO - timedelta(days=1), 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_tener_turno_y_no_trabajarlo_no_debe_nada(company, quien):
    """**Lo fichado, no lo planificado.**

    El cuadrante avisa desde que se asigna el turno, y hace bien: es cuando
    alguien puede cambiarlo. Pero la compensación se debe por haber trabajado, y
    quien tenía turno un festivo y estuvo de baja no ha ganado ningún descanso.
    """
    from apps.shifts.models import Shift

    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=quien,
            day=EL_FESTIVO,
            segments=[{"start": "08:00", "end": "16:00"}],
        )

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_el_festivo_no_lleva_plazo(company, quien):
    """El art. 37.2 no da ninguno, y el del art. 35.1 no le pega.

    Contarle los cuatro meses de las horas extra convertiría en «fuera de plazo»
    algo que no lo está, y encima citando un artículo que no habla de esto.
    """
    with tenant_context(company.id):
        trabaja(company, quien, EL_FESTIVO, 8)

    fuente = la_fuente(company, quien)
    assert fuente["due_on"] is None
    assert fuente["overdue_hours"] == 0


@pytest.mark.django_db
def test_lo_devuelto_no_se_resta_dos_veces(company, quien):
    """**La prueba que trae esta segunda fuente.**

    Con una sola fuente, restar lo devuelto dentro de ella era correcto. Con dos,
    hacerlo en cada una descontaría el mismo descanso dos veces y el saldo saldría
    a cero teniendo deuda.

    Un descanso disfrutado salda deuda y **no dice de cuál**: repartirlo exigiría
    una regla de imputación que nadie ha acordado. Así que las fuentes dicen lo
    que generan y la resta se hace una vez, sobre el total.

    Ocho horas de festivo más cuatro de horas extra son doce; devueltas cuatro,
    quedan ocho. Restando en cada fuente saldrían cuatro.
    """
    from apps.absences.models import Absence, AbsenceStatus, LeaveType
    from apps.punches.models import HoursNature, OvertimeSettlement
    from apps.punches.rest_debt import DESCANSO_COMPENSATORIO

    with tenant_context(company.id):
        trabaja(company, quien, EL_FESTIVO, 8)

        # Cuatro horas extra a compensar con descanso, en un día normal.
        otro = EL_FESTIVO + timedelta(days=2)
        entra = datetime.combine(otro, datetime.min.time(), tzinfo=UTC).replace(hour=16)
        for momento, tipo in ((entra, PunchType.IN), (entra + timedelta(hours=4), PunchType.OUT)):
            Punch.objects.create(
                tenant=company,
                employee=quien,
                timestamp=momento,
                punch_type=tipo,
                hours_nature=HoursNature.OVERTIME,
                overtime_settlement=OvertimeSettlement.REST,
            )

        tipo_descanso = LeaveType.objects.create(
            tenant=company,
            code=DESCANSO_COMPENSATORIO,
            name="Descanso compensatorio",
            family="PAID_LEAVE",
            basis="Art. 35.1 ET",
            unit="HOURS",
            period="EVENT",
        )
        Absence.objects.create(
            tenant=company,
            employee=quien,
            leave_type=tipo_descanso,
            start_date=EL_FESTIVO + timedelta(days=5),
            end_date=EL_FESTIVO + timedelta(days=5),
            start_time="09:00",
            end_time="13:00",
            status=AbsenceStatus.APPROVED,
        )

        saldo = rest_debt(employee=quien, company=company, day=HOY)

    assert saldo["owed_hours"] == 12, "las dos fuentes suman lo que generan"
    assert saldo["settled_hours"] == 4, "y lo devuelto se cuenta una sola vez"
    assert saldo["remaining_hours"] == 8
    assert {f["source"] for f in saldo["sources"]} == {"overtime", "holiday"}
