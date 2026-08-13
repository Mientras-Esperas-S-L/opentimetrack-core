"""Clock-in rules.

This is the part with legal weight. If any of these break, the record stops
being trustworthy, so they are written against the behaviour a labour inspector
would check, not against the implementation.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchSource, PunchType
from apps.punches.services import build_day_status, register_punch
from apps.tenants.models import Tenant
from apps.users.models import User


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Ana",
            last_name="García",
        )


# ------------------------------------------------------------- the server's time


@pytest.mark.django_db
def test_the_timestamp_comes_from_the_server(company, employee):
    """ADR-0007. The client never supplies the time, so it cannot fake it."""
    before = timezone.now()
    punch = register_punch(employee=employee, company=company)
    after = timezone.now()

    assert before <= punch.timestamp <= after


@pytest.mark.django_db
def test_the_type_is_inferred_and_alternates(company, employee):
    """One tap. Nobody is asked whether they are arriving or leaving.

    Con el reloj movido entre uno y otro, que es lo que pasa de verdad: tres
    eventos de una jornada están separados por horas, no por microsegundos.
    Pegados los rechaza `_refuse_a_double_tap`, y con razón.
    """
    with freeze_time("2026-08-13 08:00:00"):
        first = register_punch(employee=employee, company=company)
    with freeze_time("2026-08-13 13:00:00"):
        second = register_punch(employee=employee, company=company)
    with freeze_time("2026-08-13 14:00:00"):
        third = register_punch(employee=employee, company=company)

    assert [first.punch_type, second.punch_type, third.punch_type] == [
        PunchType.IN,
        PunchType.OUT,
        PunchType.IN,
    ]


# -------------------------------------------------------------------- integrity


@pytest.mark.django_db
def test_every_event_is_born_with_its_hash(company, employee):
    punch = register_punch(employee=employee, company=company)

    assert len(punch.hash_integrity) == 64
    assert punch.verify_hash()


@pytest.mark.django_db
def test_tampering_with_the_record_breaks_the_hash(company, employee):
    """The point of the hash: a change made behind the API's back is detectable."""
    punch = register_punch(employee=employee, company=company)

    Punch.objects_all_tenants.filter(pk=punch.pk).update(
        timestamp=punch.timestamp - timedelta(hours=2)
    )
    punch.refresh_from_db()

    assert not punch.verify_hash()


@pytest.mark.django_db
def test_voiding_does_not_invalidate_the_hash(company, employee):
    """Voiding is a later act, not a change to what was recorded."""
    punch = register_punch(employee=employee, company=company)

    punch.is_active = False
    punch.voided_at = timezone.now()
    punch.save()
    punch.refresh_from_db()

    assert punch.verify_hash()


# ----------------------------------------------------------- source of the event


@pytest.mark.django_db
def test_the_source_is_recorded_and_delegation_is_distinguishable(company, employee):
    """An inspector is entitled to know whether the person clocked in themselves."""
    admin = User.objects.create_user(
        email="admin@example.com",
        password="a-sufficiently-long-password",
        tenant=company,
        first_name="Admin",
        last_name="Person",
    )

    with freeze_time("2026-08-13 08:00:00"):
        own = register_punch(employee=employee, company=company, source=PunchSource.MOBILE)
    with freeze_time("2026-08-13 13:00:00"):
        delegated = register_punch(
            employee=employee,
            company=company,
            source=PunchSource.DELEGATED,
            source_application="GreenCity",
            recorded_by=admin,
        )

    assert not own.was_delegated
    assert delegated.was_delegated
    assert delegated.source_application == "GreenCity"
    assert delegated.recorded_by == admin


# ------------------------------------------------------------------ blocking rules


@pytest.mark.django_db
def test_approved_leave_blocks_clocking_in(company, employee):
    today = timezone.now().astimezone(company.tzinfo).date()
    Absence.objects.create(
        tenant=company,
        employee=employee,
        absence_type=AbsenceType.VACATION,
        start_date=today,
        end_date=today,
        status=AbsenceStatus.APPROVED,
    )

    with pytest.raises(BusinessRuleError) as caught:
        register_punch(employee=employee, company=company)

    assert caught.value.code == "punch_blocked_by_absence"
    assert caught.value.status_code == 409  # a rule, not a malformed request


@pytest.mark.django_db
def test_leave_still_pending_does_not_block(company, employee):
    today = timezone.now().astimezone(company.tzinfo).date()
    Absence.objects.create(
        tenant=company,
        employee=employee,
        absence_type=AbsenceType.VACATION,
        start_date=today,
        end_date=today,
        status=AbsenceStatus.PENDING,
    )

    assert register_punch(employee=employee, company=company) is not None


@pytest.mark.django_db
def test_a_deactivated_person_cannot_clock_in(company, employee):
    employee.is_active = False
    employee.save()

    with pytest.raises(BusinessRuleError) as caught:
        register_punch(employee=employee, company=company)

    assert caught.value.code == "employee_inactive"


# --------------------------------------------------------------- day calculation


@pytest.mark.django_db
def test_the_day_adds_up_its_segments(company, employee):
    with freeze_time("2026-08-11 06:00:00"):
        register_punch(employee=employee, company=company)  # in  08:00 local
    with freeze_time("2026-08-11 10:00:00"):
        register_punch(employee=employee, company=company)  # out 12:00 local
    with freeze_time("2026-08-11 11:00:00"):
        register_punch(employee=employee, company=company)  # in  13:00 local
    with freeze_time("2026-08-11 15:00:00"):
        register_punch(employee=employee, company=company)  # out 17:00 local
        status = build_day_status(employee, company)

    assert status.state == "OFF"
    assert len(status.segments) == 2
    assert status.worked_seconds == 8 * 3600


@pytest.mark.django_db
def test_an_open_segment_leaves_the_day_as_working(company, employee):
    with freeze_time("2026-08-11 06:00:00"):
        register_punch(employee=employee, company=company)
    with freeze_time("2026-08-11 08:30:00"):
        status = build_day_status(employee, company)

    assert status.state == "WORKING"
    assert status.segments[-1].is_open
    assert status.worked_seconds == pytest.approx(2.5 * 3600, abs=2)


@pytest.mark.django_db
def test_a_day_with_no_events_reads_as_not_started(company, employee):
    status = build_day_status(employee, company)

    assert status.state == "NOT_STARTED"
    assert status.worked_seconds == 0


@pytest.mark.django_db
def test_the_day_boundary_follows_the_company_zone_not_utc(db):
    """A night shift must not be split in half by the wrong midnight.

    In Madrid in August (UTC+2), 23:30 local is 21:30 UTC of the same day. Slicing
    the day by UTC would still work here, but at 00:30 local it would not: that is
    22:30 UTC of the *previous* day, and the entry would land in the wrong day.
    """
    company = Tenant.objects.create(name="Night Ltd", tax_id="B55555555", time_zone="Europe/Madrid")
    with tenant_context(company.id):
        worker = User.objects.create_user(
            email="noche@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Nica",
            last_name="Turno",
        )

        # 00:30 local on the 12th == 22:30 UTC on the 11th.
        with freeze_time("2026-08-11 22:30:00"):
            punch = register_punch(employee=worker, company=company)
            status = build_day_status(worker, company)

        assert punch.timestamp.astimezone(company.tzinfo).date() == date(2026, 8, 12)
        # It belongs to the 12th locally, so the 12th is the day that sees it.
        assert status.state == "WORKING"
