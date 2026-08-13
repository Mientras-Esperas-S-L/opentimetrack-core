"""Security metadata and its own retention window.

Two things are being pinned down here, and they are the same thing seen from
two sides:

- The IP address is kept for security, not to prove working time, so it must be
  possible to delete it while the record it was attached to stays valid.
- Deleting it must not break the hash --- and the way to get that is a versioned
  payload, never a rewritten hash. Rewriting one is indistinguishable from
  tampering with the record.

Recommended by the external legal review of 11/08/2026.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.common.models import tenant_context
from apps.punches.models import CURRENT_HASH_VERSION, Punch, PunchSource
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import User


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd",
        tax_id="B11111111",
        time_zone="Europe/Madrid",
        security_metadata_retention_days=365,
    )


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="pau@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Pau",
            last_name="Serra",
        )


def _punch(company, employee, *, when, ip="10.0.0.7", version=CURRENT_HASH_VERSION):
    """Writes an event as it would have been written on that date.

    `version=1` reproduces one stored before the payload changed, hash and all,
    which is the only honest way to test that old events still verify.
    """
    punch = Punch(
        tenant=company,
        employee=employee,
        punch_type="IN",
        timestamp=when,
        source=PunchSource.WEB,
        ip_address=ip,
        device_id="pixel-8",
        user_agent="Mozilla/5.0",
    )
    punch.hash_version = version
    punch.hash_integrity = punch.compute_hash()
    punch.save()
    return punch


# ------------------------------------------------- the IP is out of the payload


@pytest.mark.django_db
def test_removing_the_ip_leaves_the_record_verifiable(company, employee):
    """The whole point: minimisation must not cost the record its integrity."""
    punch = register_punch(employee=employee, company=company, ip_address="10.0.0.7")
    assert punch.verify_hash()

    punch.ip_address = None
    punch.device_id = ""
    punch.user_agent = ""
    punch.save(update_fields=["ip_address", "device_id", "user_agent"])
    punch.refresh_from_db()

    assert punch.verify_hash()
    assert punch.timestamp is not None  # and the event itself is untouched


@pytest.mark.django_db
def test_the_hash_still_pins_down_who_produced_the_event(company, employee):
    """What replaced the IP: the attribution a delegated punch turns on."""
    punch = register_punch(employee=employee, company=company)
    assert punch.verify_hash()

    punch.source = PunchSource.DELEGATED
    assert not punch.verify_hash()  # changing the origin is detectable

    punch.refresh_from_db()
    punch.source_application = "greencity"
    assert not punch.verify_hash()


@pytest.mark.django_db
def test_new_events_carry_the_current_version(company, employee):
    punch = register_punch(employee=employee, company=company)
    assert punch.hash_version == CURRENT_HASH_VERSION


# ------------------------------------------- old events keep verifying as they were


@pytest.mark.django_db
def test_an_event_stored_under_the_old_payload_still_verifies(company, employee):
    """Its hash was never rewritten, and it is still checked by its own rules."""
    old = _punch(company, employee, when=timezone.now() - timedelta(days=800), version=1)
    old.refresh_from_db()

    assert old.hash_version == 1
    assert old.verify_hash()


@pytest.mark.django_db
def test_removing_the_ip_from_an_old_event_does_break_it(company, employee):
    """Calibration for the test above: without the version, that one proves
    nothing. This is the behaviour that made the change necessary, and the
    reason the purge has to leave version 1 alone."""
    old = _punch(company, employee, when=timezone.now() - timedelta(days=800), version=1)

    old.ip_address = None
    assert not old.verify_hash()


@pytest.mark.django_db
def test_the_two_versions_produce_different_hashes(company, employee):
    """Otherwise the versioning would be decorative."""
    when = timezone.now() - timedelta(days=10)
    v1 = _punch(company, employee, when=when, version=1)
    v2 = _punch(company, employee, when=when, version=2)

    assert v1.hash_integrity != v2.hash_integrity


# --------------------------------------------------------------- the purge itself


@pytest.mark.django_db
def test_metadata_past_the_window_is_purged_and_the_event_survives(company, employee):
    with freeze_time("2026-08-11 10:00:00"):
        old = _punch(company, employee, when=timezone.now() - timedelta(days=400))
        stamp, kind = old.timestamp, old.punch_type

        call_command("purge_security_metadata", stdout=StringIO())

    old.refresh_from_db()
    assert old.ip_address is None
    assert old.device_id == ""
    assert old.user_agent == ""
    # The record of who clocked in, when and how is intact --- and still valid.
    assert old.timestamp == stamp
    assert old.punch_type == kind
    assert old.is_active
    assert old.verify_hash()


@pytest.mark.django_db
def test_recent_metadata_is_left_alone(company, employee):
    with freeze_time("2026-08-11 10:00:00"):
        recent = _punch(company, employee, when=timezone.now() - timedelta(days=30))
        call_command("purge_security_metadata", stdout=StringIO())

    recent.refresh_from_db()
    assert recent.ip_address == "10.0.0.7"


@pytest.mark.django_db
def test_the_window_is_the_companys_to_set(company, employee):
    company.security_metadata_retention_days = 7
    company.save(update_fields=["security_metadata_retention_days"])

    with freeze_time("2026-08-11 10:00:00"):
        punch = _punch(company, employee, when=timezone.now() - timedelta(days=30))
        call_command("purge_security_metadata", stdout=StringIO())

    punch.refresh_from_db()
    assert punch.ip_address is None


@pytest.mark.django_db
def test_old_payload_events_are_skipped_and_said_out_loud(company, employee):
    """A silent skip would read as "everything is purged". It is not."""
    with freeze_time("2026-08-11 10:00:00"):
        stuck = _punch(company, employee, when=timezone.now() - timedelta(days=900), version=1)
        out = StringIO()
        call_command("purge_security_metadata", stdout=out)

    stuck.refresh_from_db()
    assert stuck.ip_address == "10.0.0.7"  # kept, because its hash needs it
    assert stuck.verify_hash()
    assert "skipped" in out.getvalue()
    assert "version 1" in out.getvalue()


@pytest.mark.django_db
def test_a_dry_run_changes_nothing(company, employee):
    with freeze_time("2026-08-11 10:00:00"):
        punch = _punch(company, employee, when=timezone.now() - timedelta(days=400))
        out = StringIO()
        call_command("purge_security_metadata", "--dry-run", stdout=out)

    punch.refresh_from_db()
    assert punch.ip_address == "10.0.0.7"
    assert "Would purge 1" in out.getvalue()


@pytest.mark.django_db
def test_the_purge_does_not_cross_between_companies(company, employee):
    """Running from cron there is no company in context, so the boundary here is
    the filter. Worth a test of its own: getting it wrong purges everyone."""
    other = Tenant.objects.create(name="Otra SL", tax_id="B22222222", time_zone="Europe/Madrid")
    with tenant_context(other.id):
        theirs = User.objects.create_user(
            email="nuria@example.com",
            password="a-sufficiently-long-password",
            tenant=other,
        )

    with freeze_time("2026-08-11 10:00:00"):
        mine = _punch(company, employee, when=timezone.now() - timedelta(days=400))
        yours = _punch(other, theirs, when=timezone.now() - timedelta(days=400))

        call_command("purge_security_metadata", "--tenant", "B11111111", stdout=StringIO())

    mine.refresh_from_db()
    yours.refresh_from_db()
    assert mine.ip_address is None
    assert yours.ip_address == "10.0.0.7"


@pytest.mark.django_db
def test_una_empresa_de_baja_tambien_se_purga(company, employee):
    """El plazo no deja de correr porque la empresa deje de usar el producto.

    El comando recorría solo las empresas activas, así que una que se daba de
    baja conservaba las IP y los dispositivos de todos sus fichajes **para
    siempre** --- y terminaba diciendo «Purged 0 events», o sea que todo iba
    bien. Son justo los datos que ya no mira nadie.

    Los fichajes siguen ahí y tienen que seguir: son el registro y viven cuatro
    años. Lo que sobra es la IP.
    """
    with freeze_time("2026-08-11 10:00:00"):
        punch = _punch(company, employee, when=timezone.now() - timedelta(days=400))

        company.is_active = False
        company.save(update_fields=["is_active"])

        salida = StringIO()
        call_command("purge_security_metadata", stdout=salida)

    punch.refresh_from_db()
    assert punch.ip_address is None, "una empresa de baja conservaba la IP para siempre"
    assert punch.device_id == ""
    assert "Purged 1" in salida.getvalue()


@pytest.mark.django_db
def test_y_el_fichaje_de_la_empresa_de_baja_sigue_entero(company, employee):
    """El contraste, y el límite del arreglo.

    Purgar los metadatos de una empresa de baja no puede convertirse en borrar
    su registro: el art. 34.9 pide cuatro años y una baja no los acorta. Se va
    la IP; la hora, el tipo y el sello se quedan.
    """
    with freeze_time("2026-08-11 10:00:00"):
        punch = _punch(company, employee, when=timezone.now() - timedelta(days=400))
        cuando, tipo, sello = punch.timestamp, punch.punch_type, punch.hash_integrity

        company.is_active = False
        company.save(update_fields=["is_active"])
        call_command("purge_security_metadata", stdout=StringIO())

    punch.refresh_from_db()
    assert punch.timestamp == cuando
    assert punch.punch_type == tipo
    assert punch.hash_integrity == sello
    assert punch.verify_hash(), "el sello dejó de cuadrar"
