"""Suspensiones del contrato.

No son permisos: el contrato se para y no hay obligación de trabajar. Entran
porque durante ellas **no debe esperarse jornada**, que es lo que explica el
hueco en el registro. La tramitación --- el parte al INSS, el expediente del
ERTE --- se hace en otro sitio.

Casi todas encajan en la maquinaria que ya había: una ausencia de días
completos, más larga. La que no es el **ERTE de reducción de jornada**, que no
para el contrato sino que lo encoge, y sin el que todo el cuadrante de una
empresa en ERTE parcial se lee como incumplimiento.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import AbsenceStatus, LeaveType
from apps.absences.services import request_absence
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import HoursPeriod, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        seed_leave_types(company)
        yield User.objects.create_user(
            email="ana@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            regime=WorkingTimeRegime.FULL_TIME,
            contracted_hours=40,
            contracted_period=HoursPeriod.WEEK,
        )


def suspend(company, who, code, first, last, *, share=None, status=AbsenceStatus.APPROVED):
    with tenant_context(company.id):
        absence = request_absence(
            employee=who,
            company=company,
            leave_type=LeaveType.objects.get(code=code),
            start_date=first,
            end_date=last,
            reduction_share=share,
        )
        absence.status = status
        absence.save(update_fields=["status"])
        return absence


# ----------------------------------------------------------- las que paran


@pytest.mark.django_db
def test_the_catalogue_carries_the_fifteen_of_article_45(company, worker):
    with tenant_context(company.id):
        codes = set(LeaveType.objects.filter(family="SUSPENSION").values_list("code", flat=True))

    assert {"es.birth", "es.erte", "es.strike", "es.unpaid_leave", "es.custody"} <= codes


@pytest.mark.django_db
def test_none_of_them_is_paid_by_the_company(company, worker):
    """Paga la Seguridad Social, la mutua, o nadie. Quién paga se dice en la
    nota, porque el campo solo distingue si sale de la nómina."""
    with tenant_context(company.id):
        assert not LeaveType.objects.filter(family="SUSPENSION", paid=True).exists()


@pytest.mark.django_db
def test_a_suspension_blocks_clocking(company, worker):
    today = date.today()
    suspend(
        company, worker, "es.unpaid_leave", today - timedelta(days=30), today + timedelta(days=300)
    )

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        register_punch(employee=worker, company=company)

    assert caught.value.code == "punch_blocked_by_absence"


@pytest.mark.django_db
def test_and_the_roster_reports_anybody_planned_during_one(company, worker):
    with tenant_context(company.id):
        suspend(company, worker, "es.birth", date(2026, 9, 1), date(2026, 12, 20))
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 15),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert any(f.code == "rostered_on_leave" for f in findings)


# ------------------------------------------------------- el ERTE que encoge


@pytest.mark.django_db
def test_a_partial_erte_does_not_block_clocking(company, worker):
    """Quien tiene la jornada reducida un cuarenta por ciento sigue viniendo
    por el otro sesenta."""
    today = date.today()
    suspend(
        company, worker, "es.erte", today - timedelta(days=10), today + timedelta(days=80), share=40
    )

    with tenant_context(company.id):
        assert register_punch(employee=worker, company=company) is not None


@pytest.mark.django_db
def test_the_roster_is_measured_against_the_reduced_contract(company, worker):
    """Sin esto, el cuadrante entero de una empresa en ERTE parcial se lee como
    que todo el mundo se pasa de sus horas todas las semanas --- que es lo
    contrario de lo que ha pasado."""
    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        # Cinco días de cinco horas: 25 h, por debajo de 40 y por encima del
        # 60 % de 40, que son 24.
        for offset in range(5):
            Shift.objects.create(
                tenant=company,
                employee=worker,
                day=monday + timedelta(days=offset),
                segments=[{"start": "09:00", "end": "14:00"}],
            )

        sin_erte = review_roster(company=company, first=monday, last=monday + timedelta(days=6))
        assert [f for f in sin_erte if f.code == "over_contracted_hours"] == []

        suspend(company, worker, "es.erte", monday, monday + timedelta(days=90), share=40)
        con_erte = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    over = [f for f in con_erte if f.code == "over_contracted_hours"]
    assert len(over) == 1
    # Y dice la cifra reducida, no la del contrato entero.
    assert "24 h" in str(over[0].message)


@pytest.mark.django_db
def test_a_full_suspension_leaves_the_roster_arithmetic_alone(company, worker):
    """Cien por cien no es una reducción: es la suspensión de siempre, y el
    cuadrante no debería medirse contra cero."""
    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        for offset in range(5):
            Shift.objects.create(
                tenant=company,
                employee=worker,
                day=monday + timedelta(days=offset),
                segments=[{"start": "09:00", "end": "14:00"}],
            )
        suspend(company, worker, "es.erte", monday, monday + timedelta(days=90), share=100)
        findings = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    assert [f for f in findings if f.code == "over_contracted_hours"] == []


@pytest.mark.django_db
def test_only_a_suspension_can_reduce_the_day(company, worker):
    """En cualquier otro sitio parecería un ajuste y no haría nada, que es la
    peor clase de campo."""
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            reduction_share=40,
        )

    assert caught.value.code == "reduction_needs_a_suspension"


@pytest.mark.django_db
def test_a_suspension_spends_no_holiday(company, worker):
    from apps.absences.services import vacation_balance

    with tenant_context(company.id):
        suspend(company, worker, "es.birth", date(2026, 9, 1), date(2026, 12, 20))
        assert vacation_balance(worker, company, date(2026, 10, 1)).taken == 0


@pytest.mark.django_db
def test_a_pending_suspension_does_not_block_anything(company, worker):
    """Sólo lo aprobado para el registro. Una solicitud sin resolver es una
    intención, y el registro no se mide contra intenciones."""
    today = date.today()
    suspend(
        company,
        worker,
        "es.unpaid_leave",
        today,
        today + timedelta(days=90),
        status=AbsenceStatus.PENDING,
    )

    with tenant_context(company.id):
        assert register_punch(employee=worker, company=company) is not None
