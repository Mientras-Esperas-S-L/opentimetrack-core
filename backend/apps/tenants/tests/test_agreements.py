"""Reading a collective-agreement ficha, and refusing a wrong one.

The point of these tests is not that a good ficha passes. It is that a bad one
**fails** --- a validator nobody has watched reject anything is indistinguishable
from a validator that returns nothing. So every floor gets a ficha built to
break it, and the real jardinería ficha is checked figure by figure against the
BOE text it was transcribed from.

Art. 3.3 ET is the principle underneath: an agreement improves the legal
minimum or it does not hold. A ficha that fails one of these is a transcription
to re-read.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from django.utils import translation

from apps.common.models import tenant_context
from apps.tenants import agreements
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules

TODAY = dt.date(2026, 8, 12)

#: The smallest ficha the schema accepts. Tests copy it and break one thing.
MINIMAL = {
    "format": 1,
    "agreement": {
        "name": "Convenio de prueba",
        "scope": "state",
        "regcon": "99000000000001",
        "valid_from": "2025-01-01",
        "source": {
            "publication": "BOE-A-2025-0001",
            "published_on": "2025-01-01",
            "url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-0001",
        },
    },
    "working_time": {},
    "provenance": {"transcribed_by": "Pruebas", "verified_on": "2026-08-01"},
}


def write(tmp_path: Path, ficha: dict, name: str = "ficha.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(ficha, allow_unicode=True), encoding="utf-8")
    return path


def with_values(**values) -> dict:
    """A copy of MINIMAL whose working_time carries these figures."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))  # deep copy
    ficha["working_time"] = {k: {"value": v, "basis": "Art. 1"} for k, v in values.items()}
    return ficha


def codes(problems) -> list[str]:
    return [p.field for p in problems]


# ------------------------------------------------------------------ the schema


def test_a_value_without_its_article_is_rejected(tmp_path):
    """The one rule the whole format rests on. A figure nobody can trace back
    to an article cannot be argued with, and a figure that cannot be argued
    with should not configure anybody's working day."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["working_time"] = {"weekly_hours": {"value": 38}}  # no basis

    with pytest.raises(agreements.FichaError, match="basis"):
        agreements.load(write(tmp_path, ficha))


def test_a_regcon_that_is_not_fourteen_digits_is_rejected(tmp_path):
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["agreement"]["regcon"] = "9900299"

    with pytest.raises(agreements.FichaError, match="regcon"):
        agreements.load(write(tmp_path, ficha))


def test_an_unknown_key_is_rejected_rather_than_ignored(tmp_path):
    """A typo in a key name would otherwise pass silently and the figure would
    never be applied, which looks exactly like the system ignoring the
    agreement."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["working_time"] = {"weekly_ours": {"value": 38, "basis": "Art. 1"}}

    with pytest.raises(agreements.FichaError):
        agreements.load(write(tmp_path, ficha))


def test_unquoted_dates_are_accepted(tmp_path):
    """YAML turns an unquoted 2026-01-30 into a date and JSON Schema wants a
    string. Making authors remember quotes would be a rule that exists only to
    accommodate our validator."""
    path = tmp_path / "ficha.yaml"
    path.write_text(
        """
format: 1
agreement:
  name: Convenio de prueba
  scope: state
  regcon: "99000000000001"
  valid_from: 2025-01-01
  source:
    publication: BOE-A-2025-0001
    published_on: 2025-01-01
    url: https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-0001
working_time: {}
provenance:
  transcribed_by: Pruebas
  verified_on: 2026-08-01
""",
        encoding="utf-8",
    )

    ficha = agreements.load(path)

    assert ficha.verified_on == dt.date(2026, 8, 1)


def test_an_unquoted_regcon_is_refused_with_the_reason(tmp_path):
    """It is the one field where quoting matters and nothing on screen says so.
    Unquoted it becomes a number, and a provincial code starting with zero ---
    01 is Álava --- silently loses it and names a different agreement."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["agreement"]["regcon"] = 99000000000001  # an int, as YAML would read it

    # In English so the assertion documents the wording the loader is meant to
    # produce, rather than tracking whichever catalogue happens to be compiled.
    with translation.override("en"), pytest.raises(agreements.FichaError, match="quotes"):
        agreements.load(write(tmp_path, ficha))


def test_the_template_is_not_read_as_a_ficha(tmp_path):
    """It has empty values on purpose. Loading it would fail, so `load_all`
    skips anything starting with an underscore."""
    write(tmp_path, MINIMAL, "_template.yaml")
    write(tmp_path, MINIMAL, "real.yaml")

    assert [f.path.name for f in agreements.load_all(tmp_path)] == ["real.yaml"]


# ------------------------------------------------- the floors, each one fired


@pytest.mark.parametrize(
    ("values", "field", "basis"),
    [
        ({"weekly_hours": 42}, "weekly_hours", "Art. 34.1 ET"),
        ({"annual_hours": 1900}, "annual_hours", "Art. 34.1 ET"),
        ({"weekly_rest_hours": 24}, "weekly_rest_hours", "Art. 37.1 ET"),
        ({"annual_overtime_hours": 100}, "annual_overtime_hours", "Art. 35.2 ET"),
        ({"annual_leave_days": 25}, "annual_leave_days", "Art. 38.1 ET"),
    ],
)
def test_a_figure_worse_than_the_law_is_fatal(tmp_path, values, field, basis):
    """Art. 3.3 ET: an agreement may improve a minimum, never worsen it. Each
    of these is either a transcription error or an agreement that does not
    hold, and both need a person."""
    ficha = agreements.load(write(tmp_path, with_values(**values)))

    problems = [p for p in agreements.inspect(ficha, TODAY) if p.fatal]

    assert codes(problems) == [field]
    assert problems[0].basis == basis


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"max_daily_hours": 10}, "max_daily_hours"),
        ({"daily_rest_hours": 10}, "daily_rest_hours"),
    ],
)
def test_a_figure_a_sector_regime_could_justify_is_only_a_warning(tmp_path, values, field):
    """RD 1561/1995 lowers the daily rest for transport, on-call and shift
    handovers, and irregular distribution allows a ninth hour. Refusing these
    outright would call lawful agreements invalid."""
    ficha = agreements.load(write(tmp_path, with_values(**values)))

    problems = agreements.inspect(ficha, TODAY)

    assert codes(problems) == [field]
    assert not problems[0].fatal


def test_thirty_calendar_days_of_leave_is_not_below_the_floor(tmp_path):
    """The same number means two different things depending on the unit, and
    the floor differs with it: thirty calendar days, twenty-two working."""
    ficha = agreements.load(
        write(tmp_path, with_values(annual_leave_days=30, leave_days_are_working_days=False))
    )

    assert agreements.inspect(ficha, TODAY) == []


def test_twenty_two_working_days_is_not_below_the_floor_either(tmp_path):
    ficha = agreements.load(
        write(tmp_path, with_values(annual_leave_days=22, leave_days_are_working_days=True))
    )

    assert agreements.inspect(ficha, TODAY) == []


def test_a_ficha_at_the_legal_minimum_raises_nothing(tmp_path):
    """The floors are floors. Firing on the ordinary case would make every
    ficha noisy and the warnings would stop being read."""
    ficha = agreements.load(
        write(
            tmp_path,
            with_values(
                weekly_hours=40,
                daily_rest_hours=12,
                weekly_rest_hours=36,
                annual_overtime_hours=80,
                annual_leave_days=30,
            ),
        )
    )

    assert agreements.inspect(ficha, TODAY) == []


# ------------------------------------------------------------------ the dates


def test_a_ficha_checked_in_the_future_is_fatal(tmp_path):
    """Nobody can have opened the boletín tomorrow. It means the date was
    typed rather than earned."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["provenance"]["verified_on"] = "2026-12-01"

    problems = agreements.inspect(agreements.load(write(tmp_path, ficha)), TODAY)

    assert codes(problems) == ["provenance.verified_on"]
    assert problems[0].fatal


def test_an_expired_agreement_is_fatal(tmp_path):
    """A lapsed agreement that still looks current is the worst state of all:
    the company applies it believing it complies."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["agreement"]["valid_until"] = "2026-01-01"

    problems = agreements.inspect(agreements.load(write(tmp_path, ficha)), TODAY)

    assert codes(problems) == ["agreement.valid_until"]
    assert problems[0].fatal


def test_a_ficha_nobody_has_looked_at_in_two_years_is_a_warning(tmp_path):
    """Still valid --- agreements run for years --- but worth saying."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["provenance"]["verified_on"] = "2024-01-01"

    problems = agreements.inspect(agreements.load(write(tmp_path, ficha)), TODAY)

    assert codes(problems) == ["provenance.verified_on"]
    assert not problems[0].fatal


def test_two_fichas_with_the_same_regcon_are_reported(tmp_path):
    """The code is what tells two similarly named agreements apart. Two files
    claiming the same one means one of them is mislabelled."""
    write(tmp_path, MINIMAL, "one.yaml")
    write(tmp_path, MINIMAL, "two.yaml")

    results = agreements.check_all(agreements.load_all(tmp_path), TODAY)

    assert codes(results[tmp_path / "two.yaml"]) == ["agreement.regcon"]
    assert results[tmp_path / "one.yaml"] == []


# ------------------------------------------------- applying one to a company


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.mark.django_db
def test_applying_a_ficha_moves_the_figures_and_says_which(tmp_path, company):
    ficha = agreements.load(
        write(tmp_path, with_values(weekly_hours=38, break_counts_as_work=True))
    )

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        applied = agreements.apply_to_rules(ficha, rules)
        rules.refresh_from_db()

    assert applied.changed["weekly_hours"] == (Decimal("40.0"), 38)
    assert applied.changed["break_counts_as_work"] == (False, True)
    assert rules.weekly_hours == Decimal("38")
    assert rules.break_counts_as_work is True


@pytest.mark.django_db
def test_a_figure_already_matching_is_reported_as_unchanged(tmp_path, company):
    """So that "nothing happened" and "it was already right" do not look the
    same to whoever is reading the result."""
    ficha = agreements.load(write(tmp_path, with_values(weekly_hours=40)))

    with tenant_context(company.id):
        applied = agreements.apply_to_rules(ficha, WorkingTimeRules.for_company(company))

    assert applied.unchanged == ["weekly_hours"]
    assert applied.changed == {}


@pytest.mark.django_db
def test_holiday_in_calendar_days_carries_its_unit_across(tmp_path, company):
    """Thirty calendar days used to be refused, because the field counted
    working days and thirty working days is over a week more than the agreement
    gives. The conversion needed the working week, which is not in the ficha.

    Now the unit is a field too, so both go in together and the figure never
    sits in the wrong one.
    """
    ficha = agreements.load(
        write(tmp_path, with_values(annual_leave_days=30, leave_days_are_working_days=False))
    )

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        applied = agreements.apply_to_rules(ficha, rules)
        company.refresh_from_db()

    assert applied.refused == {}
    assert company.annual_leave_days == 30
    assert company.leave_days_are_working_days is False


@pytest.mark.django_db
def test_holiday_in_working_days_is_applied(tmp_path, company):
    ficha = agreements.load(
        write(tmp_path, with_values(annual_leave_days=23, leave_days_are_working_days=True))
    )

    with tenant_context(company.id):
        agreements.apply_to_rules(ficha, WorkingTimeRules.for_company(company))
        company.refresh_from_db()

    assert company.annual_leave_days == 23


@pytest.mark.django_db
def test_a_figure_with_nowhere_to_go_is_named_not_dropped(tmp_path, company):
    """1700 annual hours is a real obligation the system cannot yet compare.
    Saying so beats letting somebody believe it is being enforced."""
    ficha = agreements.load(write(tmp_path, with_values(annual_hours=1700)))

    with tenant_context(company.id):
        applied = agreements.apply_to_rules(ficha, WorkingTimeRules.for_company(company))

    assert applied.not_applicable == ["annual_hours"]


@pytest.mark.django_db
def test_nothing_is_written_when_the_caller_only_wants_to_look(tmp_path, company):
    ficha = agreements.load(write(tmp_path, with_values(weekly_hours=38)))

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        applied = agreements.apply_to_rules(ficha, rules, commit=False)
        rules.refresh_from_db()

    assert applied.changed["weekly_hours"] == (Decimal("40.0"), 38)
    assert rules.weekly_hours == Decimal("40.0")


# ------------------------------------------------ the ficha we actually ship


def shipped(name: str) -> agreements.Ficha:
    return agreements.load(agreements.AGREEMENTS_DIR / "es" / name)


def test_every_shipped_ficha_is_clean():
    """Runs the same check as CI. If this fails, a published ficha is wrong and
    somebody is configuring their working day from it."""
    fichas = agreements.load_all()
    results = agreements.check_all(fichas, TODAY)

    broken = {
        path.name: [str(p) for p in problems if p.fatal]
        for path, problems in results.items()
        if any(p.fatal for p in problems)
    }

    assert broken == {}


def test_the_gardening_agreement_says_the_break_is_working_time():
    """Art. 16 of the convenio, and the reason this ficha exists. The system
    defaults to not counting it, because art. 34.4 ET only makes it working
    time when the agreement says so --- and this one says so. The difference is
    fifteen minutes a day, around fifty-five hours a year, in the employer's
    favour."""
    ficha = shipped("jardineria-estatal.yaml")

    assert ficha.values["break_counts_as_work"] is True
    assert ficha.values["break_minutes"] == 15
    assert ficha.basis_for("break_counts_as_work") == "Art. 16"


def test_the_gardening_agreement_transcribes_what_the_boe_says():
    """Figure by figure against BOE-A-2026-2227. Written out so that a wrong
    transcription fails here rather than in somebody's payroll."""
    ficha = shipped("jardineria-estatal.yaml")

    assert ficha.regcon == "99002995011981"
    assert ficha.data["agreement"]["source"]["publication"] == "BOE-A-2026-2227"
    assert ficha.values["annual_hours"] == 1700  # art. 16
    assert ficha.values["max_daily_hours"] == 8  # art. 16
    assert ficha.values["daily_rest_hours"] == 12  # art. 16
    assert ficha.values["annual_leave_days"] == 23  # art. 18, five-day week
    assert ficha.values["leave_days_are_working_days"] is True


def test_the_cleaning_agreement_fixes_no_working_time_at_all():
    """Art. 10.2 splits subjects across bargaining levels and keeps Jornada,
    Descansos and Vacaciones out of the state list. An empty `working_time` is
    the transcription being right. A company reading this learns there is a
    provincial agreement to find, which is the one thing it needs."""
    ficha = shipped("limpieza-edificios-locales-estatal.yaml")

    assert ficha.values == {}
    assert ficha.defers["weekly_hours"]["basis"] == "Art. 10.2.B"
    assert ficha.defers["annual_leave_days"]["to"] == "provincial"


def test_the_sanitation_agreement_fixes_almost_nothing_and_says_where_to_look():
    """It is a framework agreement: art. 40.A hands the working day to the
    lower-scope one. Recording that as an absence would tell a company the
    statutory minimum applies and it is done, when in fact there is another
    agreement it has to go and find."""
    ficha = shipped("saneamiento-limpieza-viaria-estatal.yaml")

    assert "weekly_hours" not in ficha.values
    assert ficha.defers["weekly_hours"]["basis"] == "Art. 40.A"
    assert ficha.defers["weekly_hours"]["to"] == "provincial"


def test_the_two_shipped_agreements_disagree_about_the_break_and_both_are_right():
    """Gardening decides it (art. 16: working time). Sanitation refuses to
    decide it (art. 40.A: whatever the lower-scope agreement says). Same
    question, two different answers, and the ficha has to keep them apart ---
    the second is not a gap in the transcription."""
    gardening = shipped("jardineria-estatal.yaml")
    sanitation = shipped("saneamiento-limpieza-viaria-estatal.yaml")

    assert gardening.values["break_counts_as_work"] is True
    assert "break_counts_as_work" not in sanitation.values
    assert "break_counts_as_work" in sanitation.defers


def test_a_figure_cannot_be_fixed_and_deferred_at_once(tmp_path):
    """One of the two readings of the agreement is wrong, and picking one would
    be choosing a number on the reader's behalf."""
    ficha = with_values(weekly_hours=38)
    ficha["defers"] = {"weekly_hours": {"basis": "Art. 2"}}

    with (
        translation.override("en"),
        pytest.raises(agreements.FichaError, match="fixed and deferred"),
    ):
        agreements.load(write(tmp_path, ficha))


def test_a_deferral_may_not_carry_a_value(tmp_path):
    """The whole point is that the agreement does not give one. A value here
    would be inventing what the text says expressly it does not decide."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["defers"] = {"weekly_hours": {"basis": "Art. 2", "value": 38}}

    with pytest.raises(agreements.FichaError):
        agreements.load(write(tmp_path, ficha))


def test_a_deferral_still_needs_the_article_that_defers(tmp_path):
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["defers"] = {"weekly_hours": {"to": "provincial"}}

    with pytest.raises(agreements.FichaError, match="basis"):
        agreements.load(write(tmp_path, ficha))


@pytest.mark.django_db
def test_a_deferred_figure_leaves_the_company_setting_alone(tmp_path, company):
    """There is nothing to write. The company keeps its own value until
    somebody finds the agreement that fixes it."""
    ficha = yaml.safe_load(yaml.safe_dump(MINIMAL))
    ficha["defers"] = {"weekly_hours": {"basis": "Art. 40.A", "to": "provincial"}}

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        applied = agreements.apply_to_rules(agreements.load(write(tmp_path, ficha)), rules)
        rules.refresh_from_db()

    assert applied.changed == {}
    assert rules.weekly_hours == Decimal("40.0")


def test_what_the_gardening_agreement_does_not_fix_is_absent():
    """Weekly rest and the overtime cap are not in the convenio, so the
    Estatuto governs. Their absence is the transcription being right, not
    incomplete --- inventing them would apply a figure nobody agreed to."""
    ficha = shipped("jardineria-estatal.yaml")

    assert "weekly_rest_hours" not in ficha.values
    assert "annual_overtime_hours" not in ficha.values


def test_the_problem_wording_stays_in_the_chosen_language(tmp_path):
    """Every message goes through gettext, so a test asserting Spanish text
    would break the day the catalogue compiles and one asserting English would
    break under a Spanish locale."""
    ficha = agreements.load(write(tmp_path, with_values(weekly_hours=42)))

    with translation.override("en"):
        problem = agreements.inspect(ficha, TODAY)[0]
        assert "exceeds the legal maximum" in str(problem)
        assert "Art. 34.1 ET" in str(problem)
