"""La baja que se come unas vacaciones (art. 38.3 ET).

Lo que se prueba aquí es que los dos regímenes no se confundan, que es el error
fácil: el párrafo largo y detallado es justo el que **no** caduca.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.absences.models import (
    Absence,
    AbsenceStatus,
    AbsenceType,
    LeaveType,
    RecoveredHoliday,
)
from apps.absences.recovery import confirm_recovery, detect_recoveries, pending_recoveries
from apps.absences.services import approve_absence, vacation_balance
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd",
        tax_id="B11111111",
        time_zone="Europe/Madrid",
        annual_leave_days=22,
        leave_days_are_working_days=False,  # naturales: la cuenta es directa
    )


@pytest.fixture
def people(company):
    with tenant_context(company.id):
        yield {
            "worker": User.objects.create_user(
                email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
            ),
            "boss": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.ADMIN,
            ),
        }


def kind(company, code, regime):
    return LeaveType.objects.create(
        tenant=company,
        code=code,
        name=code,
        family="SICK_LEAVE" if "sick" in code else "SUSPENSION",
        vacation_recovery=regime,
        initiated_by="PERSON",
    )


def holiday(company, worker, first, last):
    return Absence.objects.create(
        tenant=company,
        employee=worker,
        absence_type=AbsenceType.VACATION,
        status=AbsenceStatus.APPROVED,
        start_date=first,
        end_date=last,
    )


def sick(company, worker, leave_type, first, last):
    return Absence.objects.create(
        tenant=company,
        employee=worker,
        absence_type=AbsenceType.SICK_LEAVE,
        leave_type=leave_type,
        status=AbsenceStatus.PENDING,
        start_date=first,
        end_date=last,
    )


# ------------------------------------------------------ los dos regímenes


@pytest.mark.django_db
def test_a_common_illness_recovers_within_eighteen_months(company, people):
    """Párrafo 3.º: enfermedad común, dieciocho meses desde el fin del año."""
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 15))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 10), date(2026, 8, 20))
        approve_absence(baja, resolved_by=people["boss"])

        recovery = RecoveredHoliday.objects.get()

    # Del 10 al 15: seis días, solo lo que coincide.
    assert recovery.days == 6
    assert recovery.regime == "EIGHTEEN_MONTHS"
    # Dieciocho meses desde el 31/12/2026.
    assert recovery.expires_on == date(2028, 6, 30)
    assert recovery.status == "PENDING"


@pytest.mark.django_db
def test_a_birth_suspension_recovers_with_no_deadline(company, people):
    """Párrafo 2.º: art. 48.4, «aunque haya terminado el año natural»."""
    with tenant_context(company.id):
        tipo = kind(company, "es.birth", "UNLIMITED")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 15))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 5), date(2026, 12, 20))
        approve_absence(baja, resolved_by=people["boss"])

        recovery = RecoveredHoliday.objects.get()

    assert recovery.regime == "UNLIMITED"
    # No es «todavía no se sabe»: es que no hay fecha.
    assert recovery.expires_on is None


@pytest.mark.django_db
def test_a_leave_that_recovers_nothing_still_clashes(company, people):
    """Una excedencia voluntaria no da derecho a recuperar vacaciones, así que
    pisarlas sigue siendo un choque y no se puede aprobar.

    La excepción del art. 38.3 es para las bajas que la ley nombra, no una
    barra libre para solapar ausencias.
    """
    from apps.common.exceptions import BusinessRuleError

    with tenant_context(company.id):
        tipo = kind(company, "es.unpaid_leave", "")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 15))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 10), date(2026, 8, 20))

        with pytest.raises(BusinessRuleError) as caught:
            approve_absence(baja, resolved_by=people["boss"])

    assert caught.value.code == "overlapping_absence"
    with tenant_context(company.id):
        assert RecoveredHoliday.objects.count() == 0


# ---------------------------------------------------------- el solapamiento


@pytest.mark.django_db
def test_only_the_overlapping_days_come_back(company, people):
    """«Total o parcialmente», dice la ley. Quince días de vacaciones y una baja
    que empieza el décimo no devuelven quince días."""
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 7, 1), date(2026, 7, 15))
        baja = sick(company, people["worker"], tipo, date(2026, 7, 10), date(2026, 7, 31))
        approve_absence(baja, resolved_by=people["boss"])

        assert RecoveredHoliday.objects.get().days == 6  # del 10 al 15


@pytest.mark.django_db
def test_a_leave_that_started_before_the_holiday_counts_too(company, people):
    """Da igual cuándo empezara: el precepto solo dice «coincida».

    Lo contrario lo sostuvo la STS de 2005 y quedó rectificado por el TJUE en
    ANGED (C-78/11) y la STS del Pleno de 3 de octubre de 2012.
    """
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 7, 10), date(2026, 7, 20))
        baja = sick(company, people["worker"], tipo, date(2026, 7, 1), date(2026, 7, 12))
        approve_absence(baja, resolved_by=people["boss"])

        assert RecoveredHoliday.objects.get().days == 3  # del 10 al 12


@pytest.mark.django_db
def test_a_leave_that_does_not_touch_the_holiday_records_nothing(company, people):
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 7, 1), date(2026, 7, 10))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 1), date(2026, 8, 5))
        approve_absence(baja, resolved_by=people["boss"])

        assert RecoveredHoliday.objects.count() == 0


@pytest.mark.django_db
def test_detecting_twice_does_not_duplicate(company, people):
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 15))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 10), date(2026, 8, 20))
        approve_absence(baja, resolved_by=people["boss"])
        detect_recoveries(absence=baja, company=company)

        assert RecoveredHoliday.objects.count() == 1


# --------------------------------------------------- del saldo y la decisión


@pytest.mark.django_db
def test_the_days_do_not_come_back_until_somebody_confirms(company, people):
    """No se devuelven solos. El derecho se ve desde el minuto uno, pero quien
    lo aplica es una persona."""
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 10))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 5), date(2026, 8, 20))
        approve_absence(baja, resolved_by=people["boss"])

        antes = vacation_balance(people["worker"], company, date(2026, 9, 1))
        assert antes.taken == 10  # los diez días siguen contando como gastados

        recovery = RecoveredHoliday.objects.get()
        confirm_recovery(recovery=recovery, company=company, decided_by=people["boss"], accept=True)
        despues = vacation_balance(people["worker"], company, date(2026, 9, 1))

    # Del 5 al 10 son seis días: vuelven al saldo.
    assert despues.taken == 4
    assert despues.remaining == antes.remaining + 6


@pytest.mark.django_db
def test_dismissing_it_leaves_the_balance_alone(company, people):
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 10))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 5), date(2026, 8, 20))
        approve_absence(baja, resolved_by=people["boss"])

        confirm_recovery(
            recovery=RecoveredHoliday.objects.get(),
            company=company,
            decided_by=people["boss"],
            accept=False,
            note="Esas vacaciones se anularon aparte.",
        )
        saldo = vacation_balance(people["worker"], company, date(2026, 9, 1))

    assert saldo.taken == 10


@pytest.mark.django_db
def test_it_cannot_be_decided_twice(company, people):
    from apps.common.exceptions import BusinessRuleError

    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 10))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 5), date(2026, 8, 20))
        approve_absence(baja, resolved_by=people["boss"])

        recovery = RecoveredHoliday.objects.get()
        confirm_recovery(recovery=recovery, company=company, decided_by=people["boss"], accept=True)
        with pytest.raises(BusinessRuleError) as caught:
            confirm_recovery(
                recovery=recovery, company=company, decided_by=people["boss"], accept=True
            )
    assert caught.value.code == "already_decided"


@pytest.mark.django_db
def test_the_queue_says_why_and_by_when(company, people):
    with tenant_context(company.id):
        tipo = kind(company, "es.sick.common", "EIGHTEEN_MONTHS")
        holiday(company, people["worker"], date(2026, 8, 1), date(2026, 8, 10))
        baja = sick(company, people["worker"], tipo, date(2026, 8, 5), date(2026, 8, 20))
        approve_absence(baja, resolved_by=people["boss"])

        rows = pending_recoveries(company=company)

    assert len(rows) == 1
    assert rows[0]["days"] == 6
    assert rows[0]["expires_on"] == "2028-06-30"
    assert rows[0]["because_of"] == "es.sick.common"
