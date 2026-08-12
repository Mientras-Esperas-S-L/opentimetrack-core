"""The audit trail. Append-only, and enforced by the database.

ADR-0003 asked for this and it was never built, which is the worst combination:
the security documentation described a guarantee the code did not provide.

What it is for. `PunchCorrection` already records who changed a clock event and
why, so that part was covered. What nobody could answer was the other half:
**who read somebody else's record**, who changed a role, who exported an
inspection report, who revoked an application's credential. A system that
proves working time but cannot say who has been looking at it is only half a
record.

Three decisions worth stating.

**Append-only means the database refuses.** Overriding `save()` and `delete()`
stops honest mistakes; it does nothing against a bug, a shell, or an
administrator with a psql prompt. A rule that only holds while the application
behaves is not a rule. The migration installs a trigger that raises on UPDATE
and DELETE, so the guarantee survives the code.

**Not everything gets logged.** A row per request would be unreadable within a
week, and an audit trail nobody reads is theatre. What goes in is reading
*another person's* data and changing anything that affects the record or who
can reach it. Reading your own leaves no trace: you are entitled to it, and
logging it would only bury the entries that matter.

**No timestamps but one.** `BaseModel` brings `updated_at`, which in a table
that cannot be updated is a contradiction that invites somebody to trust it.
This model does not inherit it.
"""

from __future__ import annotations

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditAction(models.TextChoices):
    """What happened. Kept as a closed list so the trail can be searched.

    Free text would make every query a `LIKE` and every rename a silent gap in
    the history.
    """

    # Somebody looked at data that was not their own.
    RECORD_VIEWED = "RECORD_VIEWED", _("Read somebody else's record")
    REPORT_EXPORTED = "REPORT_EXPORTED", _("Exported a working time report")
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED", _("Downloaded a supporting document")

    # Somebody changed the record.
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED", _("Requested a correction")
    CORRECTION_APPROVED = "CORRECTION_APPROVED", _("Approved a correction")
    CORRECTION_REJECTED = "CORRECTION_REJECTED", _("Rejected a correction")
    PUNCH_VOIDED = "PUNCH_VOIDED", _("Voided a clock event")
    CORRECTION_DISPUTED = "CORRECTION_DISPUTED", _("Disagreed with a proposed change")
    CORRECTION_IMPOSED = "CORRECTION_IMPOSED", _("Applied a change without agreement")

    # Somebody decided about time off.
    ABSENCE_APPROVED = "ABSENCE_APPROVED", _("Approved leave")
    ABSENCE_REJECTED = "ABSENCE_REJECTED", _("Rejected leave")

    # Somebody changed who can do what.
    PERSON_CREATED = "PERSON_CREATED", _("Added a person")
    PERSON_UPDATED = "PERSON_UPDATED", _("Changed a person")
    PERSON_DEACTIVATED = "PERSON_DEACTIVATED", _("Deactivated a person")
    PERSON_REACTIVATED = "PERSON_REACTIVATED", _("Reactivated a person")
    ROLE_CHANGED = "ROLE_CHANGED", _("Changed a role")
    # Sending it hands somebody a way into the company's records, so it is a
    # change to who can do what and not a piece of housekeeping.
    INVITATION_SENT = "INVITATION_SENT", _("Sent a link to set a password")

    # Somebody changed the rules the record is measured against.
    SETTINGS_CHANGED = "SETTINGS_CHANGED", _("Changed company settings")
    RULES_CHANGED = "RULES_CHANGED", _("Changed working time rules")

    # Applications acting on the company's behalf.
    APPLICATION_CREATED = "APPLICATION_CREATED", _("Registered an application")
    APPLICATION_REVOKED = "APPLICATION_REVOKED", _("Revoked an application credential")

    # Housekeeping that removes data.
    METADATA_PURGED = "METADATA_PURGED", _("Purged security metadata")

    # Failed sign-ins are deliberately absent. ATOMIC_REQUESTS is on and DRF
    # rolls the transaction back when it returns an error, so an entry written
    # during a failing request never lands. They go to the application log
    # instead --- see SignInView._record_failed_attempt.


class AuditLog(models.Model):
    """One thing that happened, and who did it.

    Not a `TenantOwnedModel` on purpose: that base brings `updated_at` and a
    manager built for mutable data. The company is still here as a column and
    the queryset is still scoped --- see `AuditLogViewSet` --- but the
    inheritance would carry promises this table cannot keep.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    at = models.DateTimeField(_("when"), auto_now_add=True, db_index=True)

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="audit_entries",
        verbose_name=_("company"),
    )

    # SET_NULL, not CASCADE: deleting a person must never erase what they did.
    actor = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
        verbose_name=_("who"),
    )
    # Their name as it was, copied. The foreign key can go null and a person can
    # be renamed; an entry that reads "somebody, at some point" is worthless.
    actor_label = models.CharField(_("who (as recorded)"), max_length=160, blank=True)

    action = models.CharField(_("action"), max_length=32, choices=AuditAction, db_index=True)

    # What it was about. Loose on purpose --- a UUID and a readable label ---
    # rather than a generic foreign key: the trail has to survive the target
    # being deleted, and a dangling reference is worse than a copied name.
    target_type = models.CharField(_("type"), max_length=32, blank=True)
    target_id = models.UUIDField(_("identifier"), null=True, blank=True, db_index=True)
    target_label = models.CharField(_("what (as recorded)"), max_length=200, blank=True)

    # {field: [before, after]}. Only fields that matter: ADR-0003 warns about
    # personal data ending up in here, and the trail is kept for four years.
    changes = models.JSONField(_("changes"), default=dict, blank=True)
    note = models.CharField(_("note"), max_length=300, blank=True)

    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)

    class Meta:
        verbose_name = _("audit entry")
        verbose_name_plural = _("audit trail")
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["tenant", "-at"]),
            models.Index(fields=["tenant", "action", "-at"]),
            models.Index(fields=["actor", "-at"]),
        ]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.action} {self.actor_label}"

    def save(self, *args, **kwargs):
        """Inserts only.

        The database refuses too, and that is the guarantee that counts. This
        turns the mistake into a clear error at the line that caused it instead
        of a database exception three frames away.
        """
        if self._state.adding is False:
            raise RuntimeError(
                "The audit trail is append-only: an entry cannot be modified. "
                "If something needs correcting, record a new entry saying so."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(
            "The audit trail is append-only: entries are not deleted. "
            "Retention is handled by the documented policy, not by hand."
        )
