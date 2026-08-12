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
        # The article and the explanation live in `apps.legal`, keyed by
        # country, and reach the screen through the API. Repeating them here
        # would be a second copy to keep in step --- which is what the frontend
        # was already doing, wrongly.
        help_text=_("Hours a week. See the citation served with the rules."),
    )
    daily_rest_hours = models.PositiveSmallIntegerField(
        _("rest between working days (hours)"),
        default=12,
        help_text=_("Hours between the end of a working day and the start of the next."),
    )
    weekly_rest_hours = models.PositiveSmallIntegerField(
        _("weekly rest (hours)"),
        default=36,
        help_text=_("Uninterrupted hours of weekly rest."),
    )
    break_after_hours = models.DecimalField(
        _("a continuous day needs a break after (hours)"),
        max_digits=3,
        decimal_places=1,
        default=6,
        help_text=_("A continuous day longer than this is owed a break."),
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
        help_text=_("Overtime hours allowed per year."),
    )
    night_starts_at = models.TimeField(
        _("night work starts at"),
        default=time(22, 0),
        help_text=_("Start of the night window."),
    )
    night_ends_at = models.TimeField(_("night work ends at"), default=time(6, 0))
    correction_consent_days = models.PositiveSmallIntegerField(
        _("days to answer a proposed correction"),
        default=7,
        help_text=_(
            "Days to answer a proposed change before the company may apply it "
            "anyway, recorded as made without agreement."
        ),
    )
    complementary_hours_share = models.PositiveSmallIntegerField(
        _("complementary hours, max % of the contract"),
        default=30,
        help_text=_(
            "Cap on hours a part-time contract may work beyond what was agreed, "
            "as a percentage of it."
        ),
    )
    roster_notice_days = models.PositiveSmallIntegerField(
        _("notice for roster changes (days)"),
        default=5,
        help_text=_("Days of notice before a roster change."),
    )

    class Meta:
        verbose_name = _("working time rules")
        verbose_name_plural = _("working time rules")

    def __str__(self) -> str:
        return f"{self.tenant_id}: {self.weekly_hours} h/week"

    @classmethod
    def for_company(cls, company) -> WorkingTimeRules:
        """The company's rules, creating them the first time from its country.

        Every company has them, so a missing row is a gap in setup rather than a
        meaningful state. Returning defaults beats making every caller handle
        `None` and quietly skip the checks.

        The figures come from `apps.legal`, keyed on `Tenant.country`. The field
        defaults below stay as Spain's --- they are what a row created by a
        migration or a fixture gets --- but a company created through the product
        starts on its own country's law.
        """
        from apps.legal import for_company as framework_for

        framework = framework_for(company)
        rules, _created = cls.objects.get_or_create(tenant=company, defaults=framework.defaults)
        return rules


# ---------------------------------------------------------------- under eighteen
#
# They used to be six constants here, and the reasoning for keeping them out of
# `WorkingTimeRules` was right and still is: no agreement can lower them, so a
# setting for them would be a setting whose only use is breaking the law.
#
# What was wrong is that they were **Spain's** floors written as the product's.
# They now live in `apps.legal.es`, next to the articles that impose them, and a
# company in another country gets that country's --- or, failing that, the
# directive's.
#
# These names are kept as a thin forwarding layer so the existing call sites and
# their tests read the same. New code should ask the framework directly:
#
#     from apps.legal import for_company
#     for_company(company).minors.max_daily_hours

from apps.legal import DIRECTIVE  # noqa: E402
from apps.legal.es import ESPANA  # noqa: E402

MINOR_MAX_DAILY_HOURS = ESPANA.minors.max_daily_hours
MINOR_BREAK_AFTER_HOURS = ESPANA.minors.break_after_hours
MINOR_BREAK_MINUTES = ESPANA.minors.break_minutes
MINOR_WEEKLY_REST_HOURS = ESPANA.minors.weekly_rest_hours
MINOR_NIGHT_WORK_FORBIDDEN = ESPANA.minors.night_work_forbidden
MINOR_OVERTIME_FORBIDDEN = ESPANA.minors.overtime_forbidden

__all__ = [
    "DIRECTIVE",
    "MINOR_BREAK_AFTER_HOURS",
    "MINOR_BREAK_MINUTES",
    "MINOR_MAX_DAILY_HOURS",
    "MINOR_NIGHT_WORK_FORBIDDEN",
    "MINOR_OVERTIME_FORBIDDEN",
    "MINOR_WEEKLY_REST_HOURS",
    "WorkingTimeRules",
]
