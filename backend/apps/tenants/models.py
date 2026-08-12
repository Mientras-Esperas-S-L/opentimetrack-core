"""The company: unit of isolation for the whole system."""

from __future__ import annotations

import zoneinfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


def validate_time_zone(value: str) -> None:
    """Accept any IANA zone, not a closed list.

    Spain alone spans two zones (Europe/Madrid and Atlantic/Canary), so a fixed
    list would be wrong even for the first market.
    """
    if value not in zoneinfo.available_timezones():
        raise ValidationError(
            _("%(value)s is not a valid IANA time zone."),
            params={"value": value},
        )


def default_time_zone() -> str:
    return settings.DEFAULT_TENANT_TIME_ZONE


class Tenant(BaseModel):
    """A company. No data query may cross this boundary."""

    name = models.CharField(_("legal name"), max_length=255)

    # Deliberately free-form: it holds a Spanish CIF/NIF today, but also a VAT
    # number, an EIN or whatever the jurisdiction uses. Country-specific checks
    # belong in the serializer, where the error can be explained.
    tax_id = models.CharField(
        _("tax identifier"),
        max_length=32,
        unique=True,
        help_text=_("Company tax number (CIF/NIF, VAT, EIN…)."),
    )
    country = models.CharField(
        _("country"),
        max_length=2,
        default="ES",
        help_text=_("ISO 3166-1 alpha-2 code. Selects the applicable legal rules."),
    )
    time_zone = models.CharField(
        _("time zone"),
        max_length=64,
        default=default_time_zone,
        validators=[validate_time_zone],
        help_text=_("IANA name. Storage is always UTC; this only affects display."),
    )
    language = models.CharField(
        _("language"),
        max_length=10,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        help_text=_(
            "Language the company works in. A person can override it for "
            "themselves; the browser's setting is only used when neither is set."
        ),
    )

    # Holiday entitlement comes from the collective agreement, so both of these
    # are parameters the company sets, not truths the system knows.
    annual_leave_days = models.PositiveSmallIntegerField(
        _("annual leave days"),
        default=22,
        help_text=_(
            "Working days of holiday per reference period. Art. 38 ET sets a floor "
            "of 30 calendar days; the agreement may give more. An individual "
            "employee can be given a different figure."
        ),
    )
    leave_year_start_month = models.PositiveSmallIntegerField(
        _("reference period starts in"),
        default=1,
        choices=[(m, m) for m in range(1, 13)],
        help_text=_(
            "Month the holiday reference period begins. 1 = calendar year. The "
            "period is not necessarily the calendar year: the agreement decides."
        ),
    )

    payroll_period = models.CharField(
        _("pay period"),
        max_length=16,
        default="MONTHLY",
        choices=[
            ("MONTHLY", _("Monthly")),
            ("FORTNIGHTLY", _("Every two weeks")),
            ("WEEKLY", _("Weekly")),
        ],
        help_text=_(
            "Art. 6.1: a copy of the summary for this period goes out with the "
            "payslip. Not necessarily a calendar month --- art. 29.1 ET only caps "
            "the interval at one."
        ),
    )

    record_retention_years = models.PositiveSmallIntegerField(
        _("record retention (years)"),
        default=4,
        help_text=_(
            "How long clock events are kept. Four years is the floor set by "
            "art. 34.9 ET; a longer period needs its own justification, since "
            "keeping data because it might be useful is not a basis."
        ),
    )
    security_metadata_retention_days = models.PositiveSmallIntegerField(
        _("security metadata retention (days)"),
        default=365,
        help_text=_(
            "How long the IP address, device and user agent of each event are "
            "kept. They serve to spot anomalies, not to prove working time: "
            "purging them leaves the record intact."
        ),
    )

    settings = models.JSONField(_("settings"), default=dict, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.tax_id})"

    @property
    def tzinfo(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(self.time_zone)


class TenantLimits(BaseModel):
    """Usage limits for a company.

    The Core knows nothing about plans or prices: it only enforces the limits it
    has configured. Unset means unlimited, which is what a self-hosted install
    gets by default.

    A managed service writes here through the API when a subscription changes.
    Keeping the limit as local data is what allows enforcing it synchronously
    without asking anyone over the network.
    """

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="limits",
        verbose_name=_("company"),
    )
    max_employees = models.IntegerField(_("maximum employees"), null=True, blank=True)
    max_admins = models.IntegerField(_("maximum administrators"), null=True, blank=True)
    max_storage_mb = models.IntegerField(_("maximum storage (MB)"), null=True, blank=True)
    features = models.JSONField(_("enabled features"), default=dict, blank=True)

    class Meta:
        verbose_name = _("company limits")
        verbose_name_plural = _("company limits")

    def __str__(self) -> str:
        return f"Limits for {self.tenant.name}"

    def allows_another_employee(self, current: int) -> bool:
        return self.max_employees is None or current < self.max_employees

    def allows_another_admin(self, current: int) -> bool:
        return self.max_admins is None or current < self.max_admins


# Applications live in their own module for readability, but Django needs them
# imported here to discover the models.
from apps.tenants.applications import (  # noqa: E402
    Application,
    ApplicationCredential,
    ApplicationScope,
)
from apps.tenants.rules import WorkingTimeRules  # noqa: E402

__all__ = [
    "Application",
    "ApplicationCredential",
    "ApplicationScope",
    "Tenant",
    "TenantLimits",
    "WorkingTimeRules",
]
