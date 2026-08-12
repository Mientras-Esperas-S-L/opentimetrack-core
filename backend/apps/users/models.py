"""People and departments.

Two decisions worth understanding before touching anything:

1. **Email is unique per company, not globally.** One person can work for two
   companies with the same address, and in a system meant to be consumed by
   multi-company integrators that stops being an edge case. It forces sign-in to
   resolve the company first, which is done by email domain or by identity
   provider.

2. **Federated identity is first class.** `oidc_sub` holds the immutable anchor
   issued by the identity provider. That is what lets the same person be
   recognised here and in a third-party application clocking in on their behalf,
   without inventing a mapping table.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel, TenantOwnedModel


class Department(TenantOwnedModel):
    """Organisational unit inside a company."""

    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("department")
        verbose_name_plural = _("departments")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_department_per_company",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Role(models.TextChoices):
    EMPLOYEE = "EMPLOYEE", _("Employee")
    MANAGER = "MANAGER", _("Manager")
    ADMIN = "ADMIN", _("Administrator")


class UserManager(BaseUserManager):
    """Manager without tenant filtering.

    Unlike the rest of the domain, users cannot be filtered by the tenant in
    context: at sign-in time there is no tenant yet. User isolation is enforced
    in the views and permissions instead.
    """

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("role", Role.EMPLOYEE)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """A person with access to the system."""

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
        verbose_name=_("company"),
        help_text=_("Null only for platform superusers on self-hosted installs."),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("department"),
    )

    email = models.EmailField(_("email address"), max_length=254)
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100)
    role = models.CharField(_("role"), max_length=20, choices=Role, default=Role.EMPLOYEE)
    employee_id = models.CharField(
        _("staff number"),
        max_length=50,
        blank=True,
        help_text=_(
            "The person's identifier in the company's own systems. Acts as a bridge "
            "when an external application records clock events on their behalf."
        ),
    )
    locale = models.CharField(
        _("language"),
        max_length=10,
        blank=True,
        help_text=_("Overrides the company language for this person."),
    )
    # Art. 3.b of the pending decree: the record has to state the working-time
    # regime, full or part time, the contracted hours, and the percentage when
    # part time. It belongs to the person rather than to each event --- it is
    # what was agreed, not what happened on a given day.
    part_time = models.BooleanField(
        _("part time"),
        default=False,
        help_text=_("Art. 3.b. Part-time work is counted differently (art. 12 ET)."),
    )
    part_time_percentage = models.DecimalField(
        _("percentage of a full day"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Only for part time. Art. 3.b asks for it explicitly."),
    )
    contracted_schedule = models.CharField(
        _("agreed hours"),
        max_length=200,
        blank=True,
        help_text=_(
            "Art. 3.b: the agreed working hours, as text. For example "
            "'L-V 09:00-17:00'. Free text because a schedule is not a shape a "
            "closed field can hold."
        ),
    )
    default_work_mode = models.CharField(
        _("usual mode"),
        max_length=8,
        default="ONSITE",
        choices=[("ONSITE", _("On site")), ("REMOTE", _("Remote"))],
        help_text=_(
            "Art. 3.e. What a clock event assumes when it says nothing; each "
            "event can still record the other."
        ),
    )

    annual_leave_days = models.PositiveSmallIntegerField(
        _("annual leave days"),
        null=True,
        blank=True,
        help_text=_(
            "Overrides the company figure for this person. Empty means the "
            "company's. Part-time and mid-year joiners are the usual reason."
        ),
    )

    # Federated identity. `oidc_sub` is the provider-issued identifier and does
    # not change when the person changes email address or surname.
    oidc_sub = models.CharField(
        _("identity provider subject"),
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )
    oidc_issuer = models.CharField(_("issuer"), max_length=255, blank=True)

    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("admin site access"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = _("person")
        verbose_name_plural = _("people")
        ordering = ["last_name", "first_name"]
        constraints = [
            # Unique per company, not globally: the same person may work for two
            # companies. Platform superusers (no company) are covered by the
            # second constraint.
            models.UniqueConstraint(
                fields=["tenant", "email"],
                name="unique_email_per_company",
            ),
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(tenant__isnull=True),
                name="unique_email_without_company",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name

    @property
    def is_federated(self) -> bool:
        """Their credentials are governed by an external provider, not by us."""
        return bool(self.oidc_sub)

    @property
    def can_manage(self) -> bool:
        return self.role in {Role.MANAGER, Role.ADMIN}

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN
