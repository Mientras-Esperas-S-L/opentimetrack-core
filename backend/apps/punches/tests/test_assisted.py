"""Fichaje asistido: reconciliación, recordatorios y el seam de presencia.

El principio que todo esto defiende: asiste lo rutinario, saca la excepción, no
escondas nada. Un recordatorio empuja al fichaje real, nunca lo hace por ti, así
que no puede ocultar un retraso ni enterrar horas extra.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from django.core import mail

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchReminder, PunchTrigger, PunchType
from apps.punches.reminders import reminders_due, send_reminders
from apps.punches.services import register_punch
from apps.shifts.models import Shift
from apps.shifts.services import day_reconciliation
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

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


def morning_shift(company, worker, day):
    with tenant_context(company.id):
        return Shift.objects.create(
            tenant=company, employee=worker, day=day, segments=[{"start": "09:00", "end": "17:00"}]
        )


def punch_at(company, worker, when, kind):
    """A raw punch at a fixed instant, for building a day in the past."""
    with tenant_context(company.id):
        p = Punch(tenant=company, employee=worker, punch_type=kind, timestamp=when)
        p.save()
        return p


# --------------------------------------------------------------- reconciliación


@pytest.mark.django_db
def test_a_day_with_no_shift_is_no_shift(company, worker):
    with tenant_context(company.id):
        recon = day_reconciliation(employee=worker, company=company, day=date(2026, 9, 1))
    assert recon.status == "NO_SHIFT"


@pytest.mark.django_db
def test_a_shift_with_nothing_clocked_is_missing(company, worker):
    morning_shift(company, worker, date(2026, 9, 1))
    with tenant_context(company.id):
        recon = day_reconciliation(employee=worker, company=company, day=date(2026, 9, 1))
    assert recon.status == "MISSING"
    assert recon.expected_minutes == 8 * 60


@pytest.mark.django_db
def test_within_the_entry_margin_is_on_time(company, worker):
    """Una ventana de entrada hace que un 9:20 sea variación, no incidencia."""
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.entry_tolerance_minutes = 30
        rules.save(update_fields=["entry_tolerance_minutes"])
    morning_shift(company, worker, date(2026, 9, 1))
    # 09:20 Madrid = 07:20 UTC.
    punch_at(company, worker, datetime(2026, 9, 1, 7, 20, tzinfo=UTC), PunchType.IN)
    punch_at(company, worker, datetime(2026, 9, 1, 15, 0, tzinfo=UTC), PunchType.OUT)

    with tenant_context(company.id):
        recon = day_reconciliation(employee=worker, company=company, day=date(2026, 9, 1))
    assert recon.late_minutes == 0
    assert recon.status == "OK"


@pytest.mark.django_db
def test_past_the_margin_is_late(company, worker):
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.entry_tolerance_minutes = 15
        rules.save(update_fields=["entry_tolerance_minutes"])
    morning_shift(company, worker, date(2026, 9, 1))
    # 09:40 Madrid = 07:40 UTC, 40 min tarde, margen 15.
    punch_at(company, worker, datetime(2026, 9, 1, 7, 40, tzinfo=UTC), PunchType.IN)
    punch_at(company, worker, datetime(2026, 9, 1, 15, 0, tzinfo=UTC), PunchType.OUT)

    with tenant_context(company.id):
        recon = day_reconciliation(employee=worker, company=company, day=date(2026, 9, 1))
    assert recon.late_minutes == 40
    assert recon.status == "LATE"


@pytest.mark.django_db
def test_overtime_is_surfaced_not_swallowed(company, worker):
    """Lo más importante: trabajar de más SIEMPRE sale. Es lo contrario del
    fichaje de horario, que lo esconde."""
    morning_shift(company, worker, date(2026, 9, 1))  # 8 h previstas
    # 09:00 a 19:00 Madrid = 07:00 a 17:00 UTC: 10 h, 2 de más.
    punch_at(company, worker, datetime(2026, 9, 1, 7, 0, tzinfo=UTC), PunchType.IN)
    punch_at(company, worker, datetime(2026, 9, 1, 17, 0, tzinfo=UTC), PunchType.OUT)

    with tenant_context(company.id):
        recon = day_reconciliation(employee=worker, company=company, day=date(2026, 9, 1))
    assert recon.overtime_minutes == 120
    assert recon.status == "OVERTIME"


@pytest.mark.django_db
def test_the_exit_margin_does_not_count_as_overtime(company, worker):
    """Cinco minutos de más al salir es el redondeo de una jornada normal, no
    una hora extra."""
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.exit_tolerance_minutes = 15
        rules.save(update_fields=["exit_tolerance_minutes"])
    morning_shift(company, worker, date(2026, 9, 1))
    punch_at(company, worker, datetime(2026, 9, 1, 7, 0, tzinfo=UTC), PunchType.IN)
    # 10 min de más.
    punch_at(company, worker, datetime(2026, 9, 1, 15, 10, tzinfo=UTC), PunchType.OUT)

    with tenant_context(company.id):
        recon = day_reconciliation(employee=worker, company=company, day=date(2026, 9, 1))
    assert recon.overtime_minutes == 0
    assert recon.status == "OK"


# ----------------------------------------------------------------- el seam


@pytest.mark.django_db
def test_a_punch_carries_its_trigger_and_evidence(company, worker):
    """Presencia real: un fichaje registra la prueba de qué lo disparó."""
    with tenant_context(company.id):
        punch = register_punch(
            employee=worker,
            company=company,
            trigger=PunchTrigger.GEOFENCE,
            evidence={"lat": 36.68, "lng": -6.13, "accuracy": 12},
        )
    assert punch.trigger == "GEOFENCE"
    assert punch.evidence["lat"] == 36.68


@pytest.mark.django_db
def test_the_evidence_is_not_in_the_integrity_hash(company, worker):
    """Va con la IP y el dispositivo: metadata de captura, purgable, y no parte
    del hecho de jornada. Meterla en el hash la haría imposible de borrar."""
    with tenant_context(company.id):
        punch = register_punch(
            employee=worker,
            company=company,
            trigger=PunchTrigger.GEOFENCE,
            evidence={"lat": 36.68, "lng": -6.13},
        )
        before = punch.hash_integrity
        punch.evidence = {}
        punch.trigger = PunchTrigger.MANUAL
        assert punch.compute_hash() == before  # cambiar la evidencia no rompe el sello


@pytest.mark.django_db
def test_purge_clears_the_evidence(company, worker):
    from django.core.management import call_command

    with tenant_context(company.id):
        company.security_metadata_retention_days = 0
        company.save(update_fields=["security_metadata_retention_days"])
        punch = register_punch(
            employee=worker,
            company=company,
            trigger=PunchTrigger.GEOFENCE,
            evidence={"lat": 36.68},
            ip_address="1.2.3.4",
        )

    call_command("purge_security_metadata")

    with tenant_context(company.id):
        punch.refresh_from_db()
    assert punch.evidence == {}
    assert punch.ip_address is None


# -------------------------------------------------------------- recordatorios


@pytest.mark.django_db
def test_missing_entry_is_reminded_during_the_shift(company, worker):
    morning_shift(company, worker, date(2026, 9, 1))
    # 10:00 Madrid, turno 9-17, no ha fichado.
    now = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    with tenant_context(company.id):
        due = reminders_due(company, now)
    assert [(d.kind) for d in due] == [PunchReminder.Kind.CLOCK_IN]


@pytest.mark.django_db
def test_no_reminder_before_the_shift_starts(company, worker):
    morning_shift(company, worker, date(2026, 9, 1))
    # 08:00 Madrid = 06:00 UTC, aún no empieza.
    now = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)
    with tenant_context(company.id):
        assert reminders_due(company, now) == []


@pytest.mark.django_db
def test_no_reminder_once_they_clocked_in(company, worker):
    morning_shift(company, worker, date(2026, 9, 1))
    punch_at(company, worker, datetime(2026, 9, 1, 7, 5, tzinfo=UTC), PunchType.IN)
    now = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    with tenant_context(company.id):
        due = reminders_due(company, now)
    assert PunchReminder.Kind.CLOCK_IN not in [d.kind for d in due]


@pytest.mark.django_db
def test_open_day_is_reminded_after_the_shift_ends(company, worker):
    morning_shift(company, worker, date(2026, 9, 1))
    punch_at(company, worker, datetime(2026, 9, 1, 7, 0, tzinfo=UTC), PunchType.IN)
    # 18:00 Madrid = 16:00 UTC, turno acabó a las 17, sigue abierto.
    now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
    with tenant_context(company.id):
        due = reminders_due(company, now)
    assert PunchReminder.Kind.CLOCK_OUT in [d.kind for d in due]


@pytest.mark.django_db
def test_a_reminder_is_sent_once(company, worker):
    morning_shift(company, worker, date(2026, 9, 1))
    now = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    with tenant_context(company.id):
        first = send_reminders(company, now)
        second = send_reminders(company, now)
    assert first == 1
    assert second == 0
    assert len(mail.outbox) == 1
    assert "Ana" in mail.outbox[0].body


@pytest.mark.django_db
def test_opting_out_stops_them(company, worker):
    with tenant_context(company.id):
        worker.wants_punch_reminders = False
        worker.save(update_fields=["wants_punch_reminders"])
    morning_shift(company, worker, date(2026, 9, 1))
    now = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    with tenant_context(company.id):
        assert reminders_due(company, now) == []


# ------------------------------------------------------ opt-in por autoservicio


@pytest.mark.django_db
def test_a_person_can_turn_off_their_own_reminders(company, worker):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=worker)
    r = client.patch("/api/auth/me/", {"wants_punch_reminders": False}, format="json")

    assert r.status_code == 200
    with tenant_context(company.id):
        worker.refresh_from_db()
    assert worker.wants_punch_reminders is False


@pytest.mark.django_db
def test_the_preferences_door_ignores_everything_else(company, worker):
    """Rol, contrato, activo: de otro. Por esta puerta solo pasan las
    preferencias propias."""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=worker)
    r = client.patch("/api/auth/me/", {"role": "ADMIN", "is_active": False}, format="json")

    assert r.status_code == 200
    with tenant_context(company.id):
        worker.refresh_from_db()
    assert worker.role == "EMPLOYEE"
    assert worker.is_active is True
