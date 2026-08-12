"""What a country's working-time law has to tell this product.

The rules were right and they were scattered: nine legal citations inside the
roster review, three in the model's `help_text`, six floors as module constants,
and --- the one that mattered most --- six more written by hand into the settings
screen in the frontend, where they could not be translated, could not vary, and
could drift from the backend without anybody noticing.

None of that was wrong for Spain. It was wrong as *structure*: there was no
single place that answered "what does the law say here", so every new rule got
put wherever it was first needed.

This is that place. One `LegalFramework` per country, resolved from
`Tenant.country` --- a field that has existed since the beginning saying it
"selects the applicable legal rules" and that nothing read.

Three things a framework provides, and the third is the one people forget:

**Figures.** What a company starts with before it configures anything.

**Floors.** The minimums nobody may go below. Deliberately not configurable ---
offering a setting whose only use is breaking the law is offering help --- which
is why they live here and not on the settings screen.

**Citations.** Which article each figure comes from. A warning nobody can trace
to an article is a warning nobody can argue with, and the person reading it is
entitled to know what is being applied to them. They belong to the country and
**must never be translated**: "Art. 34.3 ET" rendered in German is still Spanish
law, and it would look correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time


@dataclass(frozen=True)
class Citation:
    """Where a figure comes from, and what it means in words.

    `basis` is the article. `note` is the sentence shown next to the field ---
    what the article actually says, and where it does not apply. Both come from
    the country and neither goes through gettext: translating a citation would
    produce something that reads correctly and points at the wrong law.
    """

    basis: str
    note: str = ""


@dataclass(frozen=True)
class MinorProtections:
    """The floors for workers under eighteen.

    A separate object rather than more entries in `defaults` because these are
    not defaults: no agreement and no company may lower them, so there is
    nothing to configure. What changes between countries is the numbers, not
    that they are fixed.
    """

    max_daily_hours: float
    break_after_hours: float
    break_minutes: int
    weekly_rest_hours: float
    night_work_forbidden: bool
    overtime_forbidden: bool

    #: One per rule, so a warning about a minor can say which article protects
    #: them. Keys match the finding codes in `apps.shifts.services`.
    citations: dict[str, Citation] = field(default_factory=dict)


@dataclass(frozen=True)
class ComplementaryHours:
    """The cap on hours a part-timer may work beyond the contract.

    The one protection that part-time work actually has, and the one nothing
    was checking. Overtime is forbidden on a part-time contract; what is
    allowed instead is this, and if it has no ceiling then the ban on overtime
    buys the worker nothing.

    `max_share` is a fraction of the contracted hours, over the reference
    period. A collective agreement may raise it, which is why it lands on
    `WorkingTimeRules` as a figure the company sets rather than staying here.
    """

    max_share: float
    #: How the period is counted: the cap is on the total, not week by week.
    period_months: int = 1
    citation: Citation = field(default_factory=lambda: Citation(""))


@dataclass(frozen=True)
class LegalFramework:
    """One country's answer to "what does the law say here"."""

    #: ISO 3166-1 alpha-2, matching `Tenant.country`.
    country: str
    #: For a human reading a settings screen or an error.
    name: str

    #: Starting values for `WorkingTimeRules`. Keys are field names on that
    #: model; anything missing keeps the model's own default.
    defaults: dict[str, object]

    #: Field name -> where it comes from. Served with the rules so the screen
    #: shows the citation instead of carrying its own copy.
    citations: dict[str, Citation]

    #: Finding code -> where it comes from, for the roster review.
    finding_citations: dict[str, Citation]

    minors: MinorProtections
    complementary: ComplementaryHours | None = None

    def citation(self, key: str) -> Citation:
        """The citation for a field, or an empty one.

        Empty rather than an error on purpose: a country that has no rule about
        something should produce a warning with no citation, not a crash. The
        interface already handles a blank basis --- the roster's leave clash has
        always had one, because it is a planning mistake and not a breach.
        """
        return self.citations.get(key) or Citation(basis="")

    def finding_citation(self, code: str) -> Citation:
        return self.finding_citations.get(code) or Citation(basis="")


#: What a country gets when it says nothing. Not a country: the floors of the
#: EU working time directive (2003/88/EC), which every member state has to
#: reach or improve.
#:
#: It exists so an unrecognised `country` degrades to something defensible
#: rather than to Spain's figures under another flag --- which would be worse
#: than useless, because it would look configured.
DIRECTIVE = LegalFramework(
    country="",
    name="Directiva 2003/88/CE",
    defaults={
        # Art. 6.b: 48 hours a week including overtime, averaged. Higher than
        # any member state's own limit, which is the point of a floor.
        "weekly_hours": 48,
        "daily_rest_hours": 11,  # art. 3
        "weekly_rest_hours": 35,  # art. 5: 24 h plus the daily 11
        "break_after_hours": 6,  # art. 4, without saying how long
        "night_starts_at": time(0, 0),
        "night_ends_at": time(5, 0),  # art. 2.4: the period includes midnight to 05:00
    },
    citations={
        "weekly_hours": Citation("Art. 6.b Dir. 2003/88/CE"),
        "daily_rest_hours": Citation("Art. 3 Dir. 2003/88/CE"),
        "weekly_rest_hours": Citation("Art. 5 Dir. 2003/88/CE"),
        "break_after_hours": Citation("Art. 4 Dir. 2003/88/CE"),
    },
    finding_citations={},
    # Nothing here: complementary hours are a national construction and the
    # directive does not know them. A country without them checks nothing.
    complementary=None,
    minors=MinorProtections(
        # Directive 94/33/EC on the protection of young people at work.
        max_daily_hours=8,
        break_after_hours=4.5,
        break_minutes=30,
        weekly_rest_hours=48,
        night_work_forbidden=True,
        overtime_forbidden=False,
        citations={},
    ),
)
