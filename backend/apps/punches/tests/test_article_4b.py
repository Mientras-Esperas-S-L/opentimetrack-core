"""Changing an entry needs both sides, and what happens when they disagree.

Art. 4.b of the pending royal decree, read carefully:

    «Cualquier modificación de los asientos practicados deberá efectuarse con
    la autorización de la empresa y de la persona trabajadora afectada. En caso
    de discrepancia [...] deberá informarse a la representación legal de las
    personas trabajadoras. En ausencia de acuerdo, la empresa reflejará en el
    registro la modificación y la persona trabajadora su discrepancia.»

Read quickly, the first sentence sounds like a veto for the worker. The last
one says it is not: without agreement the company **still** records the change,
and the person records their disagreement next to it.

So the thing under test is not consent as a gate. It is that the record can
hold two accounts of the same day and say which is whose, and that a reader can
always tell an accepted correction from an imposed one.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone, translation
from freezegun import freeze_time

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.corrections import (
    CorrectionKind,
    CorrectionStatus,
    accept_correction,
    apply_without_agreement,
    dispute_correction,
    propose_correction,
    request_correction,
)
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


@pytest.fixture
def boss(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Luisa",
            role=Role.MANAGER,
        )


def a_punch(company, worker):
    with tenant_context(company.id), freeze_time("2026-09-01 06:00:00"):
        return register_punch(employee=worker, company=company)


def proposal(company, worker, boss, target=None):
    with tenant_context(company.id):
        return propose_correction(
            employee=worker,
            company=company,
            proposed_by=boss,
            kind=CorrectionKind.MODIFY if target else CorrectionKind.ADD,
            reason="El fichaje no refleja la hora real de salida.",
            target=target,
            proposed_type="" if target else "OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=2),
        )


# ------------------------------------------------- the company proposing


@pytest.mark.django_db
def test_a_change_proposed_by_the_company_waits(company, worker, boss):
    """One authorisation is missing, so nothing is applied yet."""
    punch = a_punch(company, worker)
    correction = proposal(company, worker, boss, punch)

    assert correction.status == CorrectionStatus.AWAITING_EMPLOYEE
    assert correction.employee_agreed is None
    punch.refresh_from_db()
    assert punch.is_active


@pytest.mark.django_db
def test_asking_about_your_own_record_does_not_wait(company, worker, boss):
    """When the person asks and the company approves, both have authorised.
    Making them confirm their own request would be asking twice."""
    with tenant_context(company.id):
        correction = request_correction(
            employee=worker,
            company=company,
            requested_by=worker,
            kind=CorrectionKind.ADD,
            reason="Olvidé fichar la salida.",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
        )

    assert correction.status == CorrectionStatus.PENDING


@pytest.mark.django_db
def test_accepting_applies_it(company, worker, boss):
    punch = a_punch(company, worker)
    correction = proposal(company, worker, boss, punch)

    with tenant_context(company.id):
        accept_correction(correction, employee=worker)

    correction.refresh_from_db()
    punch.refresh_from_db()
    assert correction.status == CorrectionStatus.APPROVED
    assert correction.employee_agreed is True
    assert correction.employee_responded_at is not None
    assert not punch.is_active
    assert not correction.applied_without_agreement


@pytest.mark.django_db
def test_only_the_person_concerned_can_answer(company, worker, boss):
    """Not even a manager may agree on somebody's behalf. The authorisation the
    article asks for is theirs, and one given by somebody else is not one."""
    correction = proposal(company, worker, boss, a_punch(company, worker))

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        accept_correction(correction, employee=boss)

    assert caught.value.code == "not_your_record"


# ---------------------------------------------------------- disagreeing


@pytest.mark.django_db
def test_disagreeing_records_their_account_and_applies_nothing(company, worker, boss):
    punch = a_punch(company, worker)
    correction = proposal(company, worker, boss, punch)

    with tenant_context(company.id):
        dispute_correction(correction, employee=worker, account="Salí a las 18:00, no a las 16:00.")

    correction.refresh_from_db()
    punch.refresh_from_db()
    assert correction.employee_agreed is False
    assert "18:00" in correction.employee_dissent
    assert correction.status == CorrectionStatus.AWAITING_EMPLOYEE  # still the company's move
    assert punch.is_active


@pytest.mark.django_db
def test_a_disagreement_needs_content(company, worker, boss):
    """An empty objection is not something a reader can weigh against the
    change it sits beside."""
    correction = proposal(company, worker, boss, a_punch(company, worker))

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        dispute_correction(correction, employee=worker, account="   ")

    assert caught.value.code == "account_required"


@pytest.mark.django_db
def test_disagreeing_informs_the_representatives(company, worker, boss):
    """Art. 4.b requires it."""
    with tenant_context(company.id):
        rep = User.objects.create_user(
            email="rlt@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Marta",
            is_worker_representative=True,
        )
        correction = proposal(company, worker, boss, a_punch(company, worker))
        dispute_correction(correction, employee=worker, account="No fue así.")

    correction.refresh_from_db()
    assert correction.representatives_notified_at is not None
    assert rep.first_name in correction.representatives_notice


@pytest.mark.django_db
def test_with_no_representatives_on_record_that_is_written_down(company, worker, boss):
    """Claiming to have informed nobody would be worse than admitting the gap,
    and the company needs to know the obligation is unmet."""
    correction = proposal(company, worker, boss, a_punch(company, worker))

    with tenant_context(company.id):
        dispute_correction(correction, employee=worker, account="No fue así.")

    correction.refresh_from_db()
    assert "4.b" in correction.representatives_notice


# ----------------------------------------- the company going ahead anyway


@pytest.mark.django_db
def test_the_company_may_apply_it_over_an_objection(company, worker, boss):
    """The sentence that decides the whole design: «en ausencia de acuerdo, la
    empresa reflejará en el registro la modificación y la persona trabajadora
    su discrepancia». Not a veto --- a contradiction."""
    punch = a_punch(company, worker)
    correction = proposal(company, worker, boss, punch)

    with tenant_context(company.id):
        dispute_correction(correction, employee=worker, account="Salí a las 18:00.")
        apply_without_agreement(correction, resolved_by=boss)

    correction.refresh_from_db()
    punch.refresh_from_db()
    assert correction.status == CorrectionStatus.DISPUTED
    assert correction.applied_without_agreement
    assert not punch.is_active
    # And their account survives the change being applied.
    assert "18:00" in correction.employee_dissent


@pytest.mark.django_db
def test_silence_is_not_agreement(company, worker, boss):
    """Past the window the company may go ahead, and the record says the person
    never answered rather than implying they consented."""
    punch = a_punch(company, worker)

    with freeze_time("2026-09-01 08:00:00"):
        correction = proposal(company, worker, boss, punch)

    # Language pinned: the sentence is translated, and leaving it to whichever
    # catalogue happens to be compiled makes the assertion below a coin toss.
    with (
        freeze_time("2026-09-20 08:00:00"),
        tenant_context(company.id),
        translation.override("en"),
    ):
        apply_without_agreement(correction, resolved_by=boss)

    correction.refresh_from_db()
    assert correction.status == CorrectionStatus.DISPUTED
    assert correction.employee_agreed is None  # never said yes
    # Written into the record rather than left blank: not answering is not
    # agreeing, and an entry that failed to say so would overstate the consent.
    assert correction.employee_dissent
    assert "without their agreement" in correction.employee_dissent.lower()


@pytest.mark.django_db
def test_the_company_cannot_jump_the_window(company, worker, boss):
    """Otherwise the authorisation the article asks for would be a formality
    somebody clicks past."""
    with freeze_time("2026-09-01 08:00:00"):
        correction = proposal(company, worker, boss, a_punch(company, worker))

        with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
            apply_without_agreement(correction, resolved_by=boss)

    assert caught.value.code == "still_within_the_window"


@pytest.mark.django_db
def test_the_window_is_the_companys_to_set(company, worker, boss):
    """The article sets no deadline, so this is a product decision and it has
    to be visible and changeable rather than hidden in a constant."""
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.correction_consent_days = 1
        rules.save(update_fields=["correction_consent_days"])

    with freeze_time("2026-09-01 08:00:00"):
        correction = proposal(company, worker, boss, a_punch(company, worker))

    with freeze_time("2026-09-03 08:00:00"), tenant_context(company.id):
        apply_without_agreement(correction, resolved_by=boss)

    correction.refresh_from_db()
    assert correction.status == CorrectionStatus.DISPUTED


# ------------------------------------------------- it reaches the report


@pytest.mark.django_db
def test_an_imposed_change_is_visible_in_the_report(company, worker, boss):
    """A reader has to be able to tell a correction both parties accepted from
    one imposed over an objection. Hiding that would be hiding the very
    disagreement the article exists to preserve."""
    from apps.reports.services import build_report

    punch = a_punch(company, worker)
    correction = proposal(company, worker, boss, punch)

    with tenant_context(company.id):
        dispute_correction(correction, employee=worker, account="Salí a las 18:00.")
        apply_without_agreement(correction, resolved_by=boss)

        # The correction concerns two hours ago, so the window is today.
        today = timezone.localdate()
        report = build_report(employee=worker, company=company, date_from=today, date_to=today)

    disputed = [r for r in report.rows if r.disputed]
    assert disputed, "the report says nothing about the disagreement"
    assert any("18:00" in note for r in disputed for note in r.dissent)
