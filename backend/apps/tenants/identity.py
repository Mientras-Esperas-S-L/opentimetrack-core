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

from apps.common.crypto import EncryptedTextField
from apps.common.models import TenantOwnedModel


class SsoProvider(TenantOwnedModel):
    """An OpenID Connect issuer this company trusts."""

    name = models.CharField(
        _("name"), max_length=120, help_text=_("Display name, e.g. 'Company directory'.")
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
    # ------------------------------------------------ signing people in (A1)

    slug = models.SlugField(
        _("identifier"),
        max_length=60,
        blank=True,
        default="",
        help_text=_("Stable name used in the sign-in URLs. Blank derives it from the name."),
    )
    client_id = models.CharField(
        _("client id"),
        max_length=255,
        blank=True,
        help_text=_(
            "What this install is registered as at the provider. Only for the browser flow."
        ),
    )
    client_secret = EncryptedTextField(
        _("client secret"),
        blank=True,
        default="",
        help_text=_("Stored encrypted; never sent to the browser. Only for the browser flow."),
    )
    scopes = models.CharField(
        _("scopes"),
        max_length=255,
        default="openid email profile",
        help_text=_("Space separated, as asked for at the authorisation endpoint."),
    )
    discovery_url = models.URLField(
        _("discovery document"),
        blank=True,
        help_text=_("Blank derives it from the issuer, which is the usual case."),
    )

    class EmailClaim(models.TextChoices):
        EMAIL = "email", "email"
        PREFERRED_USERNAME = "preferred_username", "preferred_username"
        UPN = "upn", "upn"

    email_claim = models.CharField(
        _("claim carrying the email"),
        max_length=32,
        choices=EmailClaim.choices,
        default=EmailClaim.EMAIL,
        help_text=_("Which claim holds the routable address. Ask the provider; they differ."),
    )
    auto_provision = models.BooleanField(
        _("create people on first sign-in"),
        default=False,
        help_text=_(
            "On: somebody signing in for the first time gets an account here, with no "
            "permissions and no working time set. Off: only people already here can sign in."
        ),
    )
    provider_enforces_mfa = models.BooleanField(
        _("the provider guarantees the second factor"),
        default=True,
        help_text=_("Evidence that federated sign-ins are still two-factor, for an audit."),
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
            models.UniqueConstraint(
                fields=["tenant", "slug"], name="unique_provider_slug_per_company"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.issuer})"

    def save(self, *args, **kwargs):
        if not self.slug:
            # Derivado y no obligatorio: quien da de alta un proveedor está pensando en
            # su nombre, no en cómo se verá en una URL.
            from django.utils.text import slugify

            self.slug = slugify(self.name)[:60]
        return super().save(*args, **kwargs)

    @property
    def expected_audience(self) -> str:
        return self.audience or self.issuer

    @property
    def well_known_url(self) -> str:
        """Where the provider describes itself: explicit, or the conventional place."""
        if self.discovery_url:
            return self.discovery_url
        return self.issuer.rstrip("/") + "/.well-known/openid-configuration"

    @property
    def can_sign_people_in(self) -> bool:
        """Whether the browser flow is set up, as opposed to only the assertion one."""
        return bool(self.is_active and self.client_id and self.client_secret)


class SsoDomain(TenantOwnedModel):
    """An email domain that belongs to a provider.

    It is what turns «rosa@contrata.example» into «then you sign in over there» without
    asking her to know which button is hers. One domain belongs to one provider per
    company: two would make the answer a guess.
    """

    provider = models.ForeignKey(
        SsoProvider,
        on_delete=models.CASCADE,
        related_name="domains",
        verbose_name=_("provider"),
    )
    domain = models.CharField(
        _("domain"),
        max_length=255,
        help_text=_("Just the domain, lowercase and without the @: contrata.example"),
    )

    class Meta:
        verbose_name = _("federated domain")
        verbose_name_plural = _("federated domains")
        ordering = ["domain"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "domain"], name="unique_domain_per_company"),
        ]

    def __str__(self) -> str:
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = (self.domain or "").strip().lower().lstrip("@")
        return super().save(*args, **kwargs)
