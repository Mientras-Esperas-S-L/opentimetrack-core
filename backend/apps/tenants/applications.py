"""External applications that act against the API.

An application is an actor with its own permissions, not a shared password. It
belongs to one company, carries only what its owner granted, can be revoked
without touching anybody's account, and everything it does is attributable to it.

On credentials: the secret is stored **hashed** and shown once, at creation. Not
being able to recover it is the point -- a secret the server can read back is a
secret the server can leak. Hashing is SHA-256 rather than a slow function
because these are 256 bits of randomness, not human passwords: there is nothing
to brute-force, and every API call needs the lookup to be fast.
"""

from __future__ import annotations

import hashlib
import secrets

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import TenantOwnedModel

# Recognisable on sight and greppable by a secret scanner, so a leaked token can
# be spotted in a log or a repository before it is used.
TOKEN_PREFIX = "ott_app_"  # noqa: S105 — a prefix, not a secret


class ApplicationScope(models.TextChoices):
    """What an application is allowed to do. Granted one by one, never in bulk."""

    PUNCH_SELF = "punch:self", _("Clock in with the employee's own identity")
    PUNCH_DELEGATED = "punch:delegated", _("Clock in on behalf of an employee")
    READ_ATTENDANCE = "read:attendance", _("Read clock events and day status")
    READ_PEOPLE = "read:people", _("Read the list of people")
    WRITE_PEOPLE = "write:people", _("Create and update people")
    RECEIVE_EVENTS = "receive:events", _("Receive outbound events")


class Application(TenantOwnedModel):
    """A third-party product authorised by a company."""

    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)

    scopes = models.JSONField(
        _("permissions"),
        default=list,
        help_text=_("List of granted scopes. Empty means the application can do nothing."),
    )

    is_active = models.BooleanField(_("active"), default=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications_created",
        verbose_name=_("authorised by"),
    )

    class Meta:
        verbose_name = _("application")
        verbose_name_plural = _("applications")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_application_per_company",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def allows(self, scope: str) -> bool:
        return self.is_active and scope in (self.scopes or [])


class ApplicationCredential(TenantOwnedModel):
    """A token of an application. Several may coexist, which is what makes
    rotation possible without downtime: issue the new one, swap it, revoke the
    old one."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="credentials",
        verbose_name=_("application"),
    )
    label = models.CharField(_("label"), max_length=100, blank=True)

    token_hash = models.CharField(_("token hash"), max_length=64, unique=True, editable=False)
    token_hint = models.CharField(
        _("hint"),
        max_length=16,
        editable=False,
        help_text=_("Last characters, to tell one credential from another in the interface."),
    )

    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    last_used_at = models.DateTimeField(_("last used"), null=True, blank=True)

    class Meta:
        verbose_name = _("application credential")
        verbose_name_plural = _("application credentials")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.application.name} …{self.token_hint}"

    # ------------------------------------------------------------------ issuing

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, application: Application, *, label: str = "", expires_at=None):
        """Creates a credential and returns it together with the token in clear.

        The token travels back to the caller exactly once. It is not stored, so
        it cannot be shown again: losing it means issuing another.
        """
        raw = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        credential = cls.objects.create(
            tenant=application.tenant,
            application=application,
            label=label,
            token_hash=cls.hash_token(raw),
            token_hint=raw[-6:],
            expires_at=expires_at,
        )
        return credential, raw

    # ------------------------------------------------------------------- status

    @property
    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return False
        return self.application.is_active

    def revoke(self) -> None:
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])

    def touch(self) -> None:
        """Records use, without a write on every single call.

        A minute of granularity is enough to answer «is this credential still in
        use?», which is what the field is for, and avoids a write per request.
        """
        now = timezone.now()
        if self.last_used_at is None or (now - self.last_used_at).total_seconds() > 60:
            type(self).objects_all_tenants.filter(pk=self.pk).update(last_used_at=now)
