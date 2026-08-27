"""That the legal layer is actually a layer.

Spain works exactly as before --- the 448 tests that existed before this refactor
prove that, unchanged --- so what is left to show is the opposite: that a second
country reaches every place a citation or a figure surfaces, without editing
anything outside its own file.

So these tests register a made-up framework and follow it through. The figures
are deliberately unlike Spain's, because a value that happens to match proves
nothing about where it came from.

If adding a country ever requires touching a file other than `apps/legal/`,
one of these fails, and that is the point of them.
"""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from rest_framework.test import APIClient

from apps.common.clock import local_today
from apps.common.models import tenant_context
from apps.legal import DIRECTIVE, FRAMEWORKS, for_country
from apps.legal.base import Citation, LegalFramework, MinorProtections
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

#: Nothing like Spain, on purpose.
NOWHERE = LegalFramework(
    country="XX",
    name="Ruritania",
    defaults={
        "weekly_hours": 35,
        "daily_rest_hours": 14,
        "weekly_rest_hours": 48,
        "break_after_hours": 4,
        "break_minutes": 25,
        "annual_overtime_hours": 120,
        "night_starts_at": time(21, 0),
        "night_ends_at": time(5, 0),
    },
    citations={
        "weekly_hours": Citation("§ 3 ArbZG-XX", "Treinta y cinco horas."),
        "daily_rest_hours": Citation("§ 5 ArbZG-XX"),
    },
    finding_citations={
        "short_daily_rest": Citation("§ 5 ArbZG-XX"),
        "weekly_hours_exceeded": Citation("§ 3 ArbZG-XX"),
        "minor_over_daily_limit": Citation("§ 8 JArbSchG-XX"),
    },
    minors=MinorProtections(
        max_daily_hours=7,
        break_after_hours=4,
        break_minutes=60,
        weekly_rest_hours=48,
        night_work_forbidden=True,
        overtime_forbidden=True,
        citations={"overtime": Citation("§ 21 JArbSchG-XX")},
    ),
)


@pytest.fixture
def elsewhere(db):
    """A company in Ruritania, with the framework registered for the test.

    Registered and removed rather than added to `FRAMEWORKS` permanently: a
    fake country left in the registry would show up in anything that iterates
    it, and the next person would have to work out whether it was real.
    """
    FRAMEWORKS["XX"] = NOWHERE
    try:
        yield Tenant.objects.create(
            name="Ruritania Ltd", tax_id="B77777777", country="XX", time_zone="Europe/Madrid"
        )
    finally:
        FRAMEWORKS.pop("XX", None)


@pytest.fixture
def spain(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", country="ES", time_zone="Europe/Madrid"
    )


def admin_of(company, email="admin@example.test"):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email, password=PASSWORD, tenant=company, first_name="Ana", role=Role.ADMIN
        )


def client_for(person):
    client = APIClient()
    client.force_authenticate(person)
    return client


# ------------------------------------------------------------------ resolving


@pytest.mark.django_db
def test_a_company_gets_its_own_countrys_figures(elsewhere, spain):
    with tenant_context(elsewhere.id):
        theirs = WorkingTimeRules.for_company(elsewhere)
    with tenant_context(spain.id):
        ours = WorkingTimeRules.for_company(spain)

    assert theirs.weekly_hours == 35
    assert theirs.daily_rest_hours == 14
    assert ours.weekly_hours == 40
    assert ours.daily_rest_hours == 12


@pytest.mark.django_db
def test_an_unknown_country_falls_back_to_the_directive_and_not_to_spain():
    """The important half of the fallback. Spain's figures under another flag
    would look configured, nobody would question them, and every warning would
    cite an article that does not apply there."""
    framework = for_country("JP")

    assert framework is DIRECTIVE
    assert framework.defaults["weekly_hours"] == 48  # art. 6.b, not Spain's 40
    assert "Dir. 2003/88/CE" in framework.citations["weekly_hours"].basis


@pytest.mark.django_db
def test_a_company_with_no_country_also_gets_the_directive():
    """Rows created before the field was filled, or by a fixture."""
    nowhere = Tenant.objects.create(name="Sin país", tax_id="B88888888", country="")

    assert for_country(nowhere.country) is DIRECTIVE


# --------------------------------------------------------- through the roster


@pytest.mark.django_db
def test_a_warning_cites_the_local_article(elsewhere):
    """Nine citations used to be typed in beside each `Finding`. If any is left
    hardcoded, this is where it shows."""
    from apps.shifts.models import Shift
    from apps.shifts.services import review_roster

    person = admin_of(elsewhere, "trabaja@ruritania.test")
    with tenant_context(elsewhere.id):
        # Two long days back to back: under fourteen hours of rest there.
        for day in (date(2026, 9, 7), date(2026, 9, 8)):
            Shift.objects.create(
                tenant=elsewhere,
                employee=person,
                day=day,
                segments=[{"start": "08:00", "end": "21:00"}],
            )
        findings = review_roster(company=elsewhere, first=date(2026, 9, 1), last=date(2026, 9, 30))

    rest = [f for f in findings if f.code == "short_daily_rest"]
    assert rest, "the roster was meant to break the daily rest rule"
    assert rest[0].basis == "§ 5 ArbZG-XX"
    assert "ET" not in rest[0].basis


@pytest.mark.django_db
def test_the_minor_floors_are_the_local_ones(elsewhere):
    """Seven hours in Ruritania, eight in Spain. A day of seven and a half is
    over the limit there and inside it here."""
    from apps.shifts.models import Shift
    from apps.shifts.services import review_roster

    young = admin_of(elsewhere, "joven@ruritania.test")
    with tenant_context(elsewhere.id):
        young.date_of_birth = date(2009, 1, 1)
        young.save(update_fields=["date_of_birth"])
        Shift.objects.create(
            tenant=elsewhere,
            employee=young,
            day=date(2026, 9, 7),
            segments=[{"start": "08:00", "end": "15:30"}],  # 7.5 h
        )
        findings = review_roster(company=elsewhere, first=date(2026, 9, 1), last=date(2026, 9, 30))

    over = [f for f in findings if f.code == "minor_over_daily_limit"]
    assert over, "seven and a half hours is over Ruritania's seven"
    assert over[0].basis == "§ 8 JArbSchG-XX"


@pytest.mark.django_db
def test_a_refusal_quotes_the_local_article(elsewhere):
    """The overtime ban for minors names its article in the message a person
    reads. It was Spain's, spelled out."""
    from apps.common.exceptions import BusinessRuleError
    from apps.punches.models import HoursNature, OvertimeSettlement
    from apps.punches.services import register_punch

    young = admin_of(elsewhere, "joven@ruritania.test")
    with tenant_context(elsewhere.id):
        young.date_of_birth = local_today(elsewhere) - timedelta(days=365 * 17)
        young.save(update_fields=["date_of_birth"])

        with pytest.raises(BusinessRuleError) as caught:
            register_punch(
                employee=young,
                company=elsewhere,
                hours_nature=HoursNature.OVERTIME,
                overtime_settlement=OvertimeSettlement.PAID,
            )

    assert "§ 21 JArbSchG-XX" in str(caught.value)
    assert "ET" not in str(caught.value)


# ------------------------------------------------------------- through the API


@pytest.mark.django_db
def test_the_rules_endpoint_serves_the_local_citations(elsewhere):
    """What removes the duplication. The settings screen used to carry its own
    copy of the articles, hardcoded and Spanish."""
    body = client_for(admin_of(elsewhere)).get("/api/working-time-rules/").json()

    assert body["country"] == "XX"
    assert body["framework"] == "Ruritania"
    assert body["citations"]["weekly_hours"]["basis"] == "§ 3 ArbZG-XX"
    assert body["weekly_hours"] == "35.0"
    assert body["minors"]["max_daily_hours"] == 7


@pytest.mark.django_db
def test_spain_still_serves_what_the_screen_used_to_hardcode(spain):
    """The other direction: the strings the frontend had written by hand now
    come from the server, and they are the same ones."""
    body = client_for(admin_of(spain)).get("/api/working-time-rules/").json()

    assert body["country"] == "ES"
    assert body["citations"]["weekly_hours"]["basis"] == "Art. 34.1 ET"
    assert body["citations"]["daily_rest_hours"]["basis"] == "Art. 34.3 ET"
    assert body["citations"]["weekly_rest_hours"]["basis"] == "Art. 37.1 ET"
    assert body["citations"]["break_after_hours"]["basis"] == "Art. 34.4 ET"
    assert body["citations"]["annual_overtime_hours"]["basis"] == "Art. 35.2 ET"
    assert body["citations"]["night_starts_at"]["basis"] == "Art. 36.1 ET"


@pytest.mark.django_db
def test_a_citation_that_does_not_exist_is_blank_and_not_an_error(elsewhere):
    """A country with no rule about something should produce a warning with no
    citation, not a crash. The roster's leave clash has always had a blank one,
    because it is a planning mistake and not a breach."""
    assert for_country("XX").citation("roster_notice_days").basis == ""
    assert for_country("XX").finding_citation("rostered_on_leave").basis == ""


# ------------------------------------------------------------- Spain unchanged


@pytest.mark.django_db
def test_spanish_figures_are_what_they_always_were(spain):
    """The refactor's contract. These are the numbers the product shipped with
    before the legal layer existed."""
    with tenant_context(spain.id):
        rules = WorkingTimeRules.for_company(spain)

    assert rules.weekly_hours == 40
    assert rules.daily_rest_hours == 12
    assert rules.weekly_rest_hours == 36
    assert rules.break_after_hours == 6
    assert rules.break_minutes == 15
    assert rules.break_counts_as_work is False
    assert rules.annual_overtime_hours == 80
    assert rules.night_starts_at == time(22, 0)
    assert rules.night_ends_at == time(6, 0)
    assert rules.correction_consent_days == 7
    assert rules.roster_notice_days == 5
