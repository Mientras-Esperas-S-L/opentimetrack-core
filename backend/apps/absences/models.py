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
    """The family an absence belongs to, and the only taxonomy this app acts on.

    It used to be the whole answer, which is why the eight permits of art. 37.3
    all came out as "personal leave". The specific kind now lives in
    `LeaveType`; this stays because every query asks the family and none of
    them ask the rest, and because it has to outlive a leave type being
    renamed.
    """

    VACATION = "VACATION", _("Holiday")
    SICK_LEAVE = "SICK_LEAVE", _("Sick leave")
    PAID_LEAVE = "PAID_LEAVE", _("Paid leave")
    UNPAID_LEAVE = "UNPAID_LEAVE", _("Unpaid leave")

    # Written before the catalogue existed. Not offered to new absences and not
    # removed either: the rows that carry them have to stay readable, and a
    # record whose reason stops rendering is a record that lost something.
    PERSONAL = "PERSONAL", _("Personal leave")
    OTHER = "OTHER", _("Other")


class LeaveUnit(models.TextChoices):
    """What an entitlement is counted in.

    Four, and they are not interchangeable. Art. 37.3.a says fifteen **calendar**
    days for a wedding; art. 37.9 says hours equivalent to four days a year;
    art. 48 bis says eight weeks. Storing all of them as "days" and hoping would
    lose the weekend on the first and the whole point on the second.
    """

    DAYS_CALENDAR = "DAYS_CALENDAR", _("calendar days")
    DAYS_WORKING = "DAYS_WORKING", _("working days")
    HOURS = "HOURS", _("hours")
    WEEKS = "WEEKS", _("weeks")


class LeavePeriod(models.TextChoices):
    """What the entitlement resets against.

    Fifteen days *per wedding* and four days *per year* are both "four days" in
    a field that does not say which, and a balance built on the wrong one is
    wrong by a whole year.
    """

    EVENT = "EVENT", _("each time")
    DAY = "DAY", _("a day")
    WEEK = "WEEK", _("a week")
    MONTH = "MONTH", _("a month")
    YEAR = "YEAR", _("a year")


class LeaveType(TenantOwnedModel):
    """One kind of leave, as this company grants it.

    A copy, deliberately. The country's catalogue seeds it and then stops being
    read: a collective agreement improves any of these, the company edits its
    own row, and a change of ours never silently rewrites a figure somebody
    agreed to.

    It replaces a four-value enum --- holiday, sick leave, personal leave,
    other --- in which the eight permits of art. 37.3 all landed on "personal
    leave". That is the same as not having them: nobody could count how many had
    been used, check a duration, or answer an inspector.
    """

    #: Stable across renames, and how the seed knows what it already wrote.
    #: Blank for one the company invented, which has no counterpart to match.
    code = models.CharField(_("code"), max_length=40, blank=True)
    name = models.CharField(_("name"), max_length=120)

    family = models.CharField(
        _("kind"),
        max_length=14,
        choices=[
            ("VACATION", _("Holiday")),
            ("SICK_LEAVE", _("Sick leave")),
            ("PAID_LEAVE", _("Paid leave")),
            ("UNPAID_LEAVE", _("Unpaid leave")),
        ],
        default="PAID_LEAVE",
        help_text=_(
            "What it behaves like. Holiday spends the holiday balance; sick leave "
            "never stores a certificate."
        ),
    )

    basis = models.CharField(
        _("legal basis"),
        max_length=60,
        blank=True,
        help_text=_("The article it comes from. Empty for one the agreement gives."),
    )

    #: Null means "el tiempo indispensable": the law grants the time the thing
    #: takes and no more. Those are exactly the ones asked for in hours.
    amount = models.DecimalField(
        _("how much"),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Empty means the indispensable time, with no fixed limit."),
    )
    unit = models.CharField(
        _("in"), max_length=14, choices=LeaveUnit, default=LeaveUnit.DAYS_CALENDAR
    )
    period = models.CharField(
        _("per"), max_length=6, choices=LeavePeriod, default=LeavePeriod.EVENT
    )
    extra_when_travelling = models.DecimalField(
        _("extra if travelling"),
        max_digits=4,
        decimal_places=1,
        default=0,
        help_text=_("Art. 37.3.b bis adds two days when the event needs a journey."),
    )

    paid = models.BooleanField(_("paid"), default=True)
    needs_justification = models.BooleanField(_("needs a supporting document"), default=False)
    note = models.TextField(_("note"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("leave type")
        verbose_name_plural = _("leave types")
        ordering = ["family", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=models.Q(code__gt=""),
                name="one_leave_type_per_code",
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def measured_in_hours(self) -> bool:
        """Whether asking for it in hours is the natural shape.

        The ones with no fixed limit and the ones counted in hours: a medical
        appointment, an exam, the four days of art. 37.9. Used only to decide
        what the form offers first --- any leave can still be part of a day.
        """
        return self.unit == LeaveUnit.HOURS or self.amount is None


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
    #: The specific kind, from the company's catalogue. Null on the rows that
    #: existed before there was a catalogue, and on anything created through an
    #: older client: `absence_type` below still carries the family.
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="absences",
        verbose_name=_("leave type"),
    )
    #: The family. Kept alongside the type rather than read through it because
    #: every query in the product asks this question and none of them ask the
    #: other --- and because it has to survive a leave type being renamed. Set
    #: from the type when there is one, so the two cannot disagree.
    absence_type = models.CharField(_("type"), max_length=20, choices=AbsenceType)

    start_date = models.DateField(_("from"))
    end_date = models.DateField(_("to"))

    # Part of a day. Empty on both means whole days, which is what leave was
    # until now --- and why somebody leaving at eleven with a fever could not be
    # recorded at all: the clock-out stood at 11:00, the day added up to three
    # hours, and nothing said why.
    #
    # Only on a single day. "From Monday at two until Wednesday at eleven" is a
    # shape the arithmetic can express and nobody asks for; refusing it keeps
    # every sum in this app honest about what a partial day is.
    start_time = models.TimeField(_("from (time)"), null=True, blank=True)
    end_time = models.TimeField(_("to (time)"), null=True, blank=True)
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

    @property
    def is_partial(self) -> bool:
        """Part of one day rather than whole days."""
        return self.start_time is not None and self.end_time is not None

    @property
    def hours(self) -> float:
        """How long a partial absence lasts. Zero for a whole-day one.

        Zero and not the length of the working day: how long a whole day is
        depends on the roster, the contract and the person, and answering it
        here would be inventing the one figure this model does not hold.
        """
        if not self.is_partial:
            return 0.0
        started = self.start_time.hour * 60 + self.start_time.minute
        ended = self.end_time.hour * 60 + self.end_time.minute
        return (ended - started) / 60

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": _("The end date cannot precede the start date.")})

        partial = self.start_time is not None or self.end_time is not None
        if partial:
            if self.start_time is None or self.end_time is None:
                raise ValidationError(
                    {"end_time": _("Give both times, or neither: half of a range is not one.")}
                )
            if self.end_time <= self.start_time:
                raise ValidationError({"end_time": _("It ends before it starts.")})
            if self.start_date != self.end_date:
                raise ValidationError(
                    {
                        "end_date": _(
                            "Part of a day is one day. For several days, leave the times "
                            "empty and they count whole."
                        )
                    }
                )

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
