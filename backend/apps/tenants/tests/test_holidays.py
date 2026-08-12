"""Festivos: a quién le tocan y qué cambian.

Art. 37.2 ET: catorce al año como máximo, **dos de ellos locales**. Esa frase
decide el diseño entero. Dos centros de la misma empresa en provincias distintas
no comparten sus dos últimos días, así que un festivo pertenece a un sitio y no
a una empresa.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.absences.services import vacation_balance
from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.holidays import HolidayScope, PublicHoliday, holidays_for
from apps.tenants.models import Tenant
from apps.users.models import User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", annual_leave_days=22
    )


@pytest.fixture
def world(company):
    with tenant_context(company.id):
        jerez = Workplace.objects.create(
            tenant=company, name="Jerez", municipality="Jerez", region="ES-AN"
        )
        madrid = Workplace.objects.create(
            tenant=company, name="Madrid", municipality="Madrid", region="ES-MD"
        )

        def person(email, workplace):
            return User.objects.create_user(
                email=email,
                password=PASSWORD,
                tenant=company,
                first_name=email[:3],
                workplace=workplace,
            )

        yield {
            "jerez": jerez,
            "madrid": madrid,
            "sur": person("sur@example.com", jerez),
            "centro": person("centro@example.com", madrid),
        }


def holiday(company, day, name, *, workplace=None, scope=HolidayScope.LOCAL):
    with tenant_context(company.id):
        return PublicHoliday.objects.create(
            tenant=company, day=day, name=name, workplace=workplace, scope=scope
        )


# ------------------------------------------------------------------ a quién


@pytest.mark.django_db
def test_a_company_wide_holiday_reaches_everybody(company, world):
    holiday(company, date(2026, 12, 25), "Navidad", scope=HolidayScope.NATIONAL)

    with tenant_context(company.id):
        for who in ("sur", "centro"):
            assert holidays_for(world[who], date(2026, 12, 1), date(2026, 12, 31)) == {
                date(2026, 12, 25)
            }


@pytest.mark.django_db
def test_a_local_holiday_reaches_only_its_workplace(company, world):
    """El caso que justifica que el festivo cuelgue del sitio: el 24 de
    septiembre es la Merced en Barcelona y un jueves cualquiera en Jerez."""
    holiday(company, date(2026, 9, 24), "Fiesta local", workplace=world["jerez"])

    with tenant_context(company.id):
        window = (date(2026, 9, 1), date(2026, 9, 30))
        assert holidays_for(world["sur"], *window) == {date(2026, 9, 24)}
        assert holidays_for(world["centro"], *window) == set()


@pytest.mark.django_db
def test_somebody_with_no_workplace_still_gets_the_national_ones(company, world):
    """Lo contrario dejaría sin Navidad a quien no tenga centro asignado, que es
    todo el mundo el día que se estrena la función."""
    with tenant_context(company.id):
        nobody = User.objects.create_user(
            email="sin@example.com", password=PASSWORD, tenant=company, first_name="Sin"
        )
    holiday(company, date(2026, 12, 25), "Navidad", scope=HolidayScope.NATIONAL)
    holiday(company, date(2026, 9, 24), "Fiesta local", workplace=world["jerez"])

    with tenant_context(company.id):
        assert holidays_for(nobody, date(2026, 1, 1), date(2026, 12, 31)) == {date(2026, 12, 25)}


# ------------------------------------------------------------- las vacaciones


@pytest.mark.django_db
def test_a_holiday_inside_a_holiday_is_not_a_day_spent(company, world):
    """Una semana de vacaciones con un festivo dentro cuesta cuatro días, no
    cinco: el festivo no era un día que fuera a trabajar."""
    holiday(company, date(2026, 12, 8), "Inmaculada", scope=HolidayScope.NATIONAL)

    with tenant_context(company.id):
        Absence.objects.create(
            tenant=company,
            employee=world["sur"],
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 12, 7),
            end_date=date(2026, 12, 11),
            status=AbsenceStatus.APPROVED,
        )
        assert vacation_balance(world["sur"], company, date(2026, 12, 15)).taken == 4


@pytest.mark.django_db
def test_and_the_colleague_without_that_holiday_spends_five(company, world):
    """La misma semana, el mismo contrato, y distinto saldo. Eso es lo que
    significa que los festivos cuelguen del centro."""
    holiday(company, date(2026, 12, 8), "Fiesta local", workplace=world["jerez"])

    with tenant_context(company.id):
        for who in ("sur", "centro"):
            Absence.objects.create(
                tenant=company,
                employee=world[who],
                absence_type=AbsenceType.VACATION,
                start_date=date(2026, 12, 7),
                end_date=date(2026, 12, 11),
                status=AbsenceStatus.APPROVED,
            )
        assert vacation_balance(world["sur"], company, date(2026, 12, 15)).taken == 4
        assert vacation_balance(world["centro"], company, date(2026, 12, 15)).taken == 5


# --------------------------------------------------------------- el cuadrante


@pytest.mark.django_db
def test_rostering_somebody_on_a_holiday_is_reported_not_refused(company, world):
    """Trabajar un festivo es lícito. Lo que genera es compensación, y por eso
    se avisa: la deuda empieza el día que se trabaja."""
    holiday(company, date(2026, 12, 8), "Inmaculada", scope=HolidayScope.NATIONAL)

    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=world["sur"],
            day=date(2026, 12, 8),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        findings = review_roster(company=company, first=date(2026, 12, 1), last=date(2026, 12, 31))

    rows = [f for f in findings if f.code == "rostered_on_a_holiday"]
    assert len(rows) == 1
    assert rows[0].basis == "Art. 37.2 ET"


@pytest.mark.django_db
def test_only_for_whoever_that_day_is_a_holiday_for(company, world):
    holiday(company, date(2026, 12, 8), "Fiesta local", workplace=world["jerez"])

    with tenant_context(company.id):
        for who in ("sur", "centro"):
            Shift.objects.create(
                tenant=company,
                employee=world[who],
                day=date(2026, 12, 8),
                segments=[{"start": "08:00", "end": "16:00"}],
            )
        findings = review_roster(company=company, first=date(2026, 12, 1), last=date(2026, 12, 31))

    rows = [f for f in findings if f.code == "rostered_on_a_holiday"]
    assert [f.employee_id for f in rows] == [world["sur"].pk]


@pytest.mark.django_db
def test_the_same_day_cannot_be_recorded_twice_for_the_same_place(company, world):
    """Postgres trata los NULL como distintos, así que una sola restricción
    sobre (empresa, día, centro) aceptaría dos veces el mismo día de empresa."""
    from django.db import IntegrityError, transaction

    holiday(company, date(2026, 12, 25), "Navidad", scope=HolidayScope.NATIONAL)

    with pytest.raises(IntegrityError), transaction.atomic(), tenant_context(company.id):
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 12, 25), name="Navidad otra vez"
        )
