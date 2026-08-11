"""Corrections to the clock record.

The rule under test in every case: the original is never overwritten. What the
pending royal decree on digital time records is expected to require --- who
changed it, when, and why, without losing the previous version --- is what these
tests pin down.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.corrections import (
    CorrectionKind,
    CorrectionStatus,
    approve_correction,
    reject_correction,
    request_correction,
)
from apps.punches.models import Punch, PunchSource
from apps.punches.services import build_day_status, register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="marta@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Marta",
            last_name="Ruiz",
            employee_id="EMP-0003",
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


# --------------------------------------------------------- the reason is required


@pytest.mark.django_db
def test_a_correction_without_a_reason_is_refused(company, employee):
    """A correction with no stated reason is indistinguishable from tampering."""
    with pytest.raises(BusinessRuleError) as caught:
        request_correction(
            employee=employee,
            company=company,
            requested_by=employee,
            kind=CorrectionKind.ADD,
            reason="   ",
            proposed_type="OUT",
            proposed_timestamp=timezone.now(),
        )

    assert caught.value.code == "reason_required"


@pytest.mark.django_db
def test_the_reason_survives_into_the_record(company, employee, manager):
    with freeze_time("2026-08-10 06:00:00"):
        register_punch(employee=employee, company=company)

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.ADD,
        reason="Me quedé sin batería y no pude fichar la salida.",
        proposed_type="OUT",
        proposed_timestamp=timezone.now() - timedelta(hours=1),
    )
    approve_correction(correction, resolved_by=manager)
    correction.refresh_from_db()

    assert "batería" in correction.reason
    assert correction.resolved_by == manager
    assert correction.resolved_at is not None


# ------------------------------------------------------ the original is preserved


@pytest.mark.django_db
def test_changing_a_time_keeps_the_original_readable(company, employee, manager):
    """The heart of it: correcting must not erase what was recorded before."""
    with freeze_time("2026-08-10 06:00:00"):
        original = register_punch(employee=employee, company=company)
    original_stamp = original.timestamp

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.MODIFY,
        target=original,
        reason="El reloj del móvil iba adelantado, entré a las 08:15.",
        proposed_timestamp=original_stamp + timedelta(minutes=15),
    )
    new_punch = approve_correction(correction, resolved_by=manager)

    original.refresh_from_db()
    assert not original.is_active  # voided, not deleted
    assert original.timestamp == original_stamp  # untouched
    assert original.replaced_by == new_punch  # points to its replacement
    assert original.voided_at is not None
    assert new_punch.source == PunchSource.ADMIN  # not recorded as it happened
    assert new_punch.recorded_by == manager


@pytest.mark.django_db
def test_the_voided_original_still_verifies_its_own_hash(company, employee, manager):
    """Voiding is a later act, not a change to what was recorded."""
    with freeze_time("2026-08-10 06:00:00"):
        original = register_punch(employee=employee, company=company)

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.MODIFY,
        target=original,
        reason="Hora equivocada.",
        proposed_timestamp=original.timestamp + timedelta(minutes=10),
    )
    approve_correction(correction, resolved_by=manager)
    original.refresh_from_db()

    assert original.verify_hash()


@pytest.mark.django_db
def test_a_voided_event_stops_counting_towards_the_day(company, employee, manager):
    with freeze_time("2026-08-10 06:00:00"):
        wrong = register_punch(employee=employee, company=company)

        correction = request_correction(
            employee=employee,
            company=company,
            requested_by=employee,
            kind=CorrectionKind.VOID,
            target=wrong,
            reason="Fiché por error, ese día libraba.",
        )
        approve_correction(correction, resolved_by=manager)

        status = build_day_status(employee, company)

    assert status.state == "NOT_STARTED"
    wrong.refresh_from_db()
    assert not wrong.is_active


# ------------------------------------------------------------------- the workflow


@pytest.mark.django_db
def test_asking_changes_nothing_until_somebody_approves(company, employee):
    """A request is a claim, not a fact."""
    before = Punch.objects_all_tenants.count()

    request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.ADD,
        reason="Olvidé fichar la entrada.",
        proposed_type="IN",
        proposed_timestamp=timezone.now() - timedelta(hours=3),
    )

    assert Punch.objects_all_tenants.count() == before


@pytest.mark.django_db
def test_a_rejected_request_is_kept(company, employee, manager):
    """Somebody claimed they worked and was told no. That is history too."""
    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.ADD,
        reason="Trabajé el sábado.",
        proposed_type="IN",
        proposed_timestamp=timezone.now() - timedelta(days=2),
    )
    reject_correction(correction, resolved_by=manager, note="Ese día no había servicio.")
    correction.refresh_from_db()

    assert correction.status == CorrectionStatus.REJECTED
    assert correction.resolution_note
    assert Punch.objects_all_tenants.count() == 0


@pytest.mark.django_db
def test_it_cannot_be_resolved_twice(company, employee, manager):
    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.ADD,
        reason="Olvidé fichar.",
        proposed_type="IN",
        proposed_timestamp=timezone.now() - timedelta(hours=2),
    )
    approve_correction(correction, resolved_by=manager)

    with pytest.raises(BusinessRuleError) as caught:
        approve_correction(correction, resolved_by=manager)

    assert caught.value.code == "already_resolved"


# ----------------------------------------------------------------- what is refused


@pytest.mark.django_db
def test_a_time_in_the_future_is_refused(company, employee):
    """Not a forgotten clock-out: a mistake, or an attempt."""
    with pytest.raises(BusinessRuleError) as caught:
        request_correction(
            employee=employee,
            company=company,
            requested_by=employee,
            kind=CorrectionKind.ADD,
            reason="Voy a trabajar luego.",
            proposed_type="IN",
            proposed_timestamp=timezone.now() + timedelta(hours=2),
        )

    assert caught.value.code == "time_in_the_future"


@pytest.mark.django_db
def test_nobody_corrects_somebody_elses_event(company, employee, manager):
    with freeze_time("2026-08-10 06:00:00"):
        theirs = register_punch(employee=manager, company=company)

    with pytest.raises(BusinessRuleError) as caught:
        request_correction(
            employee=employee,
            company=company,
            requested_by=employee,
            kind=CorrectionKind.MODIFY,
            target=theirs,
            reason="Cambiar la hora.",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
        )

    assert caught.value.code == "not_your_event"


@pytest.mark.django_db
def test_adding_an_event_without_saying_which_kind_is_refused(company, employee):
    with pytest.raises(BusinessRuleError) as caught:
        request_correction(
            employee=employee,
            company=company,
            requested_by=employee,
            kind=CorrectionKind.ADD,
            reason="Falta un fichaje.",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
        )

    assert caught.value.code == "type_required"
