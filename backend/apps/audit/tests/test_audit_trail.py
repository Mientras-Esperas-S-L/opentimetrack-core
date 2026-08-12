"""The audit trail: that it cannot be altered, and that it records the right things.

Two halves. The first is the guarantee ADR-0003 promised and the code did not
provide: append-only **in the database**, so it survives a bug, a shell, or an
administrator who would rather the entry were not there. The second is that the
entries that matter actually get written --- above all the one that was missing
entirely, reading somebody else's record.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import ProgrammingError, connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence
from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def make(company, email, role=Role.EMPLOYEE):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email, password=PASSWORD, tenant=company, first_name=email[:3], role=role
        )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def an_entry(company, **extra):
    return AuditLog.objects.create(
        tenant=company, action=AuditAction.RECORD_VIEWED, actor_label="alguien", **extra
    )


# --------------------------------------------------------------- append-only


@pytest.mark.django_db
def test_the_model_refuses_to_be_modified(company):
    entry = an_entry(company)
    entry.note = "manipulado"

    with pytest.raises(RuntimeError, match="append-only"):
        entry.save()


@pytest.mark.django_db
def test_the_model_refuses_to_be_deleted(company):
    entry = an_entry(company)

    with pytest.raises(RuntimeError, match="append-only"):
        entry.delete()


@pytest.mark.django_db
def test_the_database_refuses_an_update_too(company):
    """The guarantee that counts. Overriding save() stops honest mistakes and
    nothing else: a bug, a management command or a psql prompt goes straight
    past Python."""
    entry = an_entry(company)

    # Its own savepoint: the exception aborts the transaction, and without one
    # the assertions afterwards could not run.
    with (
        pytest.raises(ProgrammingError) as caught,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("UPDATE audit_auditlog SET note = 'manipulado' WHERE id = %s", [entry.id])
    assert "append-only" in str(caught.value)

    entry.refresh_from_db()
    assert entry.note == ""


@pytest.mark.django_db
def test_the_database_refuses_a_delete_too(company):
    entry = an_entry(company)

    with (
        pytest.raises(ProgrammingError) as caught,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("DELETE FROM audit_auditlog WHERE id = %s", [entry.id])
    assert "append-only" in str(caught.value)

    assert AuditLog.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_the_database_refuses_a_truncate(company):
    """The one-word way to empty the table. Row triggers do not see it, which
    is why there is a statement-level one.

    Nothing is inserted first on purpose. With a pending insert in the same
    transaction PostgreSQL refuses the TRUNCATE for its own reason ("pending
    trigger events"), and the test would pass without the trigger existing at
    all --- proving nothing.
    """
    with (
        pytest.raises(ProgrammingError) as caught,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("TRUNCATE audit_auditlog")

    assert "append-only" in str(caught.value)


@pytest.mark.django_db
def test_queryset_updates_and_deletes_are_stopped_by_the_database(company):
    """`.update()` and `.delete()` on a queryset never call the model methods."""
    an_entry(company)

    for operation in (
        lambda: AuditLog.objects.filter(tenant=company).update(note="x"),
        lambda: AuditLog.objects.filter(tenant=company).delete(),
    ):
        # ProgrammingError is what psycopg raises for a RAISE EXCEPTION in
        # plpgsql. Named rather than a bare Exception, so the test cannot pass
        # because of an unrelated failure.
        with pytest.raises(ProgrammingError, match="append-only"), transaction.atomic():
            operation()

    assert AuditLog.objects.filter(tenant=company).count() == 1


# ------------------------------------------------- reading somebody else's record


@pytest.mark.django_db
def test_reading_a_colleagues_history_leaves_a_trace(company, django_capture_on_commit_callbacks):
    """The gap the whole thing existed to close: a manager could read anyone's
    record and nothing recorded it."""
    worker = make(company, "worker@example.com")
    boss = make(company, "boss@example.com", Role.MANAGER)

    with django_capture_on_commit_callbacks(execute=True):
        client_for(boss).get("/api/punches/", {"employee": str(worker.id)})

    entry = AuditLog.objects.filter(action=AuditAction.RECORD_VIEWED).first()
    assert entry is not None
    assert entry.actor == boss
    assert entry.target_id == worker.id
    assert entry.actor_label


@pytest.mark.django_db
def test_reading_your_own_does_not(company, django_capture_on_commit_callbacks):
    """It is a right. Logging it would bury the entries that matter."""
    worker = make(company, "worker@example.com")

    with django_capture_on_commit_callbacks(execute=True):
        client_for(worker).get("/api/punches/", {"employee": str(worker.id)})

    assert not AuditLog.objects.filter(action=AuditAction.RECORD_VIEWED).exists()


@pytest.mark.django_db
def test_downloading_a_colleagues_document_leaves_a_trace(
    django_capture_on_commit_callbacks, company
):
    from django.core.files.uploadedfile import SimpleUploadedFile

    worker = make(company, "worker@example.com")
    boss = make(company, "boss@example.com", Role.MANAGER)
    with tenant_context(company.id):
        absence = request_absence(
            employee=worker,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            justification=SimpleUploadedFile("c.pdf", b"%PDF-1.4", "application/pdf"),
        )

    with django_capture_on_commit_callbacks(execute=True):
        client_for(boss).get(f"/api/absences/{absence.id}/justification/")

    assert AuditLog.objects.filter(action=AuditAction.DOCUMENT_DOWNLOADED).count() == 1


@pytest.mark.django_db
def test_exporting_a_colleagues_report_leaves_a_trace(company, django_capture_on_commit_callbacks):
    worker = make(company, "worker@example.com")
    boss = make(company, "boss@example.com", Role.MANAGER)
    with tenant_context(company.id):
        register_punch(employee=worker, company=company)

    today = timezone.localdate()
    with django_capture_on_commit_callbacks(execute=True):
        client_for(boss).get(
            "/api/reports/working-time/",
            {"employee": str(worker.id), "date_from": str(today), "date_to": str(today)},
        )

    entry = AuditLog.objects.filter(action=AuditAction.REPORT_EXPORTED).first()
    assert entry is not None
    assert entry.target_id == worker.id
    assert "hash" in entry.note


# ----------------------------------------------------------- changes of power


@pytest.mark.django_db
def test_a_role_change_is_its_own_action(django_capture_on_commit_callbacks, company):
    """It decides who can read other people's records, so it has to be findable
    without trawling through every ordinary edit."""
    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")

    with django_capture_on_commit_callbacks(execute=True):
        client_for(admin).patch(f"/api/employees/{worker.id}/", {"role": "MANAGER"}, format="json")

    entry = AuditLog.objects.filter(action=AuditAction.ROLE_CHANGED).first()
    assert entry is not None
    assert entry.changes["role"] == ["EMPLOYEE", "MANAGER"]


@pytest.mark.django_db
def test_deactivating_somebody_is_recorded(django_capture_on_commit_callbacks, company):
    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")

    with django_capture_on_commit_callbacks(execute=True):
        client_for(admin).delete(f"/api/employees/{worker.id}/")

    assert AuditLog.objects.filter(action=AuditAction.PERSON_DEACTIVATED).count() == 1


@pytest.mark.django_db
def test_a_settings_change_records_only_what_moved(django_capture_on_commit_callbacks, company):
    """A diff of everything would bury the one field that changed."""
    admin = make(company, "admin@example.com", Role.ADMIN)

    with django_capture_on_commit_callbacks(execute=True):
        client_for(admin).patch("/api/company/", {"annual_leave_days": 26}, format="json")

    entry = AuditLog.objects.filter(action=AuditAction.SETTINGS_CHANGED).first()
    assert entry is not None
    assert entry.changes == {"annual_leave_days": [22, 26]}


@pytest.mark.django_db
def test_approving_leave_is_recorded_with_the_dates(django_capture_on_commit_callbacks, company):
    worker = make(company, "worker@example.com")
    boss = make(company, "boss@example.com", Role.MANAGER)
    with tenant_context(company.id):
        absence = request_absence(
            employee=worker,
            company=company,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
        )

    with django_capture_on_commit_callbacks(execute=True):
        client_for(boss).post(f"/api/absences/{absence.id}/approve/")

    entry = AuditLog.objects.filter(action=AuditAction.ABSENCE_APPROVED).first()
    assert entry is not None
    assert entry.changes["from"] == "2026-09-01"


# --------------------------------------------------------------- who can read


@pytest.mark.django_db
def test_a_worker_sees_the_entries_about_themselves(company):
    """If the point is knowing who read your record, you have to be able to look."""
    worker = make(company, "worker@example.com")
    boss = make(company, "boss@example.com", Role.MANAGER)
    an_entry(company, actor=boss, target_id=worker.id, target_label="worker")
    an_entry(company, actor=boss, target_id=boss.id, target_label="somebody else")

    rows = client_for(worker).get("/api/audit/").json()["results"]

    assert len(rows) == 1
    assert rows[0]["target_id"] == str(worker.id)


@pytest.mark.django_db
def test_a_manager_does_not_get_the_company_wide_view(company):
    """They are who the trail most often has something to say about. Letting
    the watched choose what the watching shows empties it of meaning."""
    boss = make(company, "boss@example.com", Role.MANAGER)
    other = make(company, "other@example.com")
    an_entry(company, actor=other, target_id=other.id)

    rows = client_for(boss).get("/api/audit/").json()["results"]

    assert rows == []


@pytest.mark.django_db
def test_an_administrator_sees_the_company(company):
    admin = make(company, "admin@example.com", Role.ADMIN)
    other = make(company, "other@example.com")
    an_entry(company, actor=other, target_id=other.id)

    rows = client_for(admin).get("/api/audit/").json()["results"]

    assert len(rows) == 1


@pytest.mark.django_db
def test_another_companys_trail_is_not_visible(company):
    """This model is not a TenantOwnedModel, so nothing scopes it on its own.
    Worth its own test: forgetting the filter would show one company another's
    trail, which is the worst thing this table could do."""
    admin = make(company, "admin@example.com", Role.ADMIN)
    elsewhere = Tenant.objects.create(name="Otra SL", tax_id="B22222222", time_zone="Europe/Madrid")
    an_entry(elsewhere, target_label="asunto ajeno")

    rows = client_for(admin).get("/api/audit/").json()["results"]

    assert rows == []


@pytest.mark.django_db
def test_the_api_offers_no_way_to_write(company):
    """ADR-0003: no PUT, PATCH or DELETE. Structural, not a rule to remember."""
    admin = make(company, "admin@example.com", Role.ADMIN)
    entry = an_entry(company)
    client = client_for(admin)

    assert client.post("/api/audit/", {}, format="json").status_code == 405
    assert client.patch(f"/api/audit/{entry.id}/", {}, format="json").status_code == 405
    assert client.delete(f"/api/audit/{entry.id}/").status_code == 405


# ------------------------------------------------------- it must never break a request


@pytest.mark.django_db
def test_a_failure_writing_the_trail_does_not_break_the_action(
    django_capture_on_commit_callbacks, company, monkeypatch
):
    """The trail is evidence of what happened; it must not become a reason for
    things not to happen. A full audit table must never stop somebody clocking
    in."""
    from apps.audit import services

    def explode(*args, **kwargs):
        raise RuntimeError("la tabla de auditoría está llena")

    monkeypatch.setattr(services.AuditLog, "__init__", explode)

    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")

    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(admin).delete(f"/api/employees/{worker.id}/")

    assert response.status_code == 204
    worker.refresh_from_db()
    assert not worker.is_active


@pytest.mark.django_db
def test_an_entry_is_not_written_if_the_action_rolls_back(
    company, django_capture_on_commit_callbacks
):
    """An entry describing something that then rolled back would be a lie, and
    a lie in the audit trail is worse than a gap."""
    admin = make(company, "admin@example.com", Role.ADMIN)

    before = AuditLog.objects.count()
    # Refused: the only administrator cannot demote themselves.
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(admin).patch(
            f"/api/employees/{admin.id}/", {"role": "EMPLOYEE"}, format="json"
        )

    assert response.status_code == 409
    assert AuditLog.objects.count() == before


# ------------------------------------------- the entries added after the sweep


@pytest.mark.django_db
def test_there_is_no_way_to_void_an_event_without_a_reason(company):
    """The direct void endpoint is gone. It struck an event with no reason and
    no notice, while a correction of the same effect requires both --- and two
    doors to the same act, one without the guarantees, empties ADR-0014."""
    from apps.punches.services import register_punch

    admin = make(company, "admin@example.com", Role.ADMIN)
    worker = make(company, "worker@example.com")
    with tenant_context(company.id):
        punch = register_punch(employee=worker, company=company)

    response = client_for(admin).patch(
        f"/api/punches/{punch.id}/void/", {"reason": "duplicado"}, format="json"
    )

    assert response.status_code == 404
    punch.refresh_from_db()
    assert punch.is_active


@pytest.mark.django_db
def test_voiding_through_a_correction_needs_both_sides(company, django_capture_on_commit_callbacks):
    """The only way in, and art. 4.b decides how far it gets on its own.

    Proposed by the company, so one authorisation is missing: nothing is
    applied until the person answers.
    """
    from apps.punches.services import register_punch

    boss = make(company, "boss@example.com", Role.MANAGER)
    worker = make(company, "worker@example.com")
    with tenant_context(company.id):
        punch = register_punch(employee=worker, company=company)

    with django_capture_on_commit_callbacks(execute=True):
        created = (
            client_for(boss)
            .post(
                "/api/corrections/",
                {
                    "employee": str(worker.id),
                    "kind": "VOID",
                    "target": str(punch.id),
                    "reason": "Fichaje duplicado por doble pulsación.",
                },
                format="json",
            )
            .json()
        )

    assert created["status"] == "AWAITING_EMPLOYEE"
    punch.refresh_from_db()
    assert punch.is_active, "nothing may be applied before the person answers"

    with django_capture_on_commit_callbacks(execute=True):
        accepted = client_for(worker).post(f"/api/corrections/{created['id']}/accept/")

    assert accepted.status_code == 200
    punch.refresh_from_db()
    assert not punch.is_active
    assert AuditLog.objects.filter(action=AuditAction.CORRECTION_APPROVED).exists()


@pytest.mark.django_db
def test_changing_the_working_time_rules_is_recorded(company, django_capture_on_commit_callbacks):
    """They decide what the roster is measured against, so changing them
    changes what "compliant" means."""
    admin = make(company, "admin@example.com", Role.ADMIN)

    with django_capture_on_commit_callbacks(execute=True):
        client_for(admin).patch("/api/working-time-rules/", {"daily_rest_hours": 8}, format="json")

    entry = AuditLog.objects.filter(action=AuditAction.RULES_CHANGED).first()
    assert entry is not None
    assert entry.changes["daily_rest_hours"] == [12, 8]


@pytest.mark.django_db
def test_purging_metadata_leaves_a_trace(company, django_capture_on_commit_callbacks):
    """Deleting data is recorded too. Otherwise the only evidence that
    something was removed is that it is no longer there."""
    from datetime import timedelta
    from io import StringIO

    from django.core.management import call_command
    from django.utils import timezone

    from apps.punches.models import Punch

    worker = make(company, "worker@example.com")
    with tenant_context(company.id):
        punch = Punch(
            tenant=company,
            employee=worker,
            punch_type="IN",
            timestamp=timezone.now() - timedelta(days=400),
            ip_address="10.0.0.9",
        )
        punch.save()

    with django_capture_on_commit_callbacks(execute=True):
        call_command("purge_security_metadata", stdout=StringIO())

    entry = AuditLog.objects.filter(action=AuditAction.METADATA_PURGED).first()
    assert entry is not None
    assert entry.changes["purged"] == 1
    assert entry.actor is None  # cron, no person
