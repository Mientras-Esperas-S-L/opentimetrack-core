"""Clock events: the legally meaningful record.

Three rules govern this module, and none of them is negotiable:

1. **The server owns the time.** The timestamp is never taken from the client.
   A client clock can be wrong, or set on purpose.
2. **Nothing is deleted.** Correcting a mistake voids the original and writes a
   new one, so the history stays intact.
3. **Every event records how it got here.** A record created by the person from
   their own phone and one created by a third-party application on their behalf
   are both valid, but they are not the same thing, and an inspector is entitled
   to tell them apart.
"""

from __future__ import annotations

import hashlib

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TenantOwnedModel

#: Version of the hash payload used for events recorded from now on.
#:
#: Never rewrite a stored hash to match a new payload: that is exactly the
#: manipulation the hash exists to make visible. Add a version instead, and let
#: old events keep verifying under the rules they were recorded with.
CURRENT_HASH_VERSION = 3


class PunchType(models.TextChoices):
    IN = "IN", _("Clock in")
    OUT = "OUT", _("Clock out")


class PunchInterval(models.TextChoices):
    """What the event opens or closes.

    Art. 3 of the pending royal decree asks for the start and end of four
    different things, not just the working day: the day itself (3.c), each
    break that is **not** effective working time (3.d), waiting and on-call
    time when it does not count either (3.g), and interruptions of the right to
    disconnect (3.h).

    Modelled as a kind of interval rather than as more punch types, because
    every one of them is a pair. `IN`/`OUT` keeps meaning "opens" and "closes";
    this says what. Eight punch types would have been the same thing with the
    combinations multiplied out and a rule nobody remembers about which pair
    with which.
    """

    WORK = "WORK", _("Working day")
    BREAK = "BREAK", _("Break that is not working time")
    STANDBY = "STANDBY", _("Waiting or on-call time")
    DISCONNECTION = "DISCONNECTION", _("Interruption of the right to disconnect")


class WorkMode(models.TextChoices):
    """Art. 3.e: on site or remote, for the day **or part of it**.

    Part of it is why this lives on the event and not on the person: somebody
    who comes in at midday after a morning at home has two spans with different
    answers, and a single field on the contract could not say so.
    """

    ONSITE = "ONSITE", _("On site")
    REMOTE = "REMOTE", _("Remote")


class HoursNature(models.TextChoices):
    """Art. 3.f: ordinary, overtime, or complementary.

    Complementary hours are the part-time equivalent of overtime (art. 12.5
    ET) and are counted separately by law, so they are not folded in here.
    """

    ORDINARY = "ORDINARY", _("Ordinary")
    OVERTIME = "OVERTIME", _("Overtime")
    COMPLEMENTARY = "COMPLEMENTARY", _("Complementary")


class OvertimeSettlement(models.TextChoices):
    """Art. 3.f again: overtime has to say how it will be settled."""

    REST = "REST", _("Compensated with rest")
    PAID = "PAID", _("Paid")


class FlexibilityMeasure(models.TextChoices):
    """Art. 3.i: hours worked under an arrangement, saying which one.

    Left as a short closed list rather than free text so it can be counted and
    reported. `OTHER` exists because the list of arrangements a collective
    agreement can invent is not closed, and forcing a wrong label would be
    worse than admitting the gap.
    """

    NONE = "", _("None")
    CARE = "CARE", _("Care or family reasons (art. 34.8 ET)")
    FLEXITIME = "FLEXITIME", _("Flexible hours")
    IRREGULAR = "IRREGULAR", _("Irregular distribution (art. 34.2 ET)")
    OTHER = "OTHER", _("Another arrangement")


class PunchSource(models.TextChoices):
    """How the record reached the system.

    This is not telemetry: it is part of the evidence. `DELEGATED` means an
    application acted on behalf of the person rather than the person acting
    themselves, and that difference belongs in the inspection report.
    """

    WEB = "WEB", _("Web panel")
    MOBILE = "MOBILE", _("Mobile app")
    APPLICATION = "APPLICATION", _("External application, employee identity")
    DELEGATED = "DELEGATED", _("External application, on behalf of the employee")
    TERMINAL = "TERMINAL", _("Shared terminal")
    ADMIN = "ADMIN", _("Manual correction by an administrator")
    IMPORT = "IMPORT", _("Data import")


class PunchTrigger(models.TextChoices):
    """What caused a punch to be recorded, as opposed to who produced it.

    Orthogonal to `source`: a punch can come from the mobile app (`source`)
    because a geofence fired (`trigger`), or from an external application
    (`source`) because a sensor did (`trigger`). The two answer different
    questions, and both belong in the evidence.

    `MANUAL` is the ordinary case --- a person pressed the button. The rest are
    the assisted ones: a real signal of presence made the punch instead of the
    person remembering. Which signal, and its proof, lives in `evidence`.
    """

    MANUAL = "MANUAL", _("A person pressed the button")
    GEOFENCE = "GEOFENCE", _("Entering or leaving a worksite")
    NETWORK = "NETWORK", _("Joining or leaving a work network")
    SENSOR = "SENSOR", _("Another system's presence event")


class Punch(TenantOwnedModel):
    """A single clock event."""

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,  # a person with clock events is never deleted
        related_name="punches",
        verbose_name=_("employee"),
    )
    punch_type = models.CharField(_("type"), max_length=3, choices=PunchType)

    # What the event opens or closes. Everything recorded before this field
    # existed was a working day, which is why that is the default: back-filling
    # it as anything else would rewrite the meaning of the existing record.
    interval = models.CharField(
        _("interval"), max_length=16, choices=PunchInterval, default=PunchInterval.WORK
    )

    # Art. 3.e, 3.f and 3.i. Carried on the opening event of each span, because
    # they describe the span: the same day can be remote in the morning and on
    # site in the afternoon, ordinary until six and overtime after.
    work_mode = models.CharField(_("mode"), max_length=8, choices=WorkMode, default=WorkMode.ONSITE)
    hours_nature = models.CharField(
        _("nature of the hours"),
        max_length=16,
        choices=HoursNature,
        default=HoursNature.ORDINARY,
    )
    overtime_settlement = models.CharField(
        _("how the overtime is settled"),
        max_length=8,
        choices=OvertimeSettlement,
        blank=True,
        help_text=_("Required for overtime: art. 3.f asks whether it is rested or paid."),
    )
    force_majeure = models.BooleanField(
        _("to prevent or repair urgent damage"),
        default=False,
        help_text=_(
            "Art. 35.3 ET: hours worked to prevent or repair accidents and other "
            "extraordinary and urgent damage. They do not count towards the "
            "annual overtime limit, so they have to be distinguishable."
        ),
    )
    flexibility_measure = models.CharField(
        _("arrangement"),
        max_length=16,
        choices=FlexibilityMeasure,
        blank=True,
        default="",
    )

    # Server time, in UTC. Never supplied by the client.
    timestamp = models.DateTimeField(_("timestamp"), db_index=True)

    # Where it came from, for the audit trail.
    source = models.CharField(
        _("source"), max_length=16, choices=PunchSource, default=PunchSource.WEB
    )
    source_application = models.CharField(
        _("source application"),
        max_length=100,
        blank=True,
        help_text=_("Which application recorded it, when it was not this one."),
    )
    recorded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="punches_recorded",
        verbose_name=_("recorded by"),
        help_text=_("Set when somebody other than the employee created the record."),
    )

    # Security metadata, not part of the legal record. Kept to spot anomalies
    # and disputed events, purged on its own schedule --- see
    # `purge_security_metadata`. The working-time record survives it.
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    device_id = models.CharField(_("device"), max_length=100, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=255, blank=True)

    # How the punch was triggered, and the proof. Assisted clock-in --- a
    # geofence, a network, another system's sensor --- records a real presence
    # event instead of relying on somebody remembering to press the button.
    #
    # These sit with the IP and the device on purpose, NOT in the integrity
    # hash: geolocation is sensitive, minimisable, and metadata about *how* the
    # event was captured rather than the working-time fact itself. Binding it
    # into the hash would make it impossible to purge, which is exactly the
    # mistake `_hash_v1` made with the IP. `purge_security_metadata` clears it
    # with the rest.
    trigger = models.CharField(
        _("trigger"), max_length=8, choices=PunchTrigger, default=PunchTrigger.MANUAL
    )
    evidence = models.JSONField(
        _("trigger evidence"),
        default=dict,
        blank=True,
        help_text=_("What proves the trigger: coordinates, a network name, an external event id."),
    )

    hash_integrity = models.CharField(_("integrity hash"), max_length=64, editable=False)
    hash_version = models.PositiveSmallIntegerField(
        _("hash version"), default=CURRENT_HASH_VERSION, editable=False
    )

    # Soft delete: a voided event stays readable and auditable.
    is_active = models.BooleanField(_("valid"), default=True)
    voided_at = models.DateTimeField(_("voided at"), null=True, blank=True)
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaces",
        verbose_name=_("replaced by"),
    )

    class Meta:
        verbose_name = _("clock event")
        verbose_name_plural = _("clock events")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["tenant", "employee", "-timestamp"]),
            models.Index(fields=["tenant", "-timestamp"]),
            models.Index(fields=["employee", "is_active", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_punch_type_display()} {self.employee_id} @ {self.timestamp:%Y-%m-%d %H:%M}"
        )

    # ------------------------------------------------------------------ integrity

    def compute_hash(self) -> str:
        """Fingerprint of the facts that must not change afterwards.

        What it is worth: it detects accidental alteration and inconsistent
        restores. It is **not** proof of immutability --- whoever can write to
        this table can recompute it. External sealing is a separate matter.

        Deliberately excludes the mutable fields (`is_active`, `voided_at`): the
        hash proves the event was recorded as stated, and voiding it is a later
        act that leaves its own trail.

        Each event is verified under the version it was recorded with, so a
        change here never invalidates what is already stored.
        """
        if self.hash_version == 1:
            return self._hash_v1()
        if self.hash_version == 2:
            return self._hash_v2()
        return self._hash_v3()

    def _hash_v1(self) -> str:
        """Original payload. Included the IP, which turned out to be a mistake.

        A record hashed this way cannot have its IP purged without failing
        verification for good, so `purge_security_metadata` leaves it alone.
        """
        return self._digest(
            str(self.employee_id),
            str(self.tenant_id),
            self.timestamp.isoformat(),
            self.punch_type,
            self.ip_address or "",
            self.source,
        )

    def _hash_v2(self) -> str:
        """Attribution instead of network metadata.

        The IP comes out: it is kept for security, is subject to minimisation,
        and does not belong to the working-time record --- binding it into the
        hash made deleting it impossible. What goes in is who the event is
        about, when, of what kind, and **who produced it**, which is the part a
        delegated punch needs pinned down.
        """
        return self._digest(
            str(self.employee_id),
            str(self.tenant_id),
            self.timestamp.isoformat(),
            self.punch_type,
            self.source,
            self.source_application,
            str(self.recorded_by_id or ""),
        )

    def _hash_v3(self) -> str:
        """Adds what art. 3 of the pending decree makes part of the entry.

        Whether a span is the working day or an uncounted break, whether it was
        remote, whether the hours were ordinary or overtime and how that
        overtime settles: all of it is now the record, not metadata about it. An
        entry whose nature could be changed afterwards without breaking its seal
        would let somebody turn overtime into a break with nothing to show for
        it.
        """
        return self._digest(
            str(self.employee_id),
            str(self.tenant_id),
            self.timestamp.isoformat(),
            self.punch_type,
            self.source,
            self.source_application,
            str(self.recorded_by_id or ""),
            self.interval,
            self.work_mode,
            self.hours_nature,
            self.overtime_settlement,
            "1" if self.force_majeure else "0",
            self.flexibility_measure,
        )

    @staticmethod
    def _digest(*parts: str) -> str:
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        return self.hash_integrity == self.compute_hash()

    def save(self, *args, **kwargs):
        if not self.hash_integrity:
            self.hash_version = CURRENT_HASH_VERSION
            self.hash_integrity = self.compute_hash()
        super().save(*args, **kwargs)

    # -------------------------------------------------------------------- helpers

    @property
    def was_delegated(self) -> bool:
        """True when somebody other than the employee produced the record."""
        return self.source in {PunchSource.DELEGATED, PunchSource.ADMIN, PunchSource.IMPORT}


class PunchReminder(TenantOwnedModel):
    """Proof a reminder already went out, so it goes out once.

    Not the reminder's content, its *having happened*: the scheduled job runs
    every few minutes, and without this it would send the same nudge on every
    tick until the person finally clocked. One row per person, day and kind is
    the whole model.
    """

    class Kind(models.TextChoices):
        CLOCK_IN = "CLOCK_IN", _("Missing entry")
        CLOCK_OUT = "CLOCK_OUT", _("Day left open")

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="punch_reminders",
        verbose_name=_("employee"),
    )
    day = models.DateField(_("day"))
    kind = models.CharField(_("kind"), max_length=10, choices=Kind)
    sent_at = models.DateTimeField(_("sent at"), auto_now_add=True)

    class Meta:
        verbose_name = _("clock reminder")
        verbose_name_plural = _("clock reminders")
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "day", "kind"], name="one_reminder_per_person_day_kind"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.employee_id} {self.day}"


class OvertimeDecision(TenantOwnedModel):
    """A manager's ruling on a day's overtime: authorised, and how it settles.

    The record captures the real time; this is the layer on top that says which
    of it is *authorised* overtime and whether it is paid or given back in rest.
    It never alters a punch --- the day stays faithful --- it classifies it,
    which is exactly how a company handles overtime without either hiding it or
    letting it be inflated.

    `minutes` is the amount ruled on, kept because a later correction can change
    how much overtime a day really held: a decision about thirty minutes must
    not silently stand as authorising two hours, so the day reopens for review
    when the figure moves.
    """

    class Status(models.TextChoices):
        AUTHORISED = "AUTHORISED", _("Authorised")
        REJECTED = "REJECTED", _("Not authorised")

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="overtime_decisions",
        verbose_name=_("employee"),
    )
    day = models.DateField(_("day"))
    minutes = models.PositiveIntegerField(_("overtime minutes ruled on"))
    status = models.CharField(_("status"), max_length=10, choices=Status)
    #: How authorised overtime settles (art. 35.1): paid, or compensated with
    #: rest within four months. Blank when the overtime was not authorised ---
    #: there is nothing to settle.
    settlement = models.CharField(
        _("settlement"), max_length=4, choices=OvertimeSettlement, blank=True
    )
    note = models.CharField(_("note"), max_length=200, blank=True)

    decided_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overtime_decisions_made",
        verbose_name=_("decided by"),
    )
    #: True when the sole administrator ruled on their own overtime, since there
    #: was no second person to pass it through. Recorded rather than hidden,
    #: like the same case for corrections and leave.
    decided_alone = models.BooleanField(_("decided alone"), default=False)
    decided_at = models.DateTimeField(_("decided at"), auto_now=True)

    class Meta:
        verbose_name = _("overtime decision")
        verbose_name_plural = _("overtime decisions")
        ordering = ["-day"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "day"], name="one_overtime_decision_per_person_day"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_status_display()} {self.employee_id} {self.day}"

    def as_summary(self) -> dict:
        """The prior ruling, for a screen re-opening a day whose figure moved."""
        return {
            "status": self.status,
            "minutes": self.minutes,
            "settlement": self.settlement,
            "decided_by": self.decided_by.get_full_name() if self.decided_by else "",
        }


# Corrections live in their own module for readability; Django needs them
# imported here to discover the model.
from apps.punches.corrections import (  # noqa: E402
    CorrectionKind,
    CorrectionStatus,
    PunchCorrection,
)

__all__ = [
    "CorrectionKind",
    "CorrectionStatus",
    "OvertimeDecision",
    "Punch",
    "PunchCorrection",
    "PunchReminder",
    "PunchSource",
    "PunchTrigger",
    "PunchType",
]
