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

__all__ = [
    "Application",
    "ApplicationCredential",
    "ApplicationScope",
    "Tenant",
    "TenantLimits",
]
