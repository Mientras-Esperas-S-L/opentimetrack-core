"""Corrections to the clock record.

People forget to clock out. Phones run out of battery. Somebody clocks in by
mistake on their day off. A record that cannot accommodate that stops matching
reality, and a record that does not match reality proves nothing.

The rule that governs every line here: **the original is never overwritten.**
A correction adds, replaces or voids, and the previous version stays readable
with who changed it, when and why. That is what the pending royal decree on
digital time records is expected to require --- and it is the only version of
"correcting" that leaves the record still worth something as evidence.

The reason is mandatory. Not a nicety: a correction without a stated reason is
indistinguishable from tampering.
"""

from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.common.models import TenantOwnedModel
from apps.punches.models import Punch, PunchSource, PunchType


class CorrectionKind(models.TextChoices):
    ADD = "ADD", _("Add a missing event")
    MODIFY = "MODIFY", _("Change the time of an event")
    VOID = "VOID", _("Void an event that should not exist")


class CorrectionStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")


class PunchCorrection(TenantOwnedModel):
    """A request to put right something in the record.

    It is a document in its own right, not a flag on the clock event: it holds
    what was asked, by whom, why, who decided and what came of it. Even a
    rejected one stays --- the fact that somebody claimed they worked and was
    told no is itself part of the history.
    """

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="corrections",
        verbose_name=_("employee"),
    )
    kind = models.CharField(_("kind"), max_length=8, choices=CorrectionKind)

    # Empty for ADD: there is nothing to correct, something is missing.
    target = models.ForeignKey(
        Punch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="correction_requests",
        verbose_name=_("event concerned"),
    )

    proposed_type = models.CharField(_("type"), max_length=3, choices=PunchType, blank=True)
    proposed_timestamp = models.DateTimeField(_("proposed time"), null=True, blank=True)

    reason = models.TextField(
        _("reason"),
        help_text=_("Why the record does not match what happened. Required."),
    )

    status = models.CharField(
        _("status"), max_length=8, choices=CorrectionStatus, default=CorrectionStatus.PENDING
    )
    requested_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="corrections_requested",
        verbose_name=_("requested by"),
    )
    resolved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corrections_resolved",
        verbose_name=_("resolved by"),
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolution_note = models.TextField(_("resolution note"), blank=True)

    result = models.ForeignKey(
        Punch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_by_correction",
        verbose_name=_("resulting event"),
    )

    class Meta:
        verbose_name = _("record correction")
        verbose_name_plural = _("record corrections")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["employee", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.employee_id} · {self.get_status_display()}"

    @property
    def is_open(self) -> bool:
        return self.status == CorrectionStatus.PENDING


# ---------------------------------------------------------------------- requests


def request_correction(
    *,
    employee,
    company,
    requested_by,
    kind: str,
    reason: str,
    target: Punch | None = None,
    proposed_type: str = "",
    proposed_timestamp=None,
) -> PunchCorrection:
    """Records the request. Changes nothing in the record until approved."""
    if not reason or not reason.strip():
        raise BusinessRuleError(
            code="reason_required",
            message=_("State why the record does not match what happened."),
        )

    if kind in {CorrectionKind.MODIFY, CorrectionKind.VOID} and target is None:
        raise BusinessRuleError(
            code="target_required",
            message=_("Say which event is being corrected."),
        )

    if kind in {CorrectionKind.ADD, CorrectionKind.MODIFY} and proposed_timestamp is None:
        raise BusinessRuleError(
            code="time_required",
            message=_("Give the time the event actually happened."),
        )

    # A time in the future is not a forgotten clock-out, it is a mistake or an
    # attempt. Either way it does not go in.
    if proposed_timestamp is not None and proposed_timestamp > timezone.now():
        raise BusinessRuleError(
            code="time_in_the_future",
            message=_("The time cannot be in the future."),
        )

    if target is not None and target.employee_id != employee.id:
        raise BusinessRuleError(
            code="not_your_event",
            message=_("That event belongs to somebody else."),
        )

    if kind == CorrectionKind.ADD and not proposed_type:
        raise BusinessRuleError(
            code="type_required",
            message=_("Say whether the missing event is an entry or an exit."),
        )

    return PunchCorrection.objects.create(
        tenant=company,
        employee=employee,
        kind=kind,
        target=target,
        proposed_type=proposed_type or (target.punch_type if target else ""),
        proposed_timestamp=proposed_timestamp,
        reason=reason.strip(),
        requested_by=requested_by,
    )


# --------------------------------------------------------------------- decisions


@transaction.atomic
def approve_correction(correction: PunchCorrection, *, resolved_by, note: str = "") -> Punch | None:
    """Applies the correction, leaving the previous version readable."""
    if not correction.is_open:
        raise BusinessRuleError(
            code="already_resolved",
            message=_("This request has already been resolved."),
        )

    # Set before building anything: the resulting event records who approved it,
    # and "who changed it" is one of the three things the record has to state.
    # Assigning it afterwards left that field empty.
    correction.resolved_by = resolved_by
    correction.resolved_at = timezone.now()

    result: Punch | None = None

    if correction.kind == CorrectionKind.VOID:
        _void(correction.target)

    elif correction.kind == CorrectionKind.ADD:
        result = _create(correction)

    elif correction.kind == CorrectionKind.MODIFY:
        result = _create(correction)
        _void(correction.target, replaced_by=result)

    correction.status = CorrectionStatus.APPROVED
    correction.resolution_note = note
    correction.result = result
    correction.save()

    return result


def reject_correction(correction: PunchCorrection, *, resolved_by, note: str = "") -> None:
    """Turns it down. The request stays: a refused claim is history too."""
    if not correction.is_open:
        raise BusinessRuleError(
            code="already_resolved",
            message=_("This request has already been resolved."),
        )

    correction.status = CorrectionStatus.REJECTED
    correction.resolved_by = resolved_by
    correction.resolved_at = timezone.now()
    correction.resolution_note = note
    correction.save()


def _create(correction: PunchCorrection) -> Punch:
    """Builds the corrected event.

    Marked `ADMIN`, because it was not recorded as it happened. Somebody stated
    afterwards that it happened, and the record says so.
    """
    punch = Punch(
        tenant=correction.tenant,
        employee=correction.employee,
        punch_type=correction.proposed_type,
        timestamp=correction.proposed_timestamp,
        source=PunchSource.ADMIN,
        source_application="",
        recorded_by=correction.resolved_by,
    )
    punch.save()
    return punch


def _void(punch: Punch, replaced_by: Punch | None = None) -> None:
    if punch is None or not punch.is_active:
        return
    punch.is_active = False
    punch.voided_at = timezone.now()
    if replaced_by is not None:
        punch.replaced_by = replaced_by
    punch.save(update_fields=["is_active", "voided_at", "replaced_by"])
