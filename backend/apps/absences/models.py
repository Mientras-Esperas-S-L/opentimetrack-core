"""Leave requests.

Their reason for being here is not HR bookkeeping: approved leave blocks clocking
in, so this is part of the legal record too.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.absences.uploads import validate_extension, validate_size
from apps.common.models import TenantOwnedModel


class AbsenceType(models.TextChoices):
    VACATION = "VACATION", _("Holiday")
    SICK_LEAVE = "SICK_LEAVE", _("Sick leave")
    PERSONAL = "PERSONAL", _("Personal leave")
    OTHER = "OTHER", _("Other")


class AbsenceStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")


class Absence(TenantOwnedModel):
    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="absences",
        verbose_name=_("employee"),
    )
    absence_type = models.CharField(_("type"), max_length=20, choices=AbsenceType)
    start_date = models.DateField(_("from"))
    end_date = models.DateField(_("to"))
    reason = models.TextField(_("reason"), blank=True)

    status = models.CharField(
        _("status"), max_length=10, choices=AbsenceStatus, default=AbsenceStatus.PENDING
    )
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="absences_resolved",
        verbose_name=_("resolved by"),
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)

    justification = models.FileField(
        _("supporting document"),
        upload_to="justifications/%Y/%m/",
        blank=True,
        validators=[validate_extension, validate_size],
        help_text=_(
            "Not available for sick leave: the medical certificate is not stored "
            "here. Since RD 1060/2022 the worker no longer hands it to the "
            "employer --- the INSS sends the data to the company directly."
        ),
    )

    class Meta:
        verbose_name = _("absence")
        verbose_name_plural = _("absences")
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["tenant", "employee", "status"]),
            models.Index(fields=["employee", "status", "start_date", "end_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="absence_ends_after_it_starts",
            ),
            # In the database, not just in a form. A medical certificate is
            # health data (art. 9 GDPR), and the ways into this table are many:
            # an import, a shell, a serializer somebody forgets to validate. A
            # check that lives here cannot be walked around.
            models.CheckConstraint(
                condition=~models.Q(absence_type=AbsenceType.SICK_LEAVE)
                | models.Q(justification=""),
                name="no_medical_certificate_is_stored",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_absence_type_display()} {self.start_date} → {self.end_date}"

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": _("The end date cannot precede the start date.")})

        # Said properly, because "invalid field" would send somebody looking for
        # the bug rather than reading the reason.
        if self.absence_type == AbsenceType.SICK_LEAVE and self.justification:
            raise ValidationError(
                {
                    "justification": _(
                        "The medical certificate is not stored. Recording the absence, "
                        "its dates and its status is enough for working-time purposes, "
                        "and since RD 1060/2022 the worker does not hand the certificate "
                        "to the employer: the INSS sends the data to the company."
                    )
                }
            )

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1
