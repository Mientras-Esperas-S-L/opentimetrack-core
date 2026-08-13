"""Where a person can be reached, beyond their inbox.

Email always works and needs nothing registered. A browser notification needs
the browser to hand over a subscription first --- an address at the vendor's
push service, plus the two keys that let the server encrypt for that browser
and nobody else. That is what this stores.

Nothing here is part of the working-time record. A subscription can be deleted
at any moment, by the person or by the server when the vendor says the address
is dead, and losing every one of them costs a courtesy, never a punch.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TenantOwnedModel


class PushSubscription(TenantOwnedModel):
    """One browser, on one device, that agreed to be notified.

    Keyed by `endpoint`, which is what the vendor hands out and what identifies
    the browser: the same person on a phone and a laptop is two rows, and
    re-subscribing on the same browser returns the same endpoint, so it updates
    rather than piling up.
    """

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name=_("employee"),
    )
    # Vendor URLs are long and there is no ceiling in the spec; 500 is what the
    # field needs to be indexed and unique in Postgres without a hash.
    endpoint = models.URLField(_("endpoint"), max_length=500, unique=True)
    p256dh = models.CharField(_("public key"), max_length=200)
    auth = models.CharField(_("authentication secret"), max_length=100)
    # Only so a person can tell their own devices apart when unsubscribing one.
    # Not for identifying anybody: it goes no further than the settings screen.
    device_label = models.CharField(_("device"), max_length=80, blank=True)
    last_sent_at = models.DateTimeField(_("last used"), null=True, blank=True)

    class Meta:
        verbose_name = _("push subscription")
        verbose_name_plural = _("push subscriptions")

    def __str__(self) -> str:
        return f"{self.employee_id} · {self.device_label or self.endpoint[:40]}"
