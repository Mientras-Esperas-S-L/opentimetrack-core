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

from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.common.transitions import claim
from apps.common.four_eyes import refuse_self_decision
from apps.common.models import TenantOwnedModel
from apps.punches.models import Punch, PunchSource, PunchType


class CorrectionKind(models.TextChoices):
    ADD = "ADD", _("Add a missing event")
    MODIFY = "MODIFY", _("Change the time of an event")
    VOID = "VOID", _("Void an event that should not exist")


class CorrectionStatus(models.TextChoices):
    """Where a correction is, and it is not a simple yes or no.

    Art. 4.b of the pending royal decree requires **both** the company and the
    person concerned to authorise a change to an entry. Read carelessly that
    sounds like a veto for the worker, and the last sentence of the paragraph
    says it is not: «en ausencia de acuerdo, la empresa reflejará en el registro
    la modificación y la persona trabajadora su discrepancia».

    So the change goes in even without agreement. What the norm guarantees is
    **contradiction, not blocking**: the record must be able to hold two
    accounts of the same day and say which is whose. That is the difference
    between a register that hides a disagreement and one that carries it.
    """

    PENDING = "PENDING", _("Waiting for the company")
    AWAITING_EMPLOYEE = "AWAITING_EMPLOYEE", _("Waiting for the person concerned")
    APPROVED = "APPROVED", _("Applied with agreement")
    DISPUTED = "DISPUTED", _("Applied without agreement, with the disagreement recorded")
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
        _("status"), max_length=20, choices=CorrectionStatus, default=CorrectionStatus.PENDING
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

    # ------------------------------------------------------------- art. 4.b

    # Three states, not two. `None` means the person has not spoken yet, which
    # is different from having said no, and the difference decides whether the
    # company may go ahead.
    employee_agreed = models.BooleanField(
        _("the person agrees"),
        null=True,
        blank=True,
        help_text=_(
            "Art. 4.b: a change needs the authorisation of the company and of the "
            "person concerned. Empty means they have not answered."
        ),
    )
    employee_responded_at = models.DateTimeField(_("answered at"), null=True, blank=True)
    employee_dissent = models.TextField(
        _("the person's account"),
        blank=True,
        help_text=_(
            "Their version, kept beside the change and never instead of it. Art. 4.b "
            "lets the company record the modification and the person their "
            "disagreement, so the record holds both."
        ),
    )

    representatives_notified_at = models.DateTimeField(
        _("workers' representatives informed at"), null=True, blank=True
    )
    representatives_notice = models.CharField(
        _("how they were informed"),
        max_length=200,
        blank=True,
        help_text=_(
            "Art. 4.b requires informing the workers' legal representation when "
            "there is disagreement. If the company has not said who they are, that "
            "is recorded here rather than passed over in silence."
        ),
    )

    applied_without_agreement = models.BooleanField(
        _("applied without agreement"),
        default=False,
        help_text=_(
            "The change went in anyway, which art. 4.b allows. It travels to the "
            "inspection report: a reader has to be able to tell a correction both "
            "parties accepted from one imposed over an objection."
        ),
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


# ------------------------------------------------------- art. 4.b, the two sides


def propose_correction(
    *,
    employee,
    company,
    proposed_by,
    kind: str,
    reason: str,
    target: Punch | None = None,
    proposed_type: str = "",
    proposed_timestamp=None,
) -> PunchCorrection:
    """The company proposing a change to somebody's record.

    Distinct from `request_correction`, and the distinction is the whole point
    of art. 4.b. When the person asks and the company approves, both have
    authorised it and the change goes straight in. When the company proposes,
    one authorisation is missing --- so the change waits, and the person is
    asked.

    It does not wait forever. `apply_without_agreement` exists because the
    article says so: silence or refusal does not stop the company, it obliges
    the record to carry both accounts.
    """
    correction = request_correction(
        employee=employee,
        company=company,
        requested_by=proposed_by,
        kind=kind,
        reason=reason,
        target=target,
        proposed_type=proposed_type,
        proposed_timestamp=proposed_timestamp,
    )
    correction.status = CorrectionStatus.AWAITING_EMPLOYEE
    correction.save(update_fields=["status", "updated_at"])

    transaction.on_commit(lambda: notify_employee_of_proposal(correction))
    return correction


@transaction.atomic
def accept_correction(correction: PunchCorrection, *, employee) -> Punch | None:
    """The person agrees. Both authorisations are in, so it applies."""
    correction = _must_be_awaiting(correction)
    if correction.employee_id != employee.id:
        raise BusinessRuleError(
            code="not_your_record",
            message=_("Only the person concerned can accept a change to their record."),
        )

    correction.employee_agreed = True
    correction.employee_responded_at = timezone.now()
    correction.status = CorrectionStatus.PENDING
    correction.save(
        update_fields=["employee_agreed", "employee_responded_at", "status", "updated_at"]
    )
    # Back to the ordinary path: the company that proposed it now applies it.
    return approve_correction(correction, resolved_by=correction.requested_by)


@transaction.atomic
def dispute_correction(correction: PunchCorrection, *, employee, account: str) -> PunchCorrection:
    """The person disagrees, and says why.

    Nothing is applied here. The disagreement is recorded, the workers'
    representatives are informed --- art. 4.b requires it --- and the company
    decides whether to go ahead. Their account is mandatory: a disagreement with
    no content is not something a reader can weigh against the change.
    """
    correction = _must_be_awaiting(correction)
    if correction.employee_id != employee.id:
        raise BusinessRuleError(
            code="not_your_record",
            message=_("Only the person concerned can disagree with a change to their record."),
        )
    if not account or not account.strip():
        raise BusinessRuleError(
            code="account_required",
            message=_("Say what you think happened. It is recorded beside the change."),
        )

    correction.employee_agreed = False
    correction.employee_responded_at = timezone.now()
    correction.employee_dissent = account.strip()
    correction.save(
        update_fields=[
            "employee_agreed",
            "employee_responded_at",
            "employee_dissent",
            "updated_at",
        ]
    )

    _inform_representatives(correction)
    return correction


@transaction.atomic
def apply_without_agreement(correction: PunchCorrection, *, resolved_by) -> Punch | None:
    """The company goes ahead anyway, which art. 4.b permits.

    Permitted, and never silent. The entry is marked, the person's account
    travels with it, and both reach the inspection report. A reader has to be
    able to tell a correction both parties accepted from one imposed over an
    objection --- otherwise the record would be hiding the very disagreement the
    article exists to preserve.

    Two ways to get here: the person disagreed, or they did not answer within
    the window the company configured.
    """
    correction = _must_be_awaiting(correction)

    silent = correction.employee_agreed is None
    if silent and not _consent_window_has_passed(correction):
        raise BusinessRuleError(
            code="still_within_the_window",
            message=_("The person still has time to answer."),
        )

    if silent:
        # Said out loud in the record: not answering is not agreeing, and an
        # entry that failed to distinguish them would overstate the consent.
        correction.employee_dissent = str(
            _("No answer within the period given. Applied without their agreement.")
        )
        _inform_representatives(correction)

    correction.applied_without_agreement = True
    correction.save(update_fields=["applied_without_agreement", "employee_dissent", "updated_at"])

    # El paso a «pendiente» se **escribe**, no se finge en memoria. Antes esta
    # línea era `correction.status = PENDING  # so approve_correction accepts
    # it` y funcionaba porque `approve_correction` miraba el objeto que se le
    # pasaba. Ahora vuelve a leer la fila bloqueándola ---que es lo que impide
    # que dos responsables la resuelvan a la vez--- y un estado inventado en
    # memoria ya no la engaña.
    #
    # Escribirlo además es más honesto: entre estas dos líneas la corrección
    # está de verdad pendiente de aplicarse, y si algo revienta en medio, la
    # transacción de la función deshace las dos.
    correction.status = CorrectionStatus.PENDING
    correction.save(update_fields=["status", "updated_at"])

    result = approve_correction(correction, resolved_by=resolved_by)

    correction.status = CorrectionStatus.DISPUTED
    correction.save(update_fields=["status", "updated_at"])
    return result


def _must_be_awaiting(correction: PunchCorrection) -> PunchCorrection:
    """Bloquea y exige que siga esperando a la persona. Devuelve la fila fresca.

    Aquí la carrera es entre la persona y el plazo: puede aceptar en el mismo
    instante en que un responsable aplica el cambio sin acuerdo por haberse
    agotado la ventana del art. 4.b, y entonces el registro diría a la vez que
    hubo acuerdo y que no lo hubo. Cuál de las dos cosas pasó es exactamente lo
    que hay que poder responder después.
    """
    return claim(
        PunchCorrection,
        correction.pk,
        desde=CorrectionStatus.AWAITING_EMPLOYEE,
        code="not_awaiting_the_employee",
        message=_("This change is not waiting for the person concerned."),
    )


def _consent_window_has_passed(correction: PunchCorrection) -> bool:
    from apps.tenants.rules import WorkingTimeRules

    rules = WorkingTimeRules.for_company(correction.tenant)
    deadline = correction.created_at + timedelta(days=rules.correction_consent_days)
    return timezone.now() >= deadline


def _inform_representatives(correction: PunchCorrection) -> None:
    """Art. 4.b: on disagreement, the workers' representatives are informed.

    The company has to have said who they are. If it has not, that is written
    down instead of being passed over --- claiming to have informed nobody would
    be worse than admitting the gap, and the company needs to know the
    obligation is unmet.
    """
    from apps.users.models import User

    representatives = User.objects.filter(
        tenant=correction.tenant, is_worker_representative=True, is_active=True
    )

    correction.representatives_notified_at = timezone.now()
    if representatives.exists():
        correction.representatives_notice = str(
            _("Informed: %(names)s")
            % {"names": ", ".join(r.get_full_name() or r.email for r in representatives)[:150]}
        )
    else:
        correction.representatives_notice = str(
            _("No workers' representatives are on record. Art. 4.b requires informing them.")
        )
    correction.save(
        update_fields=["representatives_notified_at", "representatives_notice", "updated_at"]
    )


# --------------------------------------------------------------------- decisions


@transaction.atomic
def _note_alone(note: str) -> str:
    """Marks a decision nobody else could have taken.

    It goes in the resolution note rather than a new column because that is
    what already travels to the inspection report: a reader has to be able to
    tell a change a second person approved from one the same person filed and
    resolved, and a silent allowance would erase exactly that difference.
    """
    mark = str(
        _(
            "Resolved by the same person who is the subject: no other manager or administrator "
            "exists in the company."
        )
    )
    return f"{note}\n\n{mark}".strip() if note else mark


def approve_correction(correction: PunchCorrection, *, resolved_by, note: str = "") -> Punch | None:
    """Applies the correction, leaving the previous version readable."""
    # Bloqueando la fila, no mirando la copia en memoria: dos responsables
    # pulsando a la vez pasaban los dos. Ver `apps.common.transitions`.
    correction = claim(PunchCorrection, correction.pk, desde=CorrectionStatus.PENDING)

    # A manager filing a correction on their own record and approving it was
    # two clicks, both theirs. See apps/common/four_eyes.py for why this is
    # refused rather than merely logged, and why the sole-administrator case
    # still goes through.
    alone = refuse_self_decision(
        subject=correction.employee,
        decider=resolved_by,
        company=correction.tenant,
        what=_("a change to the working-time record"),
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
    correction.resolution_note = _note_alone(note) if alone else note
    correction.result = result
    correction.save()

    # After committing: the person must not learn of a change that then rolls back.
    transaction.on_commit(lambda: notify_employee(correction))

    return result


def reject_correction(correction: PunchCorrection, *, resolved_by, note: str = "") -> None:
    """Turns it down. The request stays: a refused claim is history too."""
    correction = claim(PunchCorrection, correction.pk, desde=CorrectionStatus.PENDING)

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


def notify_employee_of_proposal(correction: PunchCorrection) -> None:
    """Tells the person their employer wants to change their record.

    The message asks rather than announces, because at this point nothing has
    changed and their answer decides what happens next. It says what the window
    is: a proposal that could sit unanswered forever would be a change made by
    exhaustion.
    """
    import logging

    from django.conf import settings
    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    from apps.tenants.rules import WorkingTimeRules

    log = logging.getLogger(__name__)
    if not correction.employee.email:
        return

    try:
        rules = WorkingTimeRules.for_company(correction.tenant)
        body = render_to_string(
            "emails/record_change_proposed.txt",
            {
                "first_name": correction.employee.first_name,
                "company": correction.tenant.name,
                "summary": _summarise(correction),
                "reason": correction.reason,
                "proposed_by": correction.requested_by.get_full_name(),
                "days": rules.correction_consent_days,
            },
        )
        send_mail(
            subject=_("Your employer proposes a change to your working time record"),
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[correction.employee.email],
            fail_silently=True,
        )
    except Exception:
        log.exception(
            "Could not tell %s about correction %s", correction.employee_id, correction.pk
        )


def _summarise(correction: PunchCorrection) -> str:
    zone = correction.tenant.tzinfo
    when = correction.proposed_timestamp or (
        correction.target.timestamp if correction.target else None
    )
    local = when.astimezone(zone).strftime("%d/%m/%Y %H:%M") if when else ""
    summaries = {
        CorrectionKind.ADD: _("Add an entry: %(kind)s at %(when)s."),
        CorrectionKind.MODIFY: _("Change the time of an entry to %(when)s."),
        CorrectionKind.VOID: _("Void the entry recorded at %(when)s."),
    }
    return summaries[correction.kind] % {
        "when": local,
        "kind": correction.get_proposed_type_display() if correction.proposed_type else "",
    }


def notify_employee(correction: PunchCorrection) -> None:
    """Tells the person their record changed.

    Recommended by the legal review of 11/08/2026: a correction is not made
    conditional on their agreement, but it cannot happen without them finding
    out. Silence would turn a legitimate correction into something that looks
    like it was done behind their back.

    Nobody is notified of their own approved request: they already know.

    Nothing here may raise. It runs after the transaction commits, so the
    correction is already saved: letting an exception through would return an
    error to somebody whose change did go in, and they would try again.
    """
    import logging

    from django.conf import settings
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.formats import date_format

    log = logging.getLogger(__name__)

    if correction.resolved_by_id == correction.employee_id:
        return
    if not correction.employee.email:
        return

    try:
        _send_change_notice(correction, settings, send_mail, render_to_string, date_format)
    except Exception:
        # Worth a full trace: silence here means people stop being told their
        # record changed, and nobody would notice.
        log.exception("Could not notify %s of correction %s", correction.employee_id, correction.pk)


def _send_change_notice(correction, settings, send_mail, render_to_string, date_format) -> None:
    zone = correction.tenant.tzinfo
    when = correction.proposed_timestamp or (
        correction.target.timestamp if correction.target else None
    )
    local = when.astimezone(zone).strftime("%d/%m/%Y %H:%M") if when else ""

    summaries = {
        CorrectionKind.ADD: _("An entry was added: %(kind)s at %(when)s."),
        CorrectionKind.MODIFY: _("The time of an entry was changed to %(when)s."),
        CorrectionKind.VOID: _("An entry recorded at %(when)s was voided."),
    }
    summary = summaries[correction.kind] % {
        "when": local,
        "kind": correction.get_proposed_type_display() if correction.proposed_type else "",
    }

    body = render_to_string(
        "emails/record_changed.txt",
        {
            "first_name": correction.employee.first_name,
            "company": correction.tenant.name,
            "summary": summary,
            "reason": correction.reason,
            "resolver": correction.resolved_by.get_full_name() if correction.resolved_by else "",
            "decided_on": date_format(
                correction.resolved_at.astimezone(zone), "SHORT_DATETIME_FORMAT"
            )
            if correction.resolved_at
            else "",
        },
    )

    send_mail(
        subject=_("Your working time record has changed"),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[correction.employee.email],
        fail_silently=True,  # a failed notice must not undo an approved correction
    )
