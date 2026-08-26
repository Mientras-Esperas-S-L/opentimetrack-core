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


# ------------------------------------------------------- notice to the person

# Recommended by the legal review of 11/08/2026: a correction does not depend on
# the person agreeing, but it cannot happen without them finding out.


@pytest.mark.django_db
def test_the_person_is_told_when_their_record_changes(
    company, employee, manager, django_capture_on_commit_callbacks
):
    """The notice goes out on commit, so the person never hears about a change
    that then rolls back. That is why the test has to capture the callbacks."""
    from django.core import mail

    with freeze_time("2026-08-10 06:00:00"):
        original = register_punch(employee=employee, company=company)

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.MODIFY,
        target=original,
        reason="El reloj iba adelantado.",
        proposed_timestamp=original.timestamp + timedelta(minutes=20),
    )
    with django_capture_on_commit_callbacks(execute=True):
        approve_correction(correction, resolved_by=manager)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [employee.email]
    assert "El reloj iba adelantado." in message.body  # the reason travels
    assert "Luisa Ferrer" in message.body  # and who decided


@pytest.mark.django_db
def test_nobody_is_told_about_their_own_approved_request(
    company, employee, django_capture_on_commit_callbacks
):
    """They already know: they asked for it."""
    from django.core import mail

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.ADD,
        reason="Olvidé fichar la salida.",
        proposed_type="OUT",
        proposed_timestamp=timezone.now() - timedelta(hours=1),
    )
    with django_capture_on_commit_callbacks(execute=True):
        approve_correction(correction, resolved_by=employee)

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_a_failed_notice_does_not_undo_the_correction(
    company, employee, manager, monkeypatch, django_capture_on_commit_callbacks
):
    """The record is what matters; the email is a courtesy that must not break it."""

    def explode(*args, **kwargs):
        raise RuntimeError("el servidor de correo está caído")

    monkeypatch.setattr("django.core.mail.send_mail", explode)

    with freeze_time("2026-08-10 06:00:00"):
        original = register_punch(employee=employee, company=company)

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.VOID,
        target=original,
        reason="Fiché por error.",
    )
    with django_capture_on_commit_callbacks(execute=True):
        approve_correction(correction, resolved_by=manager)

    correction.refresh_from_db()
    original.refresh_from_db()
    assert correction.status == CorrectionStatus.APPROVED
    assert not original.is_active


@pytest.mark.django_db
def test_the_person_can_see_which_punch_is_being_changed(company, employee, manager):
    """Consentir un cambio exige saber cuál es el cambio (art. 4.b).

    Una propuesta de **anular** no lleva hora nueva ---no hay ninguna--- así que
    la pantalla de quien tenía que autorizarla decía «Anular un fichaje» y
    ponía dos botones debajo. Se le pedía consentir sin decirle qué. Y en un
    cambio de hora enseñaba la nueva y nunca la que sustituye, que es la mitad
    de la información.
    """
    from rest_framework.test import APIClient

    with tenant_context(company.id):
        punch = register_punch(employee=employee, company=company)
        correction = request_correction(
            employee=employee,
            company=company,
            requested_by=manager,
            kind=CorrectionKind.VOID,
            target=punch,
            reason="Se fichó desde el terminal de otra cuadrilla.",
        )

    client = APIClient()
    client.force_authenticate(user=employee)
    body = client.get(f"/api/corrections/{correction.id}/").json()

    assert body["target_detail"] is not None
    assert body["target_detail"]["id"] == str(punch.id)
    assert body["target_detail"]["timestamp"]
    assert body["target_detail"]["punch_type"] == punch.punch_type
    # Y sigue sin haber hora propuesta, que es lo correcto en una anulación.
    assert body["proposed_timestamp"] is None


# ------------------------------------------- what the corrected event must carry


@pytest.mark.django_db
def test_correcting_the_hour_keeps_what_the_event_was(company, employee, manager):
    """Art. 4.b is the only legitimate way to touch the record. It must not corrupt it.

    The substitute used to be built from scratch with six fields, so everything
    art. 3 asks the record to carry --- whether the span was work or a break,
    whether the hours were ordinary or overtime, how the overtime is settled ---
    was silently reset. Correcting the end of a break turned it into a work
    span: the day then read as one endless shift with a break open since the
    morning, and 0 h worked.
    """
    from apps.punches.models import HoursNature, OvertimeSettlement, PunchInterval, WorkMode

    with freeze_time("2026-08-12 06:00:00"):
        register_punch(employee=employee, company=company)
    with freeze_time("2026-08-12 12:00:00"):
        register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-12 12:30:00"):
        vuelta = register_punch(
            employee=employee,
            company=company,
            interval=PunchInterval.BREAK,
            work_mode=WorkMode.REMOTE,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.REST,
        )
    with freeze_time("2026-08-12 16:00:00"):
        register_punch(employee=employee, company=company)

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.MODIFY,
        reason="Volví a las 13:00, no a las 12:30.",
        target=vuelta,
        proposed_type=vuelta.punch_type,
        proposed_timestamp=vuelta.timestamp + timedelta(minutes=30),
    )
    nuevo = approve_correction(correction, resolved_by=manager)

    assert nuevo.interval == PunchInterval.BREAK
    assert nuevo.work_mode == WorkMode.REMOTE
    assert nuevo.hours_nature == HoursNature.OVERTIME
    assert nuevo.overtime_settlement == OvertimeSettlement.REST


@pytest.mark.django_db
def test_a_corrected_day_still_adds_up(company, employee, manager):
    """The symptom the lost fields produced: a nine-hour day reading as zero."""
    from datetime import date

    from apps.punches.models import PunchInterval

    with freeze_time("2026-08-12 06:00:00"):
        register_punch(employee=employee, company=company)
    with freeze_time("2026-08-12 12:00:00"):
        register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-12 12:30:00"):
        vuelta = register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-12 16:00:00"):
        register_punch(employee=employee, company=company)

    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=employee,
        kind=CorrectionKind.MODIFY,
        reason="Volví a las 13:00.",
        target=vuelta,
        proposed_type=vuelta.punch_type,
        proposed_timestamp=vuelta.timestamp + timedelta(minutes=30),
    )
    approve_correction(correction, resolved_by=manager)

    day = build_day_status(employee=employee, company=company, day=date(2026, 8, 12))
    assert day.state == "OFF"
    assert day.break_seconds == 3600
    assert day.worked_seconds == 9 * 3600


@pytest.mark.django_db
def test_the_proposed_type_has_to_be_an_entry_or_an_exit(company, employee):
    """`punch_type` is varchar(3) with no CHECK, and `save()` skips `full_clean()`.

    Lowercase "in" used to sail through the whole flow: 201 on the request, 200
    on the approval, a confirmation email to both parties --- and a day still
    reading zero hours, because no reader recognises that value. Worse, the next
    real punch is then inferred as an exit and chains a second wrong event.
    """
    with pytest.raises(BusinessRuleError) as caught:
        request_correction(
            employee=employee,
            company=company,
            requested_by=employee,
            kind=CorrectionKind.ADD,
            reason="Olvidé fichar la entrada.",
            proposed_type="in",
            proposed_timestamp=timezone.now() - timedelta(hours=2),
        )

    assert caught.value.code == "unknown_type"


@pytest.mark.django_db
def test_the_api_refuses_an_unknown_type_with_a_readable_error(company, employee, manager):
    """And it comes back as a 400, not as a 500 a connector cannot react to."""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=employee)
    response = client.post(
        "/api/corrections/",
        {
            "kind": CorrectionKind.ADD,
            "proposed_type": "in",
            "proposed_timestamp": (timezone.now() - timedelta(hours=2)).isoformat(),
            "reason": "Olvidé fichar la entrada.",
        },
        format="json",
    )

    assert response.status_code == 400
    assert Punch.objects.filter(employee=employee).count() == 0
