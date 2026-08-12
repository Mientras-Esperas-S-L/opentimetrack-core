"""Working-time rules, as data.

ADR-0012 §3: the Core knows rules configurable per company and per collective
agreement, **not constants scattered through the code**. Each one carries its
legal basis so that anybody reading a warning can tell what is being applied and
why --- and can argue with it.

The values here are **starting points, not truths**. A collective agreement may
improve any of them, and the sector-specific regimes of RD 1561/1995 modify
several outright: driving time, on-call work, shift work handovers. The company
owns its compliance and has its own advisers; this holds the figures it gives us
and says out loud when a roster departs from them.

That is also why nothing here blocks. A product that refused to save a roster
breaking the twelve-hour rest would be unusable in transport, in healthcare
on-call, and in any shift changeover --- all of them lawful under their own
regime. It warns, it says on what basis, and it leaves the decision where it
belongs.
"""

from __future__ import annotations

from datetime import time

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class WorkingTimeRules(BaseModel):
    """The figures a company works to, with the article each one comes from."""

    tenant = models.OneToOneField(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="working_time_rules",
        verbose_name=_("company"),
    )

    weekly_hours = models.DecimalField(
        _("weekly hours"),
        max_digits=4,
        decimal_places=1,
        default=40,
        help_text=_(
            "Art. 34.1 ET: 40 hours a week on average over the reference period. "
            "An ordinary legal maximum; the agreement or the contract may improve it."
        ),
    )
    daily_rest_hours = models.PositiveSmallIntegerField(
        _("rest between working days (hours)"),
        default=12,
        help_text=_(
            "Art. 34.3 ET. RD 1561/1995 modifies it for particular sectors, which "
            "is why departing from it is reported and not prevented."
        ),
    )
    weekly_rest_hours = models.PositiveSmallIntegerField(
        _("weekly rest (hours)"),
        default=36,
        help_text=_(
            "Art. 37.1 ET: a day and a half uninterrupted. It may be accumulated "
            "over periods of up to fourteen days."
        ),
    )
    break_after_hours = models.DecimalField(
        _("a continuous day needs a break after (hours)"),
        max_digits=3,
        decimal_places=1,
        default=6,
        help_text=_("Art. 34.4 ET: fifteen minutes when the continuous day exceeds six hours."),
    )
    break_minutes = models.PositiveSmallIntegerField(_("break (minutes)"), default=15)
    break_counts_as_work = models.BooleanField(
        _("the break counts as working time"),
        default=False,
        help_text=_(
            "Only when the agreement or the contract says so. Assuming it would "
            "overstate the hours worked."
        ),
    )
    annual_overtime_hours = models.PositiveSmallIntegerField(
        _("overtime hours per year"),
        default=80,
        help_text=_("Art. 35.2 ET."),
    )
    night_starts_at = models.TimeField(
        _("night work starts at"),
        default=time(22, 0),
        help_text=_("Art. 36.1 ET: between 22:00 and 06:00."),
    )
    night_ends_at = models.TimeField(_("night work ends at"), default=time(6, 0))
    correction_consent_days = models.PositiveSmallIntegerField(
        _("days to answer a proposed correction"),
        default=7,
        help_text=_(
            "Art. 4.b needs the person's authorisation to change an entry but sets "
            "no deadline for answering. Without one a proposal would hang forever, "
            "so the company sets the window. Past it the change can be applied, "
            "recorded as made without agreement."
        ),
    )
    roster_notice_days = models.PositiveSmallIntegerField(
        _("notice for roster changes (days)"),
        default=5,
        help_text=_(
            "Art. 34.2 ET requires five days' notice for irregular distribution of "
            "the working day. Art. 38.3 ET asks for the holiday calendar two months ahead."
        ),
    )

    class Meta:
        verbose_name = _("working time rules")
        verbose_name_plural = _("working time rules")

    def __str__(self) -> str:
        return f"{self.tenant_id}: {self.weekly_hours} h/week"

    @classmethod
    def for_company(cls, company) -> WorkingTimeRules:
        """The company's rules, creating the defaults the first time.

        Every company has them, so a missing row is a gap in setup rather than a
        meaningful state. Returning defaults beats making every caller handle
        `None` and quietly skip the checks.
        """
        rules, _created = cls.objects.get_or_create(tenant=company)
        return rules
