"""Shifts: when somebody is expected to work.

ADR-0012 §2 draws the line this module lives on, and it is the easiest one to
get wrong: **a shift says when work can happen; planning says what gets done in
that time.** The Core owns the first. An application that assigns routes reads
availability from here before planning; it does not set it.

Two things a shift is emphatically not:

- **It is not the record.** What somebody was expected to work and what they
  actually worked are different facts, and the second one is the evidence. A
  roster that quietly became the record would be the exact fraud art. 34.9 ET
  exists to prevent. Nothing here ever writes a `Punch`.
- **It is not a decision about compliance.** Rosters that depart from the rest
  rules are reported, never refused --- see `apps.tenants.rules`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TenantOwnedModel


def validate_segments(value) -> None:
    """Segments are `[{"start": "08:00", "end": "16:00"}, ...]`.

    Validated here rather than trusted, because a malformed segment does not
    fail until something tries to compare a roster against a real day --- by
    which time the shift has been on a screen for a week.
    """
    if not isinstance(value, list) or not value:
        raise ValidationError(_("A shift needs at least one time span."))

    for span in value:
        if not isinstance(span, dict) or "start" not in span or "end" not in span:
            raise ValidationError(_("Each span needs a start and an end."))
        try:
            time.fromisoformat(span["start"])
            time.fromisoformat(span["end"])
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Times are written as HH:MM.")) from exc


def span_minutes(span: dict) -> int:
    """Length of one span, in minutes.

    An end earlier than the start means the span runs past midnight --- a night
    shift from 22:00 to 06:00 --- not an error. Treating it as one would make the
    product unusable for exactly the sector with the strictest rules.
    """
    start = time.fromisoformat(span["start"])
    end = time.fromisoformat(span["end"])

    minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    return minutes if minutes > 0 else minutes + 24 * 60


class ShiftPattern(TenantOwnedModel):
    """A reusable shape of a working day: mornings, nights, a split day.

    Kept apart from the assignment so that changing what "morning" means does
    not require touching every day it was ever used on --- and, more to the
    point, so that changing it does **not** silently rewrite the past. An
    assignment copies the spans it was created with.
    """

    name = models.CharField(_("name"), max_length=80)
    segments = models.JSONField(
        _("time spans"),
        validators=[validate_segments],
        help_text=_("Pairs of start and end times. Two of them make a split day."),
    )
    colour = models.CharField(
        _("colour"),
        max_length=7,
        default="#1b5e4a",
        help_text=_("Hex, for the roster. Never the only way a shift is identified."),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("shift pattern")
        verbose_name_plural = _("shift patterns")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="shift_pattern_name_unique_per_company"
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def minutes(self) -> int:
        return sum(span_minutes(span) for span in self.segments)


class Shift(TenantOwnedModel):
    """One person, one day, the hours they are expected to work."""

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name=_("employee"),
    )
    day = models.DateField(_("day"))

    # Where it came from, for the roster. The spans below are the truth: a
    # pattern edited afterwards must not change a day already published.
    pattern = models.ForeignKey(
        ShiftPattern,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts",
        verbose_name=_("pattern"),
    )
    segments = models.JSONField(_("time spans"), validators=[validate_segments])
    note = models.CharField(_("note"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("shift")
        verbose_name_plural = _("shifts")
        ordering = ["day"]
        indexes = [
            models.Index(fields=["tenant", "day"]),
            models.Index(fields=["employee", "day"]),
        ]
        constraints = [
            # One shift per person per day. A split day is several spans inside
            # one shift, not two shifts --- otherwise "what is expected today"
            # has no single answer, and every comparison against the record
            # would have to guess which one it meant.
            models.UniqueConstraint(fields=["employee", "day"], name="one_shift_per_person_per_day")
        ]

    def __str__(self) -> str:
        return f"{self.employee_id} {self.day}"

    def clean(self):
        validate_segments(self.segments)

    @property
    def minutes(self) -> int:
        return sum(span_minutes(span) for span in self.segments)

    @property
    def starts_at(self) -> datetime:
        """First span's start, as a naive local datetime."""
        first = min(self.segments, key=lambda s: s["start"])
        return datetime.combine(self.day, time.fromisoformat(first["start"]))

    @property
    def ends_at(self) -> datetime:
        """Last span's end, rolling into the next day when it wraps midnight."""
        last = max(self.segments, key=lambda s: s["start"])
        end = time.fromisoformat(last["end"])
        start = time.fromisoformat(last["start"])
        finish = datetime.combine(self.day, end)
        return finish + timedelta(days=1) if end <= start else finish

    def overlaps_night(self, night_from: time, night_to: time) -> bool:
        """Whether any span touches the night window.

        Only a hint for the roster. Art. 36.1 ET attaches its limits to somebody
        who **holds the status of night worker** --- three hours daily or a third
        of the annual working day --- not to anybody who happens to work between
        22:00 and 06:00. Getting that backwards was one of the four errors the
        legal review corrected, and it is not going to be reintroduced here.
        """
        for span in self.segments:
            start = time.fromisoformat(span["start"])
            end = time.fromisoformat(span["end"])
            if _touches(start, end, night_from, night_to):
                return True
        return False


def _touches(start: time, end: time, night_from: time, night_to: time) -> bool:
    """Whether a span overlaps the night window.

    Written out rather than compared directly because **either** range can wrap
    midnight: a shift can (22:00-06:00) and so can the window, which is the
    usual case (22:00-06:00) but not the only one --- a company can configure
    02:00-04:00, and the first version of this said yes to every morning shift
    because it assumed the wrap.

    Both are unrolled into minute ranges on a 48-hour line, so a wrap is just a
    range that runs past 1440 instead of a special case.
    """

    def unroll(a: time, b: time) -> list[tuple[int, int]]:
        first_minute = a.hour * 60 + a.minute
        last_minute = b.hour * 60 + b.minute
        if last_minute > first_minute:
            return [(first_minute, last_minute)]
        # Wraps midnight: the piece before, and the piece after.
        return [(first_minute, 1440), (0, last_minute)]

    for span_from, span_to in unroll(start, end):
        for night_start, night_end in unroll(night_from, night_to):
            if span_from < night_end and night_start < span_to:
                return True
    return False


def working_days_between(first: date, last: date):
    """Every day in the range, ends included."""
    current = first
    while current <= last:
        yield current
        current += timedelta(days=1)
