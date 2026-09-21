"""A punch made where there was no signal, and sent when there was.

The rule the rest of this module rests on is that the server owns the clock. This is
its one exception, and what is fixed here is that it stays an exception: the device's
time is accepted only inside a window the company sets, both times are always stored,
the gap reaches the inspection report, and none of it can be quietly rewritten
afterwards.

Art. 34.9 ET asks for a record that is reliable, objective and traceable. It does not
ask for it to be written at the same moment as the work --- which is fortunate,
because somebody at the far end of a park with no coverage cannot write anything.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone, translation
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval
from apps.punches.services import register_punch
from apps.reports.services import build_report, day_notes
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def marta(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="marta@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Marta",
            last_name="Ruiz",
            employee_id="EMP-0003",
        )


def signed_in(marta):
    client = APIClient()
    client.force_authenticate(user=marta)
    return client


# ------------------------------------------------------- the ordinary punch


@pytest.mark.django_db
def test_a_punch_that_declares_nothing_still_counts_by_our_clock(company, marta):
    """The rule, not the exception: nothing changes for the punch made online."""
    with freeze_time("2026-09-18 07:00:00+02:00"):
        punch = register_punch(employee=marta, company=company)

    assert punch.declared_at is None
    assert punch.timestamp == punch.received_at
    assert punch.was_deferred is False


# ------------------------------------------------------ inside the window


@pytest.mark.django_db
def test_the_time_that_counts_is_the_one_the_device_declared(company, marta):
    made = datetime(2026, 9, 18, 6, 55, tzinfo=timezone.get_fixed_timezone(120))

    with freeze_time("2026-09-18 09:30:00+02:00"):
        punch = register_punch(employee=marta, company=company, declared_at=made)

    assert punch.timestamp == made, "quien empezó a las 6:55 empezó a las 6:55"
    assert punch.declared_at == made
    assert punch.received_at > punch.declared_at, "y las dos horas se guardan"
    assert punch.arrival_delay == timedelta(hours=2, minutes=35)
    assert punch.was_deferred is True


@pytest.mark.django_db
def test_a_couple_of_seconds_of_network_is_not_a_deferred_punch(company, marta):
    """Marcar esos sería poner la marca en casi todos y enseñar a no mirarla."""
    with freeze_time("2026-09-18 07:00:00+02:00"):
        casi_ahora = timezone.now() - timedelta(seconds=8)
        punch = register_punch(employee=marta, company=company, declared_at=casi_ahora)

    assert punch.timestamp == casi_ahora
    assert punch.was_deferred is False


# ----------------------------------------------------- outside the window


@pytest.mark.django_db
def test_past_the_grace_period_it_goes_through_the_correction_flow(company, marta):
    """No se rechaza por falsa: se rechaza porque nadie ha respondido de ella."""
    anteayer = timezone.now() - timedelta(days=2)

    # El idioma se fija alrededor de la llamada, no del assert: el mensaje se
    # interpola al lanzarse, así que para entonces ya está en el idioma que hubiera.
    # Y está traducido a tres, de modo que leerlo en el del entorno haría que la
    # prueba dijera una cosa distinta según quién la corra.
    with translation.override("en"), pytest.raises(BusinessRuleError) as refusal:
        register_punch(employee=marta, company=company, declared_at=anteayer)

    assert refusal.value.code == "declared_time_too_late"
    assert "correction" in str(refusal.value.message)
    assert not Punch.objects_all_tenants.filter(employee=marta).exists()


@pytest.mark.django_db
def test_the_company_decides_how_late_is_too_late(company, marta):
    """Un plazo más largo acepta lo que el de por defecto rechaza."""
    company.offline_punch_grace_hours = 72
    company.save(update_fields=["offline_punch_grace_hours"])
    anteayer = timezone.now() - timedelta(days=2)

    punch = register_punch(employee=marta, company=company, declared_at=anteayer)

    assert punch.timestamp == anteayer


@pytest.mark.django_db
def test_a_company_at_zero_records_everything_from_arrival(company, marta):
    company.offline_punch_grace_hours = 0
    company.save(update_fields=["offline_punch_grace_hours"])

    with pytest.raises(BusinessRuleError) as refusal:
        register_punch(
            employee=marta, company=company, declared_at=timezone.now() - timedelta(minutes=30)
        )

    assert refusal.value.code == "declared_time_not_accepted"


@pytest.mark.django_db
def test_a_clock_set_to_the_future_is_refused(company, marta):
    with pytest.raises(BusinessRuleError) as refusal:
        register_punch(
            employee=marta, company=company, declared_at=timezone.now() + timedelta(hours=3)
        )

    assert refusal.value.code == "declared_time_in_the_future"


@pytest.mark.django_db
def test_a_clock_a_few_seconds_fast_is_trimmed_not_refused(company, marta):
    """Los relojes de los móviles van sincronizados, no al segundo."""
    with freeze_time("2026-09-18 07:00:00+02:00"):
        punch = register_punch(
            employee=marta, company=company, declared_at=timezone.now() + timedelta(seconds=20)
        )
        assert punch.timestamp == punch.received_at


# ------------------------------------------------------------- the evidence


@pytest.mark.django_db
def test_the_gap_is_sealed_so_it_cannot_be_tidied_away_later(company, marta):
    punch = register_punch(
        employee=marta, company=company, declared_at=timezone.now() - timedelta(hours=3)
    )
    assert punch.verify_hash() is True

    # Alguien deja el asiento como si hubiera llegado en el momento.
    punch.received_at = punch.declared_at
    assert punch.verify_hash() is False, "borrar el desfase tiene que romper el sello"


@pytest.mark.django_db
def test_the_inspection_report_says_it_was_recorded_offline(company, marta):
    entrada = datetime(2026, 9, 18, 6, 55, tzinfo=timezone.get_fixed_timezone(120))
    salida = datetime(2026, 9, 18, 14, 0, tzinfo=timezone.get_fixed_timezone(120))

    with freeze_time("2026-09-18 16:00:00+02:00"):
        register_punch(employee=marta, company=company, declared_at=entrada)
        register_punch(employee=marta, company=company, declared_at=salida)

    informe = build_report(
        employee=marta, company=company, date_from=entrada.date(), date_to=entrada.date()
    )
    fila = next(r for r in informe.rows if r.entries)

    assert fila.deferred is True
    with translation.override("en"):
        nota = str(day_notes(fila))
    assert "offline" in nota
    assert "16:00" in nota, "y dice cuándo llegó, que es la otra mitad de la prueba"


@pytest.mark.django_db
def test_the_api_takes_the_declared_time_and_gives_both_back(company, marta):
    made = timezone.now() - timedelta(hours=1)

    answer = signed_in(marta).post(
        "/api/punches/",
        {"declared_at": made.isoformat(), "interval": PunchInterval.WORK},
        format="json",
    )

    assert answer.status_code == 201
    cuerpo = answer.json()
    assert cuerpo["declared_at"] is not None
    assert cuerpo["received_at"] is not None
    assert cuerpo["was_deferred"] is True
