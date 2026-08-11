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


class PunchType(models.TextChoices):
    IN = "IN", _("Clock in")
    OUT = "OUT", _("Clock out")


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


class Punch(TenantOwnedModel):
    """A single clock event."""

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,  # a person with clock events is never deleted
        related_name="punches",
        verbose_name=_("employee"),
    )
    punch_type = models.CharField(_("type"), max_length=3, choices=PunchType)

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

    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    device_id = models.CharField(_("device"), max_length=100, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=255, blank=True)

    hash_integrity = models.CharField(_("integrity hash"), max_length=64, editable=False)

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

        Deliberately excludes the mutable fields (`is_active`, `voided_at`): the
        hash proves the event was recorded as stated, and voiding it is a later
        act that leaves its own trail.
        """
        payload = "|".join(
            [
                str(self.employee_id),
                str(self.tenant_id),
                self.timestamp.isoformat(),
                self.punch_type,
                self.ip_address or "",
                self.source,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        return self.hash_integrity == self.compute_hash()

    def save(self, *args, **kwargs):
        if not self.hash_integrity:
            self.hash_integrity = self.compute_hash()
        super().save(*args, **kwargs)

    # -------------------------------------------------------------------- helpers

    @property
    def was_delegated(self) -> bool:
        """True when somebody other than the employee produced the record."""
        return self.source in {PunchSource.DELEGATED, PunchSource.ADMIN, PunchSource.IMPORT}
