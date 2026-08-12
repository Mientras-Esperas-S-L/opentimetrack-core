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


class WorkingTimeRegime(models.TextChoices):
    """Which set of rules applies to somebody's working day.

    Not a list of contract types. Spain has dozens and almost none of them
    change anything about recording time; what changes it is which limits apply
    and what hours beyond the agreed ones are called.

    The distinction that costs money if it is wrong is **part time against
    reduced**. They look the same on a roster and the law treats them
    differently: art. 12.4.c forbids overtime on a part-time contract, and a
    reduced working day under art. 37.6 is a full-time contract worked less, so
    that ban does not reach it. A system that filed both as "part time" would
    refuse overtime to people entitled to it.

    Deliberately **not** here: whether the work is seasonal. A permanent-
    seasonal contract (art. 16 ET) is full or part time *while it is active* ---
    it is a different axis, and folding it in would force a choice between two
    facts that are both true.
    """

    FULL_TIME = "FULL_TIME", _("Full time")
    PART_TIME = "PART_TIME", _("Part time")
    REDUCED = "REDUCED", _("Reduced working day")
    TRAINING = "TRAINING", _("Training contract")
    VARIABLE = "VARIABLE", _("No agreed figure")


class HoursPeriod(models.TextChoices):
    """What the agreed figure is a figure *of*.

    A week is the obvious one and not the commonest. Spanish collective
    agreements very often set the year --- the state gardening agreement says
    1700 hours a year and no weekly figure at all --- and a product that only
    understood weeks would either ignore that or invent a division nobody
    agreed to.
    """

    WEEK = "WEEK", _("a week")
    MONTH = "MONTH", _("a month")
    YEAR = "YEAR", _("a year")


#: How many qualifying days it takes before the roster will claim to have read
#: a habit. Not a legal figure --- art. 36.1 says "normally" and leaves it there
#: --- but a reading has to rest on something, and a majority of one day is not
#: a habit. Kept low on purpose: this only decides when the product *asks* the
#: company about the status, and asking too rarely is the worse mistake.
NIGHT_EVIDENCE_DAYS = 3


class NightWorkerStatus(models.TextChoices):
    """Whether art. 36.1's status applies, and who decided.

    Three values rather than a boolean because there are three real answers and
    the third is the commonest. The law defines the status by *what the person
    normally does*, which the roster can see; but the company holds the contract
    and sometimes knows before any roster exists --- somebody hired expressly
    for nights is a night worker from day one, with a blank calendar.

    So: `AUTO` reads it from the roster and is the default; `YES` and `NO` are
    the company saying it knows better, which it is entitled to do and which
    gets recorded as a decision rather than silently overriding the reading.
    """

    AUTO = "AUTO", _("Read from the roster")
    YES = "YES", _("Yes")
    NO = "NO", _("No")


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
    # regime, the contracted hours, and the percentage when part time. It
    # belongs to the person rather than to each event --- it is what was agreed,
    # not what happened on a given day.
    #
    # There used to be a boolean and a percentage here, and no number of hours,
    # so the roster compared everybody against the company's weekly limit:
    # somebody contracted for twenty-five hours could be rostered for
    # thirty-eight without a word, because thirty-eight is under forty.
    regime = models.CharField(
        _("working-time regime"),
        max_length=12,
        choices=WorkingTimeRegime,
        default=WorkingTimeRegime.FULL_TIME,
        help_text=_("Art. 3.b. Decides which limits apply, not just how many hours."),
    )
    contracted_hours = models.DecimalField(
        _("contracted hours"),
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text=_(
            "The figure the contract agreed. Empty on a full-time contract means "
            "the company's own; empty with no agreed figure means there is none."
        ),
    )
    contracted_period = models.CharField(
        _("over"),
        max_length=8,
        choices=HoursPeriod,
        default=HoursPeriod.WEEK,
        help_text=_("Whether the figure above is a week, a month or a year."),
    )

    # How long the relationship lasts, and whether the work is continuous. A
    # separate axis from the regime on purpose: a permanent-seasonal contract is
    # full or part time *while it is active*, and a six-month contract records
    # time exactly like an open-ended one. Folding either into the regime would
    # force a choice between two facts that are both true.
    contract_start = models.DateField(
        _("contract starts"),
        null=True,
        blank=True,
        help_text=_("Empty means it was already running when the company started here."),
    )
    contract_end = models.DateField(
        _("contract ends"),
        null=True,
        blank=True,
        help_text=_("Empty means open-ended. A date makes it fixed-term."),
    )
    seasonal = models.BooleanField(
        _("permanent seasonal"),
        default=False,
        help_text=_(
            "Art. 16 ET: the work comes in periods of activity. Outside them there "
            "is no expected working day, and the roster says so instead of "
            "reporting an absence."
        ),
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
    # A third axis, and for the same reason as the other two: it is a fact that
    # is true alongside the regime and the contract, not instead of either. A
    # night worker can be full time or part time, permanent or seasonal, and
    # rotating shifts say nothing about how many hours were agreed.
    night_worker = models.CharField(
        _("night worker"),
        max_length=6,
        choices=NightWorkerStatus,
        default=NightWorkerStatus.AUTO,
        help_text=_(
            "Art. 36.1 ET. A status, not a shift: three hours of the daily working "
            "day at night as a rule, or a third of the year. It brings an eight-hour "
            "average over fifteen days and a ban on overtime. Leave it on automatic "
            "to read it from the roster."
        ),
    )
    rotating_shifts = models.BooleanField(
        _("rotating shifts"),
        default=False,
        help_text=_(
            "Art. 36.3 ET. The person rotates between shift teams. This does not add "
            "limits: it stops the ordinary ones being applied to a changeover, where "
            "a shorter rest is lawful and owed back rather than a breach."
        ),
    )
    voluntary_night_shift = models.BooleanField(
        _("volunteered for nights"),
        default=False,
        help_text=_(
            "Art. 36.3 ET allows more than two consecutive weeks on the night shift "
            "only when the person asked for it. Recorded here because the roster "
            "cannot tell a volunteer from somebody left there."
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

    date_of_birth = models.DateField(
        _("date of birth"),
        null=True,
        blank=True,
        help_text=_(
            "Only used to apply the protections the law gives workers under "
            "eighteen: eight hours a day, a thirty-minute break from four and a "
            "half, two days of weekly rest, and no night work or overtime. "
            "Without it those protections cannot be applied, and the system says "
            "so rather than assuming the person is an adult."
        ),
    )

    # Art. 4.b: on disagreement over a change, the workers' legal representation
    # must be informed. Art. 6.2 also grants them access to the record. The
    # system cannot know who they are, so the company marks them.
    is_worker_representative = models.BooleanField(
        _("workers' representative"),
        default=False,
        help_text=_(
            "Informed when somebody disagrees with a change to their record "
            "(art. 4.b), and entitled to consult the register (art. 6.2)."
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

    def is_minor_on(self, day) -> bool:
        """Whether they were under eighteen on a given day.

        On a **given day**, never "now". Somebody turns eighteen and the
        protections stop applying from that date --- but a roster drawn for last
        month, or a report of last year, has to be read with the age they had
        then. Asking "are they a minor" without a date silently rewrites the
        past every birthday.
        """
        if self.date_of_birth is None:
            return False
        eighteenth = self.date_of_birth.replace(year=self.date_of_birth.year + 18)
        return day < eighteenth

    @property
    def age_is_known(self) -> bool:
        """So a caller can tell "adult" from "we do not know".

        The difference matters: the second one means the protections are not
        being applied, which somebody should be told rather than left to assume.
        """
        return self.date_of_birth is not None

    @property
    def is_federated(self) -> bool:
        """Their credentials are governed by an external provider, not by us."""
        return bool(self.oidc_sub)

    @property
    def part_time(self) -> bool:
        """Whether the part-time regime applies, which is a narrower question
        than "does this person work fewer hours".

        A reduced working day under art. 37.6 is fewer hours and is **not**
        part-time work: the contract stays full time and the overtime ban of
        art. 12.4.c does not reach it. Answering this by hours worked rather
        than by regime would deny overtime to people entitled to it.
        """
        return self.regime == WorkingTimeRegime.PART_TIME

    def holds_night_worker_status(self, night, roster) -> bool:
        """Whether art. 36.1's status applies, from the contract or the roster.

        The company's answer wins when it gave one. That is not a loophole: the
        status is defined by what somebody *normally* does, and a month of
        roster is a worse witness to "normally" than the contract that hired
        them for nights. A company that answers `NO` about somebody plainly on
        nights still gets the roster's own reading reported separately, so the
        override is visible rather than silent.

        With no answer, the test is the article's: three hours of the daily
        working day inside the window, habitually. Habitually is read here as
        the majority of the days rostered, and never from fewer than
        `NIGHT_EVIDENCE_DAYS` of them --- one night covered for a colleague is a
        majority of one, and the first version of this said that made somebody a
        night worker. The annual third of art. 36.1 is not something a month of
        calendar can see at all, which is exactly why the company can declare it.
        """
        if self.night_worker == NightWorkerStatus.YES:
            return True
        if self.night_worker == NightWorkerStatus.NO:
            return False
        if not night or not roster:
            return False
        threshold = night.qualifying_daily_hours * 60
        qualifying = sum(
            1
            for shift in roster
            if shift.night_minutes(night.window_starts_at, night.window_ends_at) >= threshold
        )
        return qualifying >= NIGHT_EVIDENCE_DAYS and qualifying * 2 > len(roster)

    def is_engaged_on(self, day) -> bool:
        """Whether the relationship covers that day.

        Asked per day rather than once, for the same reason the age is: a
        roster drawn for a period that ends mid-month has to know where it
        stops, and a single answer would either extend it or cut it short.

        A permanent-seasonal contract is engaged whenever it is not ended: the
        periods of activity within it are a separate thing, and the system does
        not model the call-up yet --- which is a gap worth naming rather than a
        question to answer wrongly.
        """
        if self.contract_start and day < self.contract_start:
            return False
        if self.contract_end and day > self.contract_end:
            return False
        return True

    @property
    def has_agreed_hours(self) -> bool:
        """Whether there is any figure to measure against at all."""
        return self.regime != WorkingTimeRegime.VARIABLE

    def agreed_hours(self, rules) -> tuple[float, str] | None:
        """The agreed figure and the period it covers, or None.

        Returns the period rather than converting to weeks. Dividing 1700 hours
        a year by 52 produces a number nobody agreed to and that no week is
        supposed to match: an annual figure is met or missed over a year, and
        saying so is more use than a weekly average that is wrong every week.
        """
        if not self.has_agreed_hours:
            return None
        if self.contracted_hours is not None:
            return float(self.contracted_hours), self.contracted_period
        if self.regime in {WorkingTimeRegime.FULL_TIME, WorkingTimeRegime.REDUCED}:
            # Full time with nothing written down is the company's own week.
            # Not a guess: full time *is* the ordinary week, and asking every
            # full-timer to retype it invites typos in a value already known.
            return float(rules.weekly_hours), HoursPeriod.WEEK
        return None

    def share_of_full_time(self, rules) -> float | None:
        """The percentage art. 3.b asks for, worked out rather than typed.

        Two fields saying the same thing end up disagreeing, and the one that
        reaches the inspection report should be the one derived from the hours
        actually agreed. Only comparable when both are the same period.
        """
        agreed = self.agreed_hours(rules)
        if agreed is None:
            return None
        hours, period = agreed
        if period != HoursPeriod.WEEK or not rules.weekly_hours:
            return None
        return round(hours / float(rules.weekly_hours) * 100, 2)

    @property
    def can_manage(self) -> bool:
        return self.role in {Role.MANAGER, Role.ADMIN}

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN
