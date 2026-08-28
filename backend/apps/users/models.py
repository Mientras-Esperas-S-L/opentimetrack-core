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

import zoneinfo

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel, TenantOwnedModel
from apps.common.texto import validate_texto_legible
from apps.tenants.models import validate_time_zone


class Department(TenantOwnedModel):
    """Organisational unit inside a company."""

    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(
        _("description"), blank=True, validators=[validate_texto_legible]
    )
    is_active = models.BooleanField(_("active"), default=True)

    # Who answers for it. Several, because holiday does not stop for the one
    # person who can approve it, and because a large department is usually run
    # by more than one.
    #
    # Not "the manager who belongs here": somebody in the office can perfectly
    # well run the gardening crew, and reading the scope off membership would
    # hand them the office's records instead of the ones they answer for.
    managers = models.ManyToManyField(
        "users.User",
        blank=True,
        related_name="departments_managed",
        verbose_name=_("managers"),
        help_text=_(
            "Who may read and resolve for the people in it. Only has an effect on "
            "the manager profile: an administrator sees the whole company."
        ),
    )

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


class Workplace(TenantOwnedModel):
    """A centro de trabajo: where the work is done, not who it is done with.

    A different axis from the department and a legally heavier one. A department
    is how a company organises itself; a workplace is a place, and three things
    hang off the place rather than off the company:

    **The record is kept and inspected per workplace.** An inspector turns up at
    a site and asks for the record of that site.

    **Two of the fourteen public holidays are local**, decided by the town hall
    and approved by the region. Without knowing the municipality there is no way
    to apply them --- and the other twelve come from the region, which is the
    other field here.

    **The time zone is a property of the place.** Spain has two, and a company
    with an office in Madrid and another in Las Palmas cannot have one. The code
    that slices a day already said so in a comment before there was anywhere to
    put the answer.
    """

    name = models.CharField(_("name"), max_length=120)
    address = models.CharField(_("address"), max_length=255, blank=True)

    municipality = models.CharField(
        _("municipality"),
        max_length=120,
        blank=True,
        help_text=_("Decides the two local public holidays."),
    )
    #: The official code, because names are not unique --- Spain has several
    #: municipalities called the same thing in different provinces, and a
    #: holiday calendar keyed by name would give one of them the other's days.
    municipality_code = models.CharField(
        _("municipality code"),
        max_length=10,
        blank=True,
        help_text=_("INE code in Spain. Names repeat between provinces; codes do not."),
    )
    region = models.CharField(
        _("region"),
        max_length=8,
        blank=True,
        help_text=_(
            "Decides the public holidays the region sets. Empty uses only the national ones."
        ),
    )

    time_zone = models.CharField(
        _("time zone"),
        max_length=64,
        blank=True,
        validators=[validate_time_zone],
        help_text=_(
            "Empty uses the company's. Only needed where a workplace is in "
            "another zone: in Spain, the Canary Islands."
        ),
    )

    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("workplace")
        verbose_name_plural = _("workplaces")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_workplace_per_company",
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def tzinfo(self):
        """Its own zone, or the company's."""
        return zoneinfo.ZoneInfo(self.time_zone) if self.time_zone else self.tenant.tzinfo


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
    #: Art. 11.2: alterna trabajo y formación, y por eso trae un tope propio de
    #: tiempo de trabajo efectivo ---65 % el primer año, 85 % el segundo---.
    TRAINING_ALTERNATING = "TRAINING_ALT", _("Training contract, alternating")
    #: Art. 11.3: para obtener práctica profesional. Comparte nombre con el
    #: anterior y **no comparte el tope**: aquí la jornada es la ordinaria.
    TRAINING_PRACTICE = "TRAINING_PRO", _("Training contract, work practice")
    #: El valor que había antes de separarlos, y que se queda a propósito.
    #:
    #: Los contratos formativos que ya estaban guardados no dicen cuál de los
    #: dos son, y mandarlos a uno u otro sería decidirlo por quien los firmó:
    #: al primero les inventaría un tope que quizá no les toca, y al segundo les
    #: quitaría uno que quizá sí. Se quedan aquí, nombrando el hueco, y la
    #: revisión del cuadrante pide que se concrete.
    TRAINING = "TRAINING", _("Training contract, kind not stated")
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
    # Where they work, as opposed to who they work with. Separate from the
    # department because they answer different questions: the department says
    # who reads their record, the workplace says which local holidays apply,
    # which zone their day is sliced in, and where an inspection would ask for
    # the record.
    workplace = models.ForeignKey(
        Workplace,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="people",
        verbose_name=_("workplace"),
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
    first_name = models.CharField(
        _("first name"), max_length=100, validators=[validate_texto_legible]
    )
    last_name = models.CharField(
        _("last name"), max_length=100, validators=[validate_texto_legible]
    )
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

    # Opt-in and on by default: forgetting to clock in or out is the ordinary
    # failure, and a nudge is help, not surveillance. The reminder prompts the
    # real punch --- it never records one --- so it cannot hide a late arrival
    # or an early leave, only make them get recorded.
    wants_punch_reminders = models.BooleanField(
        _("wants clock reminders"),
        default=True,
        help_text=_(
            "Send a reminder when a shift starts and there is no entry, or when a "
            "day is left open. It prompts the real punch; it never records one."
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
    #
    # Único **por empresa**, no globalmente: ver la restricción de más abajo. Un
    # `unique=True` a secas aquí contradecía el diseño que esta misma clase
    # declara para el correo.
    oidc_sub = models.CharField(
        _("identity provider subject"),
        max_length=255,
        blank=True,
        default="",
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
            # La identidad federada, por empresa y por el mismo motivo que el
            # correo. Un grupo con dos sociedades en el mismo OTT y un solo
            # proveedor de identidad es el caso normal, no el raro: con la
            # restricción global, la segunda empresa no podía dar de alta a
            # alguien que ya estaba en la primera, y lo que recibía su conector
            # era un 500 sin código al que reaccionar.
            #
            # Dentro de una empresa sí es única: dos fichas con el mismo `sub`
            # son la misma persona duplicada, y el acceso entraría en cualquiera
            # de las dos.
            models.UniqueConstraint(
                fields=["tenant", "oidc_sub"],
                condition=~models.Q(oidc_sub=""),
                name="unique_identity_per_company",
            ),
            # El número de empleado, único dentro de la empresa. Es el puente
            # con las aplicaciones que fichan en nombre de alguien: el conector
            # manda «EMP-0042» y el servidor tiene que saber a quién se refiere.
            # Repetido, la resolución devuelve a quien salga primero y los
            # fichajes acaban en la ficha de otra persona --- un fallo que no
            # avisa y que solo se nota cuando alguien mira su registro y ve
            # jornadas que no hizo.
            #
            # Solo cuando lo hay: en blanco es lo normal en una empresa que no
            # usa números, y no puede chocar consigo mismo.
            # Y sin distinguir mayúsculas, porque **el resto del producto ya
            # trata «EMP-9» y «emp-9» como la misma persona**: así los busca
            # `_resolve` en la puerta de integración y así el fichaje delegado,
            # que además rechaza la referencia por ambigua si encuentra dos.
            # Comparando exacto se podían crear las dos por shell o por
            # importación, y entonces una puerta elegía al azar y la otra se
            # plantaba para todo el mundo.
            models.UniqueConstraint(
                Lower("employee_id"),
                "tenant",
                condition=~models.Q(employee_id=""),
                name="unique_staff_number_per_company",
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

    @property
    def tzinfo(self):
        """The zone their working day is measured in.

        Their workplace's, or the company's. Asked of the person rather than of
        the company because the answer differs between two people on the same
        payroll --- Madrid and Las Palmas is one hour, and one hour is the
        difference between a punch landing on Monday and on Sunday.
        """
        return self.workplace.tzinfo if self.workplace_id else self.tenant.tzinfo

    def is_engaged_on(self, day) -> bool:
        """Whether the relationship covers that day.

        Asked per day rather than once, for the same reason the age is: a
        roster drawn for a period that ends mid-month has to know where it
        stops, and a single answer would either extend it or cut it short.

        Y para un fijo discontinuo, además, dentro de un periodo de actividad
        (art. 16 ET). **Solo si los hay**: mientras no se haya declarado
        ninguno, la relación cubre todo el contrato como cualquier otra. Es
        deliberado --- una empresa que marca a alguien como fijo discontinuo y
        todavía no ha cargado sus campañas no puede quedarse con una persona
        que no está en activo ningún día del año.
        """
        if self.contract_start and day < self.contract_start:
            return False
        if self.contract_end and day > self.contract_end:
            return False
        if self.seasonal and self.temporadas:
            return any(p.covers(day) for p in self.temporadas)
        return True

    @cached_property
    def temporadas(self) -> list:
        """Los periodos de actividad de esta persona, o una lista vacía.

        Con `objects_all_tenants` y filtrando por la persona, que es el mismo
        camino que toma `rastro_de`: el manager por defecto filtra por la
        empresa **del contexto**, y esto se pregunta también desde donde no hay
        contexto puesto ---el cotejo del cuadrante, una comprobación suelta---.
        Filtrar por `self` acota tanto como la empresa, porque los periodos de
        una persona son de su empresa por definición.

        Cacheado porque `is_engaged_on` se pregunta **por día**: un mes de
        cuadrante son treinta llamadas para la misma persona, y sin esto serían
        treinta consultas. El precio es que una instancia viva no ve un periodo
        añadido después, y eso está bien: cada petición reconstruye la suya.
        """
        if not self.seasonal:
            return []
        return list(ActivityPeriod.objects_all_tenants.filter(employee=self))

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


class ActivityPeriod(TenantOwnedModel):
    """Cuándo se llama a trabajar a quien tiene contrato fijo discontinuo.

    El art. 16 ET dice que el trabajo viene «en periodos de actividad», y hasta
    ahora el sistema sabía que alguien era fijo discontinuo ---el campo
    `seasonal` existe--- pero no **cuándo** lo estaba. `is_engaged_on` lo decía
    en su propio texto: era un hueco que se nombraba en vez de contestarlo mal.

    Lo que faltaba no era el cotejo. Lo esperado sale del cuadrante, así que
    fuera de temporada, si nadie pone turnos, el sistema ya no espera jornada.
    Faltaban tres cosas y esta las sostiene:

    1. **Poder decirlo**, que es lo que hace este modelo.
    2. **Que el cuadrante avise** si se asigna turno fuera de temporada. El
       aviso existía para las fechas del contrato y se saltaba a quien no tiene
       ninguna --- que es justo el fijo discontinuo indefinido.
    3. **Que quede constancia del llamamiento.** El art. 16.3 lo pide por
       escrito y con antelación, así que `called_on` es una fecha y no un
       booleano: «se le llamó» sin decir cuándo no acredita la antelación.

    El fin es opcional a propósito. Una campaña que empieza sabe cuándo empieza
    y no siempre cuándo acaba, y obligar a inventarse una fecha de cierre
    produciría un dato falso donde ahora hay un hueco honesto.
    """

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="activity_periods",
        verbose_name=_("employee"),
    )
    start_date = models.DateField(_("activity starts"))
    end_date = models.DateField(
        _("activity ends"),
        null=True,
        blank=True,
        help_text=_("Empty while the season is open: a campaign knows when it starts."),
    )
    called_on = models.DateField(
        _("called up on"),
        null=True,
        blank=True,
        help_text=_(
            "Art. 16.3 ET: the call-up is in writing and with notice. The date is "
            "what shows the notice was given; a tick would not."
        ),
    )
    note = models.TextField(_("note"), blank=True, validators=[validate_texto_legible])

    class Meta:
        verbose_name = _("period of activity")
        verbose_name_plural = _("periods of activity")
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="activity_period_ends_after_it_starts",
            ),
        ]

    def __str__(self) -> str:
        hasta = self.end_date.isoformat() if self.end_date else "…"
        return f"{self.start_date.isoformat()} → {hasta}"

    def covers(self, day) -> bool:
        """Si ese día cae dentro del periodo."""
        if day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date


class RemoteWorkAgreement(TenantOwnedModel):
    """El acuerdo de trabajo a distancia del art. 5 de la Ley 10/2021.

    La ley se aplica cuando se trabaja a distancia al menos el 30 % de la
    jornada en un periodo de tres meses (art. 1), y entonces exige acuerdo
    **por escrito y previo** al inicio. Sin él, la empresa está incumpliendo
    aunque todo lo demás esté bien.

    **Lo que este modelo guarda, y lo que no.** El contenido mínimo del art. 7
    ---inventario de medios, gastos y su compensación, horario, porcentaje y
    distribución, centro de trabajo al que queda adscrita la persona, medios de
    control, procedimiento de reversibilidad--- es un documento, y un documento
    no se sustituye por siete campos: quien tenga que enseñarlo en una
    inspección enseña el papel firmado, no una pantalla.

    Lo que aquí hace falta es **saber si existe y desde cuándo**, porque eso es
    lo que convierte «esta persona teletrabaja el 45 %» en «esta persona
    teletrabaja el 45 % y no consta acuerdo», que es la frase que sirve de algo.

    **`signed_on` y `starts_on` son dos fechas distintas a propósito.** El art.
    5.1 dice que el acuerdo es previo, así que firmar después de empezar es
    precisamente el defecto que hay que poder ver. Con una sola fecha no se
    podría.
    """

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="remote_work_agreements",
        verbose_name=_("employee"),
    )
    signed_on = models.DateField(
        _("signed on"),
        help_text=_("Art. 5.1: the agreement comes before the remote work starts."),
    )
    starts_on = models.DateField(_("remote work starts"))
    ends_on = models.DateField(
        _("remote work ends"),
        null=True,
        blank=True,
        help_text=_("Empty for an open-ended agreement, which is the usual one."),
    )
    agreed_share = models.DecimalField(
        _("share agreed (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Art. 7.f asks the agreement to state it. Left empty it is not checked "
            "against what is actually worked: the figure that binds is on paper."
        ),
    )
    note = models.TextField(_("note"), blank=True, validators=[validate_texto_legible])

    class Meta:
        verbose_name = _("remote work agreement")
        verbose_name_plural = _("remote work agreements")
        ordering = ["-starts_on"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__isnull=True)
                | models.Q(ends_on__gte=models.F("starts_on")),
                name="remote_agreement_ends_after_it_starts",
            ),
        ]

    def __str__(self) -> str:
        hasta = self.ends_on.isoformat() if self.ends_on else "…"
        return f"{self.starts_on.isoformat()} → {hasta}"

    def covers(self, day) -> bool:
        """Si ese día está amparado por este acuerdo."""
        if day < self.starts_on:
            return False
        return self.ends_on is None or day <= self.ends_on

    @property
    def signed_late(self) -> bool:
        """Firmado después de empezar, que es lo que el art. 5.1 no admite."""
        return self.signed_on > self.starts_on


class AdaptationStatus(models.TextChoices):
    """Las tres respuestas que el art. 34.8 admite, y la espera.

    El artículo no deja «denegada» a secas: la empresa comunica por escrito la
    aceptación, **plantea una alternativa** o se niega, y en los dos últimos
    casos motiva. La alternativa es una respuesta distinta de la negativa ---es
    el resultado normal de una negociación--- y meterlas en el mismo cajón
    perdería justo lo que el artículo quiere que quede escrito.
    """

    PENDING = "PENDING", _("In negotiation")
    ACCEPTED = "ACCEPTED", _("Accepted")
    ALTERNATIVE = "ALTERNATIVE", _("An alternative was proposed")
    REFUSED = "REFUSED", _("Refused")
    WITHDRAWN = "WITHDRAWN", _("Withdrawn by the person")


class ScheduleAdaptation(TenantOwnedModel):
    """Una solicitud de adaptación de jornada del art. 34.8 ET, y su respuesta.

    El derecho existe desde 2019 y es de los más usados que hay: cualquier
    persona con hijos menores de doce años puede pedir cambiar la duración, la
    distribución o la forma de prestación de su jornada ---incluido pasar a
    trabajo a distancia--- para conciliar.

    Lo que el producto ya sabía era la **consecuencia**: un fichaje puede
    marcarse como trabajado bajo una adaptación (art. 3.i, `FlexibilityMeasure.
    CARE`). Lo que no había era **el expediente**, y es donde está la obligación:

    - La empresa abre un proceso de negociación de **quince días como máximo**.
    - Al terminar, **por escrito**, acepta, propone una alternativa o se niega.
    - En los dos últimos casos, **motiva**.

    Sin eso, una solicitud podía quedarse sin contestar para siempre y no había
    dónde mirarlo. El plazo se avisa ---nadie puede impedir que pase el tiempo---
    y la motivación se exige, porque ahí el artículo no da opción.

    **No guarda si la adaptación se concedió «de verdad».** Lo que se pacte se
    aplica cambiando la jornada, el cuadrante o el modo de trabajo, que ya
    existen. Esto es el expediente de cómo se llegó ahí.
    """

    #: Art. 34.8: «un periodo máximo de quince días».
    PLAZO_DE_RESPUESTA = 15

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="schedule_adaptations",
        verbose_name=_("employee"),
    )
    requested_on = models.DateField(
        _("requested on"),
        help_text=_("The fifteen days of art. 34.8 count from here."),
    )
    asked_for = models.TextField(
        _("what is being asked"),
        validators=[validate_texto_legible],
        help_text=_("Duration, distribution, or the way the work is done --- remote included."),
    )
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=AdaptationStatus,
        default=AdaptationStatus.PENDING,
    )
    answered_on = models.DateField(_("answered on"), null=True, blank=True)
    answer = models.TextField(
        _("answer"),
        blank=True,
        validators=[validate_texto_legible],
        help_text=_(
            "Art. 34.8 asks for this in writing, and for a reason when the answer is "
            "not a plain yes."
        ),
    )
    answered_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_adaptations_answered",
        verbose_name=_("answered by"),
    )

    class Meta:
        verbose_name = _("schedule adaptation")
        verbose_name_plural = _("schedule adaptations")
        ordering = ["-requested_on"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(answered_on__isnull=True)
                | models.Q(answered_on__gte=models.F("requested_on")),
                name="adaptation_answered_after_it_was_asked",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.requested_on.isoformat()} · {self.get_status_display()}"

    @property
    def needs_a_reason(self) -> bool:
        """Si esta respuesta es de las que el artículo obliga a motivar."""
        return self.status in {AdaptationStatus.ALTERNATIVE, AdaptationStatus.REFUSED}

    def days_waiting(self, today) -> int | None:
        """Días que lleva sin contestar, o `None` si ya se contestó."""
        if self.status != AdaptationStatus.PENDING:
            return None
        return (today - self.requested_on).days

    def out_of_time(self, today) -> bool:
        """Si se ha pasado el plazo del art. 34.8 sin contestar."""
        esperando = self.days_waiting(today)
        return esperando is not None and esperando > self.PLAZO_DE_RESPUESTA
