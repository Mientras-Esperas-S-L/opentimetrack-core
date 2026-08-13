"""Reading collective-agreement fichas, and refusing the ones that look wrong.

A ficha is a YAML file under `agreements/` holding the working-time figures of
one collective agreement, each with the article it comes from. The format lives
outside the backend on purpose: it is meant to be written by somebody's labour
adviser, not by us, and a format that only works inside one product never
becomes a format.

Two layers of checking, and the second is the one that earns its keep:

**The schema** (`agreements/schema.json`) checks the shape. Required fields,
a fourteen-digit REGCON, a `basis` on every value.

**The floors below** check the figures against the Estatuto. Art. 3.3 ET works
by *norma mínima*: an agreement may improve a legal minimum and may not worsen
it. So a ficha claiming a 42-hour week is one of two things --- a transcription
error, or an agreement that does not hold --- and in both cases somebody needs
to look before a company runs its rosters against it.

Nothing here is a legal opinion. It is arithmetic against published articles,
and it says which article, so it can be argued with.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

AGREEMENTS_DIR = Path(settings.AGREEMENTS_DIR)

#: Ours, next to the fichas we publish.
BUNDLED_SCHEMA = Path(settings.BASE_DIR).parent / "agreements" / "schema.json"


def schema_path() -> Path:
    """The schema to validate against.

    A deployment pointing `AGREEMENTS_DIR` at its adviser's own directory may
    ship a copy of the schema there; otherwise ours applies. Looking in the
    fichas' directory first is what keeps a company from being stuck on our
    version of the format.
    """
    theirs = AGREEMENTS_DIR / "schema.json"
    return theirs if theirs.is_file() else BUNDLED_SCHEMA


#: A ficha that has not been looked at in this long is still valid --- agreements
#: run for years --- but it is worth saying so. This is our judgement, not a rule.
STALE_AFTER = dt.timedelta(days=730)


class FichaError(Exception):
    """The file could not be read, parsed, or validated against the schema."""


@dataclass(slots=True)
class Problem:
    """Something wrong with a ficha, with the article that makes it wrong."""

    field: str
    message: str
    basis: str = ""
    fatal: bool = True

    def __str__(self) -> str:
        where = f"{self.field}: " if self.field else ""
        because = f" ({self.basis})" if self.basis else ""
        return f"{where}{self.message}{because}"


@dataclass(slots=True)
class Ficha:
    """A parsed ficha. `values` flattens `working_time` to plain numbers."""

    path: Path
    data: dict[str, Any]
    values: dict[str, Any] = field(default_factory=dict)

    @property
    def defers(self) -> dict[str, dict[str, str]]:
        """Parameters the agreement hands to a lower-scope one.

        Not the same as saying nothing. Silence means the statutory minimum
        applies and the company is done; a deferral means the figure exists
        somewhere else and somebody has to go and find it. A framework
        agreement can defer nearly everything, and then its ficha is almost
        entirely this section.
        """
        return self.data.get("defers", {})

    @property
    def name(self) -> str:
        return self.data["agreement"]["name"]

    @property
    def regcon(self) -> str:
        return self.data["agreement"]["regcon"]

    @property
    def verified_on(self) -> dt.date:
        return _as_date(self.data["provenance"]["verified_on"])

    def basis_for(self, key: str) -> str:
        entry = self.data.get("working_time", {}).get(key)
        return entry.get("basis", "") if entry else ""

    def note_for(self, key: str) -> str:
        entry = self.data.get("working_time", {}).get(key)
        return entry.get("note", "") if entry else ""


# ------------------------------------------------------------------ reading


def load(path: Path) -> Ficha:
    """Read one ficha and validate its shape. Raises `FichaError`."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FichaError(str(exc)) from exc

    if not isinstance(raw, dict):
        raise FichaError(_("the file does not contain a ficha"))

    # YAML reads an unquoted 99002995011981 as a number, and the schema would
    # only say it is not a string. Worse, a provincial code beginning with a
    # zero --- 01 is Álava --- loses it on the way in, and the ficha would then
    # name a different agreement. Say what to do instead of what is wrong.
    if isinstance(raw.get("agreement", {}).get("regcon"), int):
        raise FichaError(
            _(
                "agreement.regcon: put it in quotes. Unquoted it is read as a number "
                "and a code beginning with zero loses it"
            )
        )

    try:
        jsonschema.validate(_dates_as_text(raw), _schema())
    except jsonschema.ValidationError as exc:
        where = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise FichaError(f"{where}: {exc.message}") from exc

    # A figure cannot be both fixed and handed to somebody else. When a ficha
    # says both, one of the two readings is wrong, and guessing which would be
    # picking a number on the reader's behalf. The schema cannot see this: it
    # would need to enumerate every key twice and the error would be unreadable.
    if both := sorted(set(raw.get("working_time", {})) & set(raw.get("defers", {}))):
        raise FichaError(
            _(
                "%(keys)s: fixed and deferred at the same time; one of the two readings "
                "of the agreement is wrong"
            )
            % {"keys": ", ".join(both)}
        )

    values = {key: entry["value"] for key, entry in raw.get("working_time", {}).items()}
    return Ficha(path=path, data=raw, values=values)


def load_all(directory: Path | None = None) -> list[Ficha]:
    """Every ficha under the directory. The template is skipped by its name."""
    root = directory or AGREEMENTS_DIR
    found = []
    for path in sorted(root.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        found.append(load(path))
    return found


_SCHEMA_CACHE: dict[str, Any] = {}


def _schema() -> dict[str, Any]:
    if not _SCHEMA_CACHE:
        import json

        _SCHEMA_CACHE.update(json.loads(schema_path().read_text(encoding="utf-8")))
    return _SCHEMA_CACHE


def _as_date(value: Any) -> dt.date:
    """YAML gives a date for an unquoted `2026-01-30` and a string if quoted."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def _dates_as_text(value: Any) -> Any:
    """Turn YAML's date objects back into ISO strings, for the schema's sake.

    JSON Schema has no date type: it checks a string against `format: date`.
    YAML does have one and applies it to any unquoted `2026-01-30`, so a ficha
    written the obvious way would fail validation on a technicality. Requiring
    quotes would be a rule whose only purpose is to accommodate our validator.
    """
    if isinstance(value, dict):
        return {k: _dates_as_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dates_as_text(v) for v in value]
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


# ------------------------------------------------------------------ the floors
#
# Each entry: the key, the comparison, the legal figure, and the article. Read
# as "the ficha's value may not be <worse than> this".


def inspect(ficha: Ficha, today: dt.date | None = None) -> list[Problem]:
    """Everything questionable about a ficha, fatal or not."""
    # `timezone.localdate()` y no `dt.date.today()`: el segundo da la fecha UTC
    # del contenedor, y entre medianoche y las dos de la madrugada un convenio
    # verificado hoy se marcaría como «con fecha futura». Aquí no hay empresa en
    # juego ---una ficha de convenio no es de nadie--- así que vale la zona
    # activa de Django. Ver `apps/common/clock.py`.
    today = today or timezone.localdate()
    problems: list[Problem] = []
    got = ficha.values

    # -- dates -------------------------------------------------------------

    if ficha.verified_on > today:
        problems.append(
            Problem(
                "provenance.verified_on",
                _("dated in the future: nobody can have checked it yet"),
            )
        )
    elif today - ficha.verified_on > STALE_AFTER:
        problems.append(
            Problem(
                "provenance.verified_on",
                _("last checked on %(day)s, over two years ago")
                % {"day": ficha.verified_on.isoformat()},
                fatal=False,
            )
        )

    valid_until = ficha.data["agreement"].get("valid_until")
    if valid_until and _as_date(valid_until) < today:
        problems.append(
            Problem(
                "agreement.valid_until",
                _(
                    "expired on %(day)s; a lapsed agreement that looks current is worse "
                    "than no ficha at all"
                )
                % {"day": _as_date(valid_until).isoformat()},
            )
        )

    valid_from = _as_date(ficha.data["agreement"]["valid_from"])
    if valid_until and _as_date(valid_until) < valid_from:
        problems.append(Problem("agreement.valid_until", _("earlier than valid_from")))

    # -- working time, against the Estatuto ---------------------------------
    #
    # Art. 3.3 ET: an agreement improves the legal minimum or it does not hold.
    # Anything failing here is a transcription to re-read, not a setting.

    if (weekly := got.get("weekly_hours")) is not None and weekly > 40:
        problems.append(
            Problem(
                "weekly_hours",
                _("%(got)s exceeds the legal maximum of 40") % {"got": weekly},
                "Art. 34.1 ET",
            )
        )

    # 40 h a week over 52 weeks, less the 30 days of art. 38.1: about 1826 h.
    if (annual := got.get("annual_hours")) is not None and annual > 1826:
        problems.append(
            Problem(
                "annual_hours",
                _("%(got)s is above the ceiling that 40 hours a week works out to (1826)")
                % {"got": annual},
                "Art. 34.1 ET",
            )
        )

    if (daily := got.get("max_daily_hours")) is not None and daily > 9:
        problems.append(
            Problem(
                "max_daily_hours",
                _(
                    "%(got)s exceeds nine ordinary hours; over that needs the agreement to "
                    "distribute the day irregularly, which is a company fact and not a "
                    "property of the agreement"
                )
                % {"got": daily},
                "Art. 34.3 ET",
                fatal=False,
            )
        )

    if (rest := got.get("daily_rest_hours")) is not None and rest < 12:
        problems.append(
            Problem(
                "daily_rest_hours",
                _(
                    "%(got)s is below the twelve-hour floor. RD 1561/1995 lowers it for "
                    "particular sectors; if that is the case here, say so in the note"
                )
                % {"got": rest},
                "Art. 34.3 ET",
                fatal=False,
            )
        )

    if (weekly_rest := got.get("weekly_rest_hours")) is not None and weekly_rest < 36:
        problems.append(
            Problem(
                "weekly_rest_hours",
                _("%(got)s is below a day and a half uninterrupted") % {"got": weekly_rest},
                "Art. 37.1 ET",
            )
        )

    if (overtime := got.get("annual_overtime_hours")) is not None and overtime > 80:
        problems.append(
            Problem(
                "annual_overtime_hours",
                _("%(got)s exceeds the eighty-hour cap") % {"got": overtime},
                "Art. 35.2 ET",
            )
        )

    if (leave := got.get("annual_leave_days")) is not None:
        working_days = got.get("leave_days_are_working_days", False)
        # Art. 38.1 fixes thirty calendar days. Expressed in working days for a
        # five-day week that is twenty-two, which is why agreements that switch
        # units land on 22 or 23 rather than on 30.
        floor, unit = (22, _("working days")) if working_days else (30, _("calendar days"))
        if leave < floor:
            problems.append(
                Problem(
                    "annual_leave_days",
                    _("%(got)s %(unit)s is below the minimum of %(floor)s")
                    % {"got": leave, "unit": unit, "floor": floor},
                    "Art. 38.1 ET",
                )
            )

    # -- the trap that is not an error --------------------------------------
    #
    # Worth saying out loud because it is the one figure where the system's
    # default and the agreement's text quietly disagree, and the difference
    # accrues in the employer's favour: fifteen minutes a day is around 55
    # hours a year.

    if got.get("break_counts_as_work") and not got.get("break_minutes"):
        problems.append(
            Problem(
                "break_counts_as_work",
                _("the break counts as working time but its length is not transcribed"),
                fatal=False,
            )
        )

    return problems


def check_all(fichas: list[Ficha], today: dt.date | None = None) -> dict[Path, list[Problem]]:
    """`inspect` over the lot, plus what only shows up across files."""
    results = {f.path: inspect(f, today) for f in fichas}

    seen: dict[str, Path] = {}
    for ficha in fichas:
        first = seen.get(ficha.regcon)
        if first is not None:
            results[ficha.path].append(
                Problem(
                    "agreement.regcon",
                    _(
                        "same code as %(other)s: the REGCON is what tells two similar "
                        "agreements apart"
                    )
                    % {"other": first.name},
                )
            )
        else:
            seen[ficha.regcon] = ficha.path

    return results


# ------------------------------------------------------- applying one to a company

#: Ficha key -> (which object, which field). Two targets because the working
#: figures live on the rules and the holiday entitlement on the company itself.
#:
#: Deliberately not every key. A ficha may carry figures the system does not yet
#: know how to compare, and leaving them out --- visibly --- beats pretending
#: they were applied. Two live examples: `annual_hours`, because we compare
#: weeks and the agreement fixes a year; and `max_daily_hours`, because for
#: adults nothing checks it yet (only the under-eighteen floor is enforced).
APPLICABLE = {
    "weekly_hours": ("rules", "weekly_hours"),
    "daily_rest_hours": ("rules", "daily_rest_hours"),
    "weekly_rest_hours": ("rules", "weekly_rest_hours"),
    "break_after_hours": ("rules", "break_after_hours"),
    "break_minutes": ("rules", "break_minutes"),
    "break_counts_as_work": ("rules", "break_counts_as_work"),
    "annual_overtime_hours": ("rules", "annual_overtime_hours"),
    "annual_leave_days": ("tenant", "annual_leave_days"),
    "leave_year_start_month": ("tenant", "leave_year_start_month"),
    # Applied rather than only read. It used to be a qualifier: the ficha said
    # which unit its figure was in, the loader refused to write a calendar-day
    # figure because the field counted working days, and there was nowhere to
    # record the answer. Now the company holds the unit, so both go in together
    # and the two never disagree.
    "leave_days_are_working_days": ("tenant", "leave_days_are_working_days"),
}

#: Keys that only qualify another key and are never written anywhere.
QUALIFIERS: set[str] = set()


@dataclass(slots=True)
class Applied:
    """What a ficha changed, and what it could not."""

    changed: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    unchanged: list[str] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)
    refused: dict[str, str] = field(default_factory=dict)


def apply_to_rules(ficha: Ficha, rules, *, commit: bool = True) -> Applied:
    """Write a ficha's figures onto a company's rules and onto the company.

    Returns what moved so the caller can show it before or after. A ficha is not
    a silent import: somebody is going to run their rosters against these
    numbers, and they should see which ones changed.
    """
    result = Applied()
    tenant = rules.tenant
    targets = {"rules": rules, "tenant": tenant}
    touched: dict[str, list[str]] = {"rules": [], "tenant": []}

    for key, value in ficha.values.items():
        if key in QUALIFIERS:
            continue

        where = APPLICABLE.get(key)
        if where is None:
            result.not_applicable.append(key)
            continue

        if (refusal := _refuse(key, ficha)) is not None:
            result.refused[key] = refusal
            continue

        which, attribute = where
        obj = targets[which]
        current = getattr(obj, attribute)

        # DecimalField gives Decimal, the YAML gives int or float.
        if type(current)(value) == current:
            result.unchanged.append(key)
            continue

        result.changed[key] = (current, value)
        if commit:
            setattr(obj, attribute, value)
            touched[which].append(attribute)

    if commit:
        for which, fields in touched.items():
            if fields:
                targets[which].save(update_fields=[*fields, "updated_at"])

    return result


def _refuse(key: str, ficha: Ficha) -> str | None:
    """Reasons to leave a value alone even though there is a field for it.

    Empty for now, and kept rather than deleted. It held one rule --- a ficha in
    calendar days could not be written into a field that counted working days,
    so the conversion was left to a human --- which stopped being true once the
    unit became something the company records. The next figure that only makes
    sense with a qualifier will want this back.
    """
    return None
