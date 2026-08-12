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
class NightWork:
    """Night work, and the status it creates.

    Two different things live here and confusing them is the mistake this
    product already made once. **Night time** is a window on the clock, and any
    shift can touch it. **Night worker** is a *status a person holds*, reached
    by working enough of their time inside that window, and it is the status ---
    not the window --- that the limits attach to.

    Somebody who covers one night is not a night worker and none of this applies
    to them. Somebody who is one carries the limits on every day they work,
    including the days they never go near the window.
    """

    #: When the night window opens and closes. Wrapping midnight is the normal
    #: case; `Shift.night_minutes` unrolls both ranges so it needs no handling.
    window_starts_at: time
    window_ends_at: time

    #: Hours inside the window, on a normal day, that make somebody a night
    #: worker. The test is habitual, not "on this one day".
    qualifying_daily_hours: float
    #: The other way to reach the status: this share of the year's working time
    #: at night. Kept as a figure even though the roster cannot see a whole
    #: year --- a company that knows it can declare the status directly.
    qualifying_annual_share: float

    #: The cap on a night worker's day, as an average rather than a ceiling.
    average_daily_hours: float
    average_over_days: int

    overtime_forbidden: bool

    #: Compensating rest instead of a pay supplement is one of the lawful ways
    #: to pay for night work, and the reason a night rota often carries more
    #: days off than a day rota does. Whether it applies here is the collective
    #: agreement's business, not ours; the flag exists so a country that has no
    #: such option can say so.
    rest_may_compensate: bool = False

    citations: dict[str, Citation] = field(default_factory=dict)


@dataclass(frozen=True)
class ShiftWork:
    """Rotating shifts, and the allowances they come with.

    This exists because of a *false positive*, which is worse than a missing
    check: a rotating team changing from nights to mornings cannot take twelve
    hours between the two, and the roster review was reporting every changeover
    as a breach. It is not one --- the law that allows the rotation also allows
    the shorter rest, provided the difference is given back.

    So these are not extra limits. They are the permissions that stop the
    ordinary limits from being applied where they do not belong.
    """

    #: How long somebody may stay on the night shift before the rotation has to
    #: move them off it. Zero means the country sets no such limit.
    max_consecutive_night_weeks: int

    #: The floor the daily rest may drop to on a changeover day, instead of the
    #: ordinary one. The difference is owed, not forgiven.
    changeover_rest_hours: float
    #: The window the owed rest has to be given back within, and the window the
    #: weekly rest may be accumulated over. The same figure in Spain; kept as
    #: one field until a country needs them apart.
    accumulation_weeks: int

    citations: dict[str, Citation] = field(default_factory=dict)


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
    #: The subdivisions that set their own public holidays, as code -> name.
    #: Empty for a country where holidays are national and nothing else, which
    #: is most of them --- so the workplace form simply does not ask.
    #:
    #: Codes rather than names because a name is not an identifier: it gets
    #: renamed, translated and abbreviated, and a calendar keyed by one starts
    #: giving a region somebody else's days.
    regions: dict[str, str] = field(default_factory=dict)
    night: NightWork | None = None
    shifts: ShiftWork | None = None

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
    night=NightWork(
        # Art. 2.3: night time is a period of at least seven hours that must
        # include midnight to 05:00. Member states pick the exact hours; these
        # are the ones the definition guarantees.
        window_starts_at=time(0, 0),
        window_ends_at=time(5, 0),
        # Art. 2.4: a night worker normally works at least three hours of daily
        # working time at night, or a proportion the member state defines.
        qualifying_daily_hours=3,
        qualifying_annual_share=0,
        # Art. 8.a: eight hours per twenty-four on average. The directive does
        # not fix the reference period beyond leaving it to national law.
        average_daily_hours=8,
        average_over_days=14,
        # Art. 8 says nothing about overtime; the ban is a national addition.
        overtime_forbidden=False,
        rest_may_compensate=False,
        citations={
            "definition": Citation("Art. 2.4 Dir. 2003/88/CE"),
            "average": Citation("Art. 8.a Dir. 2003/88/CE"),
        },
    ),
    # Art. 17.3 lets member states derogate from the daily and weekly rest for
    # shift work, but the directive fixes no figures --- so nothing here, and a
    # country that has not written its own gets the ordinary limits.
    shifts=None,
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
