"""Leave: requesting, resolving, and the balance.

The balance tests carry most of the weight. A wrong figure here is not a
cosmetic bug: somebody books days they do not have, or loses days they do.
"""

from __future__ import annotations

from datetime import date, timedelta

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
    """1 to 5 July 2026 is Wednesday to Sunday: three working days, not five.

    The entitlement is expressed in working days, so the deduction is too.
    Counting the weekend was the old behaviour and it is what made everybody run
    out of holiday in October.
    """
    absence = _ask(company, employee, date(2026, 7, 1), date(2026, 7, 5))
    approve_absence(absence, resolved_by=manager)

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    assert balance.entitled == 22
    assert balance.taken == 3
    assert balance.remaining == 19
    assert balance.working_days is True


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
    """30 Dec to 2 Jan: two working days in one period, one in the next.

    Wednesday and Thursday on the 2026 side; Friday on the 2027 side, because
    the 2nd is a Saturday.
    """
    absence = _ask(company, employee, date(2026, 12, 30), date(2027, 1, 2))
    approve_absence(absence, resolved_by=manager)

    assert vacation_balance(employee, company, date(2026, 12, 1)).taken == 2
    assert vacation_balance(employee, company, date(2027, 2, 1)).taken == 1


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


# ------------------------------------------------------- working or calendar
#
# The bug these pin down: the entitlement was documented in working days and
# the consumption counted calendar days, so a fortnight off took fourteen of
# twenty-two. Nothing on any screen said which unit anything was in.


@pytest.mark.django_db
def test_a_fortnight_off_costs_ten_days_not_fourteen(company, employee, manager):
    """Two full weeks, Monday to Sunday twice over."""
    absence = _ask(company, employee, date(2026, 7, 6), date(2026, 7, 19))
    approve_absence(absence, resolved_by=manager)

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    assert balance.taken == 10
    assert balance.remaining == 12


@pytest.mark.django_db
def test_the_company_can_count_calendar_days_instead(company, employee, manager):
    """Plenty of agreements say thirty natural days and mean it. Then the
    weekend does come off, and the entitlement is the thirty-day figure."""
    company.leave_days_are_working_days = False
    company.annual_leave_days = 30
    company.save(update_fields=["leave_days_are_working_days", "annual_leave_days"])

    absence = _ask(company, employee, date(2026, 7, 6), date(2026, 7, 19))
    approve_absence(absence, resolved_by=manager)

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    assert balance.taken == 14
    assert balance.remaining == 16
    assert balance.working_days is False


@pytest.mark.django_db
def test_a_working_day_is_a_day_that_person_works(company, employee, manager):
    """Not Monday to Friday. Somebody on a rotating rota works Saturdays, and
    charging them for a Sunday they were never going to work is the same
    mistake in a smaller size."""
    from apps.shifts.models import Shift

    with tenant_context(company.id):
        # Rostered Thursday to Sunday, off Monday to Wednesday.
        for day in (date(2026, 7, 9), date(2026, 7, 10), date(2026, 7, 11), date(2026, 7, 12)):
            Shift.objects.create(
                tenant=company,
                employee=employee,
                day=day,
                segments=[{"start": "08:00", "end": "16:00"}],
            )

    absence = _ask(company, employee, date(2026, 7, 6), date(2026, 7, 12))
    approve_absence(absence, resolved_by=manager)

    # Four rostered days in that week, two of them at the weekend.
    assert vacation_balance(employee, company, date(2026, 8, 1)).taken == 4


@pytest.mark.django_db
def test_with_no_roster_at_all_it_falls_back_to_monday_to_friday(company, employee, manager):
    """Somebody on a flexible arrangement has no roster. Deducting every
    calendar day would be the old bug back for exactly the people the flexible
    checks were added for."""
    absence = _ask(company, employee, date(2026, 7, 6), date(2026, 7, 12))
    approve_absence(absence, resolved_by=manager)

    assert vacation_balance(employee, company, date(2026, 8, 1)).taken == 5


@pytest.mark.django_db
def test_the_roster_only_speaks_for_the_days_it_reaches(company, employee, manager):
    """Vacaciones a meses vista, cuadrante a semanas vista: el caso normal es
    una ausencia que el cuadrante cubre a medias. Antes, un solo turno en el
    rango hacía contar únicamente los días con turno, y una quincena con una
    semana publicada costaba cinco días en vez de diez."""
    from apps.shifts.models import Shift

    with tenant_context(company.id):
        # Cuadrante publicado solo la primera semana: lunes a viernes.
        for offset in range(5):
            Shift.objects.create(
                tenant=company,
                employee=employee,
                day=date(2026, 7, 6) + timedelta(days=offset),
                segments=[{"start": "08:00", "end": "16:00"}],
            )

    absence = _ask(company, employee, date(2026, 7, 6), date(2026, 7, 19))
    approve_absence(absence, resolved_by=manager)

    balance = vacation_balance(employee, company, date(2026, 8, 1))
    # Primera semana del cuadrante: 5. Segunda, sin publicar: lunes-viernes, 5.
    assert balance.taken == 10


@pytest.mark.django_db
def test_but_inside_its_reach_a_gap_is_a_real_day_off(company, employee, manager):
    """Si el cuadrante llega más allá de la ausencia, sus huecos son descansos
    de verdad y no deben descontarse."""
    from apps.shifts.models import Shift

    with tenant_context(company.id):
        # Rota jueves a domingo esa semana, y tiene cuadrante la semana
        # siguiente también: el horizonte va más allá de la ausencia.
        for day in (
            date(2026, 7, 9),
            date(2026, 7, 10),
            date(2026, 7, 11),
            date(2026, 7, 12),
            date(2026, 7, 16),
        ):
            Shift.objects.create(
                tenant=company,
                employee=employee,
                day=day,
                segments=[{"start": "08:00", "end": "16:00"}],
            )

    absence = _ask(company, employee, date(2026, 7, 6), date(2026, 7, 12))
    approve_absence(absence, resolved_by=manager)

    # Solo los cuatro días rotados dentro de la semana pedida.
    assert vacation_balance(employee, company, date(2026, 8, 1)).taken == 4


# ------------------------------------------------- vacaciones que se devengan


@pytest.mark.django_db
def test_somebody_hired_in_march_has_not_earned_the_whole_year(company, employee):
    """Las vacaciones se ganan trabajando. Quien entra el 9 de marzo no ha
    ganado el año entero en marzo.

    Hasta el 13/08/2026 esto daba los 22 días a todo el mundo desde el primer
    día. En una empresa con temporeros no es un redondeo: son semanas regaladas
    que luego se liquidan en la nómina.
    """
    with tenant_context(company.id):
        employee.contract_start = date(2026, 3, 9)
        employee.save()
        balance = vacation_balance(employee, company, date(2026, 8, 1))

    # Del 9 de marzo al 31 de diciembre son 298 días de 365.
    # 22 x 298/365 = 17,96 -> 18, redondeando al alza.
    assert balance.entitled == 18
    assert balance.full_year == 22
    assert balance.prorated is True
    assert balance.accrued_from == date(2026, 3, 9)


@pytest.mark.django_db
def test_a_three_month_contract_earns_three_months_of_holiday(company, employee):
    with tenant_context(company.id):
        employee.contract_start = date(2026, 6, 1)
        employee.contract_end = date(2026, 8, 31)
        employee.save()
        balance = vacation_balance(employee, company, date(2026, 8, 1))

    # 92 días de 365: 22 x 92/365 = 5,54 -> 6.
    assert balance.entitled == 6
    assert balance.accrued_from == date(2026, 6, 1)
    assert balance.accrued_to == date(2026, 8, 31)


@pytest.mark.django_db
def test_a_full_year_is_not_prorated(company, employee):
    """Alguien con contrato desde antes y sin fin: el año entero, y sin ruido
    en la respuesta."""
    with tenant_context(company.id):
        employee.contract_start = date(2019, 1, 7)
        employee.save()
        balance = vacation_balance(employee, company, date(2026, 8, 1))

    assert balance.entitled == 22
    assert balance.prorated is False
    assert balance.accrued_from is None


@pytest.mark.django_db
def test_rounding_goes_up_because_the_figure_is_a_legal_floor(company, employee):
    """Redondear a la baja quitaría días sobre un mínimo del art. 38.1. Al alza
    el peor caso es dar medio día de más."""
    with tenant_context(company.id):
        employee.contract_start = date(2026, 12, 31)  # un solo día
        employee.save()
        balance = vacation_balance(employee, company, date(2026, 12, 31))

    assert balance.entitled == 1  # 22 x 1/365 = 0,06 -> 1, no 0


@pytest.mark.django_db
def test_a_contract_that_does_not_reach_this_period_earns_nothing(company, employee):
    with tenant_context(company.id):
        employee.contract_start = date(2027, 2, 1)
        employee.save()
        balance = vacation_balance(employee, company, date(2026, 8, 1))

    assert balance.entitled == 0


@pytest.mark.django_db
def test_the_balance_reaches_the_api_saying_why(company, employee):
    """La cifra prorrateada sin explicación acaba en una discusión. Va con lo
    que daría el año completo y con el tramo que se ha devengado."""
    from rest_framework.test import APIClient

    with tenant_context(company.id):
        employee.contract_start = date(2026, 3, 9)
        employee.save()

    client = APIClient()
    client.force_authenticate(user=employee)
    body = client.get("/api/absences/balance/").json()

    assert body["entitled"] == 18
    assert body["full_year"] == 22
    assert body["prorated"] is True
    assert body["accrued_from"] == "2026-03-09"
