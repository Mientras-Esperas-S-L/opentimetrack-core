"""The working-time report.

What is checked here is what an inspector would look for: that the figures add
up, that the day is grouped by the local date, that incidents are visible rather
than hidden, and that the document can be shown not to have changed.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.reports.pdf import render_pdf
from apps.reports.services import build_report, to_csv
from apps.tenants.models import Tenant
from apps.users.models import User


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Jardines del Sur S.L.", tax_id="B98765432", time_zone="Europe/Madrid"
    )


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Ana",
            last_name="García",
            employee_id="EMP-0042",
        )


def _work_a_day(employee, company, entry: str, exit_: str):
    with freeze_time(entry):
        register_punch(employee=employee, company=company)
    with freeze_time(exit_):
        register_punch(employee=employee, company=company)


@pytest.mark.django_db
def test_the_report_adds_up_the_period(company, employee):
    _work_a_day(employee, company, "2026-08-03 06:00:00", "2026-08-03 14:00:00")  # 8 h
    _work_a_day(employee, company, "2026-08-04 06:00:00", "2026-08-04 12:00:00")  # 6 h

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 4),
    )

    assert report.total_seconds == 14 * 3600
    assert len(report.rows) == 2
    assert report.rows[0].seconds == 8 * 3600


@pytest.mark.django_db
def test_an_entry_with_no_exit_is_reported_not_hidden(company, employee):
    """Hiding an incomplete day would make the record less trustworthy, not more."""
    with freeze_time("2026-08-03 06:00:00"):
        register_punch(employee=employee, company=company)

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    )

    assert report.rows[0].incidents
    assert report.rows[0].entries[0][1] is None


@pytest.mark.django_db
def test_the_hash_depends_on_the_content_and_not_on_the_moment(company, employee):
    """Two copies of the same period must be comparable."""
    _work_a_day(employee, company, "2026-08-03 06:00:00", "2026-08-03 14:00:00")

    with freeze_time("2026-08-10 09:00:00"):
        first = build_report(
            employee=employee,
            company=company,
            date_from=date(2026, 8, 3),
            date_to=date(2026, 8, 3),
        )
    with freeze_time("2026-09-01 18:30:00"):
        second = build_report(
            employee=employee,
            company=company,
            date_from=date(2026, 8, 3),
            date_to=date(2026, 8, 3),
        )

    assert first.fingerprint == second.fingerprint
    assert first.generated_at != second.generated_at


@pytest.mark.django_db
def test_changing_the_hours_changes_the_hash(company, employee):
    _work_a_day(employee, company, "2026-08-03 06:00:00", "2026-08-03 14:00:00")
    before = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    ).fingerprint

    _work_a_day(employee, company, "2026-08-03 15:00:00", "2026-08-03 17:00:00")
    after = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    ).fingerprint

    assert before != after


@pytest.mark.django_db
def test_the_csv_carries_what_the_law_asks_for(company, employee):
    _work_a_day(employee, company, "2026-08-03 06:00:00", "2026-08-03 14:00:00")

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    )
    text = to_csv(report)

    assert "Jardines del Sur S.L." in text  # company
    assert "B98765432" in text  # tax number
    assert "Ana García" in text  # employee
    assert "EMP-0042" in text  # staff number
    assert "08:00" in text  # hours worked
    assert report.fingerprint in text  # verification hash


@pytest.mark.django_db
def test_the_pdf_is_generated_and_is_a_pdf(company, employee):
    _work_a_day(employee, company, "2026-08-03 06:00:00", "2026-08-03 14:00:00")

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    )
    content = render_pdf(report)

    assert content.startswith(b"%PDF-")
    assert len(content) > 1000


@pytest.mark.django_db
def test_an_empty_period_still_produces_a_document(company, employee):
    """Somebody who did not work has the right to a record saying so."""
    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 3),
    )

    assert report.total_seconds == 0
    assert render_pdf(report).startswith(b"%PDF-")


@pytest.mark.django_db
def test_when_the_agreement_makes_the_break_working_time_the_report_says_so(company, employee):
    """The document handed over must not contradict the screen that produced it.

    Art. 34.4 ET counts the break as working time when the agreement says so,
    and the gardening agreement shipped in this repository does say so. Before
    this test the report subtracted it regardless: the same day read 8 h on
    screen and 7 h 45 in the PDF, the CSV and the payroll summary --- always in
    the direction that favours the employer.
    """
    from apps.punches.models import PunchInterval
    from apps.punches.services import build_day_status
    from apps.tenants.rules import WorkingTimeRules

    rules = WorkingTimeRules.for_company(company)
    rules.break_counts_as_work = True
    rules.save(update_fields=["break_counts_as_work"])

    with freeze_time("2026-08-03 06:00:00"):
        register_punch(employee=employee, company=company)
    with freeze_time("2026-08-03 10:00:00"):
        register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-03 10:15:00"):
        register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-03 14:00:00"):
        register_punch(employee=employee, company=company)

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    )
    on_screen = build_day_status(employee=employee, company=company, day=date(2026, 8, 3))

    assert report.rows[0].break_seconds == 15 * 60
    assert report.rows[0].seconds == 8 * 3600
    assert report.total_seconds == on_screen.worked_seconds


@pytest.mark.django_db
def test_by_default_the_break_still_comes_off_the_total(company, employee):
    """The other half of the rule: assuming it counts would overstate the hours."""
    from apps.punches.models import PunchInterval
    from apps.punches.services import build_day_status

    with freeze_time("2026-08-03 06:00:00"):
        register_punch(employee=employee, company=company)
    with freeze_time("2026-08-03 10:00:00"):
        register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-03 10:15:00"):
        register_punch(employee=employee, company=company, interval=PunchInterval.BREAK)
    with freeze_time("2026-08-03 14:00:00"):
        register_punch(employee=employee, company=company)

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 3),
    )
    on_screen = build_day_status(employee=employee, company=company, day=date(2026, 8, 3))

    assert report.rows[0].seconds == 8 * 3600 - 15 * 60
    assert report.total_seconds == on_screen.worked_seconds


# ------------------------------------------- de dónde vino cada cosa, dicho bien


@pytest.mark.django_db
def test_el_informe_distingue_quien_registro_cada_cosa(company, employee):
    """Tres orígenes muy distintos salían como «registrado por una aplicación».

    `was_delegated` agrupa `DELEGATED`, `ADMIN` e `IMPORT` --- que para el modelo
    es útil, porque los tres significan «no lo hizo la persona»--- y el informe
    usaba ese booleano para escribir una sola frase. Así que una corrección
    resuelta por la administración de la empresa, tras el procedimiento del art.
    4.b, se le contaba a la Inspección como si la hubiera registrado una
    aplicación externa.

    El manual promete lo contrario en dos sitios: «los dos que no hizo la persona
    van destacados» y «quien lee el informe tiene derecho a distinguirlos». Un
    inspector que lea «una aplicación» donde hubo una corrección entiende otra
    cosa, y lo que entiende es más benigno para la empresa.
    """
    from apps.punches.models import PunchSource
    from apps.reports.services import build_report, day_notes

    with freeze_time("2026-08-03 06:00:00"):
        register_punch(employee=employee, company=company, source=PunchSource.DELEGATED)
    with freeze_time("2026-08-04 06:00:00"):
        register_punch(employee=employee, company=company, source=PunchSource.ADMIN)
    with freeze_time("2026-08-05 06:00:00"):
        register_punch(employee=employee, company=company, source=PunchSource.IMPORT)

    report = build_report(
        employee=employee,
        company=company,
        date_from=date(2026, 8, 3),
        date_to=date(2026, 8, 5),
    )
    porDia = {row.day: day_notes(row) for row in report.rows}

    assert "aplicación" in porDia[date(2026, 8, 3)]
    assert "corregido" in porDia[date(2026, 8, 4)].lower(), (
        f"una corrección se cuenta como otra cosa: {porDia[date(2026, 8, 4)]!r}"
    )
    assert "importado" in porDia[date(2026, 8, 5)].lower(), (
        f"una importación se cuenta como otra cosa: {porDia[date(2026, 8, 5)]!r}"
    )
    # Y no se confunden entre sí.
    assert "aplicación" not in porDia[date(2026, 8, 4)]
    assert "aplicación" not in porDia[date(2026, 8, 5)]
