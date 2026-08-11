"""Leave: requesting, resolving, and the balance.

The balance tests carry most of the weight. A wrong figure here is not a
cosmetic bug: somebody books days they do not have, or loses days they do.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.absences.services import (
    approve_absence,
    cancel_absence,
    leave_period_for,
    reject_absence,
    request_absence,
    vacation_balance,
)
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", annual_leave_days=22
    )


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="iker@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Iker",
            last_name="Mena",
        )


@pytest.fixture
def manager(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Luisa",
            last_name="Ferrer",
            role=Role.MANAGER,
        )


def _ask(company, employee, start, end, kind=AbsenceType.VACATION, **kw):
    return request_absence(
        employee=employee,
        company=company,
        absence_type=kind,
        start_date=start,
        end_date=end,
        **kw,
    )


# ------------------------------------------------------------ the reference period


@pytest.mark.django_db
def test_by_default_the_period_is_the_calendar_year(company):
    start, end = leave_period_for(company, date(2026, 6, 15))
    assert (start, end) == (date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.django_db
def test_the_period_can_start_in_another_month(company):
    """The agreement decides, not the calendar. An April-March period was one of
    the four things the legal review corrected."""
    company.leave_year_start_month = 4
    company.save(update_fields=["leave_year_start_month"])

    assert leave_period_for(company, date(2026, 6, 15)) == (date(2026, 4, 1), date(2027, 3, 31))
    # A day before April belongs to the period that opened the previous year.
    assert leave_period_for(company, date(2026, 2, 10)) == (date(2025, 4, 1), date(2026, 3, 31))


# ----------------------------------------------------------------------- balance


@pytest.mark.django_db
def test_approved_leave_comes_off_the_balance(company, employee, manager):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))  # 5 days
    approve_absence(absence, resolved_by=manager)

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    assert balance.entitled == 22
    assert balance.taken == 5
    assert balance.remaining == 17


@pytest.mark.django_db
def test_pending_requests_also_come_off(company, employee):
    """Otherwise two people book the same last day and both are told yes."""
    _ask(company, employee, date(2026, 7, 1), date(2026, 7, 3))

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    assert balance.pending == 3
    assert balance.taken == 0
    assert balance.remaining == 19


@pytest.mark.django_db
def test_a_rejected_request_does_not_count(company, employee, manager):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 3))
    reject_absence(absence, resolved_by=manager)

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    assert balance.remaining == 22


@pytest.mark.django_db
def test_leave_straddling_the_period_boundary_only_counts_its_own_days(company, employee, manager):
    """30 Dec to 2 Jan is two days in one period and two in the next."""
    absence = _ask(company, employee, date(2026, 12, 30), date(2027, 1, 2))
    approve_absence(absence, resolved_by=manager)

    assert vacation_balance(employee, company, date(2026, 12, 1)).taken == 2
    assert vacation_balance(employee, company, date(2027, 2, 1)).taken == 2


@pytest.mark.django_db
def test_a_person_can_have_their_own_entitlement(company, employee):
    """Part-time and mid-year joiners are the usual reason."""
    employee.annual_leave_days = 11
    employee.save(update_fields=["annual_leave_days"])

    assert vacation_balance(employee, company).entitled == 11


@pytest.mark.django_db
def test_sick_leave_does_not_touch_the_holiday_balance(company, employee, manager):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 10), AbsenceType.SICK_LEAVE)
    approve_absence(absence, resolved_by=manager)

    assert vacation_balance(employee, company, date(2026, 8, 1)).taken == 0


# ---------------------------------------------------------------------- requests


@pytest.mark.django_db
def test_overlapping_leave_is_refused(company, employee):
    _ask(company, employee, date(2026, 7, 1), date(2026, 7, 10))

    with pytest.raises(BusinessRuleError) as caught:
        _ask(company, employee, date(2026, 7, 8), date(2026, 7, 12))

    assert caught.value.code == "overlapping_absence"


@pytest.mark.django_db
def test_a_pending_request_also_blocks_an_overlap(company, employee):
    """Two overlapping requests in the queue mean whoever approves the second
    creates a contradiction nobody catches."""
    _ask(company, employee, date(2026, 7, 1), date(2026, 7, 10))

    with pytest.raises(BusinessRuleError):
        _ask(company, employee, date(2026, 7, 5), date(2026, 7, 6), AbsenceType.PERSONAL)


@pytest.mark.django_db
def test_leave_ending_before_it_starts_is_refused(company, employee):
    with pytest.raises(BusinessRuleError) as caught:
        _ask(company, employee, date(2026, 7, 10), date(2026, 7, 1))

    assert caught.value.code == "ends_before_it_starts"


@pytest.mark.django_db
def test_two_people_may_take_the_same_days(company, employee, manager):
    """The clash rule is per person, not company-wide. Getting this wrong would
    stop a second person booking a day somebody else already has."""
    _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    other = _ask(company, manager, date(2026, 7, 1), date(2026, 7, 5))

    assert other.pk is not None


# --------------------------------------------------------------------- decisions


@pytest.mark.django_db
def test_it_cannot_be_resolved_twice(company, employee, manager):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    approve_absence(absence, resolved_by=manager)

    with pytest.raises(BusinessRuleError) as caught:
        reject_absence(absence, resolved_by=manager)

    assert caught.value.code == "already_resolved"


@pytest.mark.django_db
def test_the_decision_records_who_and_when(company, employee, manager):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    approve_absence(absence, resolved_by=manager)
    absence.refresh_from_db()

    assert absence.status == AbsenceStatus.APPROVED
    assert absence.approved_by == manager
    assert absence.resolved_at is not None


@pytest.mark.django_db
def test_a_rejected_request_is_kept(company, employee, manager):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    reject_absence(absence, resolved_by=manager)

    assert Absence.objects_all_tenants.filter(pk=absence.pk).exists()


@pytest.mark.django_db
def test_you_can_withdraw_your_own_pending_request(company, employee):
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    cancel_absence(absence, cancelled_by=employee)

    assert not Absence.objects_all_tenants.filter(pk=absence.pk).exists()


@pytest.mark.django_db
def test_you_cannot_withdraw_somebody_elses(company, employee, manager):
    absence = _ask(company, manager, date(2026, 7, 1), date(2026, 7, 5))

    with pytest.raises(BusinessRuleError) as caught:
        cancel_absence(absence, cancelled_by=employee)

    assert caught.value.code == "not_your_request"


@pytest.mark.django_db
def test_an_approved_request_is_not_withdrawn_by_the_employee(company, employee, manager):
    """It has blocked days and possibly other people's plans by then."""
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    approve_absence(absence, resolved_by=manager)

    with pytest.raises(BusinessRuleError) as caught:
        cancel_absence(absence, cancelled_by=employee)

    assert caught.value.code == "already_resolved"
