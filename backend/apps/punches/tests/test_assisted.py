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


# --------------------------------------------- desconexión digital (art. 88)


@pytest.mark.django_db
def test_nothing_is_sent_at_night(company, worker):
    """Art. 88 LOPDGDD. Un turno que acaba a las 22:00 no puede convertirse en
    un aviso a las 23:30: a esa hora ya no recuerda nada, solo molesta."""
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "14:00", "end": "22:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),  # 14:00 Madrid
        )
        # 23:30 en Madrid: la jornada sigue abierta y tocaría avisar.
        de_noche = reminders_due(company, now=datetime(2026, 9, 1, 21, 30, tzinfo=UTC))

    assert de_noche == []


@pytest.mark.django_db
def test_the_same_case_inside_the_window_does_send(company, worker):
    """Y la comprobación contra un caso conocido: sin la ventana, ese mismo
    día sí avisa. Un vacío sin este contraste no prueba nada."""
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 6, 0, tzinfo=UTC),  # 08:00 Madrid
        )
        # 17:30 en Madrid: dentro de la ventana de aviso.
        de_tarde = reminders_due(company, now=datetime(2026, 9, 1, 15, 30, tzinfo=UTC))

    assert len(de_tarde) == 1
    assert de_tarde[0].kind == PunchReminder.Kind.CLOCK_OUT


@pytest.mark.django_db
def test_a_company_may_switch_the_window_off(company, worker):
    """Con las dos horas iguales no hay ventana: hay sectores que trabajan de
    noche y para ellos la noche es su jornada."""
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.quiet_from = rules.quiet_until
        rules.save()

        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "14:00", "end": "22:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        )
        de_noche = reminders_due(company, now=datetime(2026, 9, 1, 21, 30, tzinfo=UTC))

    assert len(de_noche) == 1


@pytest.mark.django_db
def test_la_ventana_de_silencio_va_en_la_hora_de_cada_persona(company, worker):
    """Alguien en Canarias tiene su noche una hora después.

    La ventana la fija la empresa ---de 21:00 a 07:00--- pero se mide en el
    reloj de quien la sufre. A las 21:30 de Madrid son las 20:30 en Las Palmas:
    ahí todavía no molesta, y callarse sería perder el aviso que sí sirve.

    Es el mismo tipo de fallo que ya apareció tres veces hoy: dar por buena una
    hora sin preguntar de quién es. Aquí estaba bien y no había nada que lo
    sostuviera.
    """
    from apps.users.models import Workplace

    with tenant_context(company.id):
        canarias = Workplace.objects.create(
            tenant=company, name="Delegación de Las Palmas", time_zone="Atlantic/Canary"
        )
        worker.workplace = canarias
        worker.save(update_fields=["workplace"])

        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "12:00", "end": "20:00"}],  # hora canaria
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 11, 0, tzinfo=UTC),  # 12:00 en Canarias
        )

        # 21:30 en Madrid = 20:30 en Las Palmas: fuera de su ventana de silencio.
        de_canarias = reminders_due(company, now=datetime(2026, 9, 1, 19, 30, tzinfo=UTC))

    assert len(de_canarias) == 1, "callado a una hora que para esa persona es la tarde"
    assert de_canarias[0].kind == PunchReminder.Kind.CLOCK_OUT


@pytest.mark.django_db
def test_y_una_hora_despues_si_calla_en_canarias(company, worker):
    """El otro lado, que es lo que convierte la anterior en una prueba.

    Sin esto, un cambio que ignorara la ventana entera pasaría la de arriba.
    """
    from apps.users.models import Workplace

    with tenant_context(company.id):
        canarias = Workplace.objects.create(
            tenant=company, name="Delegación de Las Palmas", time_zone="Atlantic/Canary"
        )
        worker.workplace = canarias
        worker.save(update_fields=["workplace"])

        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "12:00", "end": "20:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 11, 0, tzinfo=UTC),
        )

        # 22:30 en Madrid = 21:30 en Las Palmas: ya dentro de su ventana.
        tarde = reminders_due(company, now=datetime(2026, 9, 1, 20, 30, tzinfo=UTC))

    assert tarde == []


@pytest.mark.django_db
def test_la_jornada_de_noche_que_sigue_abierta_se_recuerda_por_la_mañana(company, worker):
    """El olvido más común, y el que peor encaja en «hoy».

    Quien entra a las 22:00 y se va a las 06:00 sin fichar la salida deja el día
    abierto, y a la mañana siguiente ese turno **pertenece a ayer**: mirar solo
    la fecha de hoy no lo encontraría nunca, y el aviso no saldría jamás
    precisamente para quien más lo necesita.

    A las 07:30 ---ya fuera de la ventana de silencio, que acaba a las 07:00---
    tiene que salir.
    """
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "22:00", "end": "06:00"}],  # cruza la medianoche
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),  # 22:00 Madrid
        )

        # 07:30 del día siguiente en Madrid.
        por_la_mañana = reminders_due(company, now=datetime(2026, 9, 2, 5, 30, tzinfo=UTC))

    assert len(por_la_mañana) == 1, "el turno de ayer no se miró"
    assert por_la_mañana[0].kind == PunchReminder.Kind.CLOCK_OUT
    assert por_la_mañana[0].day == date(2026, 9, 1), "el aviso va con el día del turno"


@pytest.mark.django_db
def test_de_madrugada_ese_mismo_turno_calla(company, worker):
    """El contraste. A las 06:30 sigue siendo de noche para el art. 88.

    Sin esta, un cambio que se saltara la ventana pasaría la de arriba, y el
    turno de noche recibiría avisos justo cuando se va a dormir --- que es la
    forma más segura de que los apague y no vuelva a verlos.
    """
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "22:00", "end": "06:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
        )

        # 06:30 en Madrid: el turno ya acabó, pero la ventana no.
        de_madrugada = reminders_due(company, now=datetime(2026, 9, 2, 4, 30, tzinfo=UTC))

    assert de_madrugada == []


@pytest.mark.django_db
def test_el_recordatorio_llega_en_el_idioma_de_cada_persona(company, worker):
    """Sale de un trabajo programado, y ahí no hay idioma activo.

    Sin fijarlo, el aviso se enviaría en el idioma por defecto del servidor: un
    «Remember to clock in» a alguien que trabaja en Jerez. Y al revés --- una
    empresa con gente de fuera --- cada cual en el suyo.

    Se comprueban los dos sentidos: una prueba que solo mirase el castellano
    pasaría igual si el idioma de la persona se ignorara por completo, porque el
    castellano es el de la empresa.
    """
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 6, 0, tzinfo=UTC),
        )

        # Primero en el idioma de la empresa, que es el castellano.
        mail.outbox.clear()
        send_reminders(company, now=datetime(2026, 9, 1, 15, 30, tzinfo=UTC))
        assert len(mail.outbox) == 1
        # Por una palabra que solo aparece en castellano. «Fichar» no vale: el
        # asunto de la salida es «Todavía no has fichado la salida», y buscar la
        # raíz exacta convierte una prueba de idioma en una de conjugación.
        assert "salida" in mail.outbox[0].subject.lower()

        # Y ahora alguien que prefiere el inglés. Se borra el rastro del aviso
        # anterior, que si no se manda una sola vez --- y eso ya está probado.
        PunchReminder.objects.all().delete()
        worker.locale = "en"
        worker.save(update_fields=["locale"])

        mail.outbox.clear()
        send_reminders(company, now=datetime(2026, 9, 1, 15, 30, tzinfo=UTC))
        assert len(mail.outbox) == 1
        assert "clocked out" in mail.outbox[0].subject.lower()
