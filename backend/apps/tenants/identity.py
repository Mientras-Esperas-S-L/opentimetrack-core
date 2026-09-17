"""Identity providers a company trusts, and what they are allowed to do.

Two different things hang off the same row, and keeping them apart is the point:

- **Signing people in** (A1, still to come): the person's browser goes to the
  provider and comes back with an `id_token`.
- **Acting for a person** (this file's `may_act_for_people`): the managing
  application's *server* presents a short assertion it signed and gets a session
  for that person, with no browser in the middle. It is the only way an
  application can clock somebody in **as themselves** while they are in the field
  with no coverage and the punch is being replayed from a queue.

The second is a strong power: an issuer holding it can obtain a session for
anybody in that company. That is not a hole, it is what being a company's
identity provider means -- the same provider could sign them in through the
browser anyway. What the record keeps is the trail: a punch made through such a
session is `APPLICATION`, never `WEB`, and it carries the application's name.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TenantOwnedModel


class SsoProvider(TenantOwnedModel):
    """An OpenID Connect issuer this company trusts."""

    name = models.CharField(
        _("name"), max_length=120, help_text=_("Display name, e.g. 'GreenCityControl'.")
    )
    issuer = models.CharField(
        _("issuer"),
        max_length=255,
        help_text=_("Exactly the `iss` of its tokens, e.g. https://gcc.example/o."),
    )
    jwks_uri = models.URLField(
        _("keys"),
        blank=True,
        help_text=_(
            "Where its public keys are. Blank derives it from the issuer's discovery document."
        ),
    )
    audience = models.CharField(
        _("audience"),
        max_length=255,
        blank=True,
        help_text=_(
            "What its tokens must carry in `aud` for this install. Blank accepts the issuer's own."
        ),
    )
    is_active = models.BooleanField(_("active"), default=True)

    may_act_for_people = models.BooleanField(
        _("may act for its people"),
        default=False,
        help_text=_(
            "Lets its server exchange a signed assertion for a session of one of its "
            "people, with no browser. A managing application that clocks in on their "
            "behalf needs it; off by default."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("identity provider")
        verbose_name_plural = _("identity providers")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "issuer"], name="unique_issuer_per_company"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.issuer})"

    @property
    def keys_url(self) -> str:
        """Explicit, or the conventional one derived from the issuer."""
        if self.jwks_uri:
            return self.jwks_uri
        return self.issuer.rstrip("/") + "/.well-known/jwks.json"

    @property
    def expected_audience(self) -> str:
        return self.audience or self.issuer
