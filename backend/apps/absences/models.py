"""Leave requests.

Their reason for being here is not HR bookkeeping: approved leave blocks clocking
in, so this is part of the legal record too.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from apps.absences.uploads import validate_content, validate_extension, validate_size
from apps.common.models import TenantOwnedModel
from apps.common.texto import validate_texto_legible

logger = logging.getLogger(__name__)


class AbsenceType(models.TextChoices):
    """The family an absence belongs to, and the only taxonomy this app acts on.

    It used to be the whole answer, which is why the eight permits of art. 37.3
    all came out as "personal leave". The specific kind now lives in
    `LeaveType`; this stays because every query asks the family and none of
    them ask the rest, and because it has to outlive a leave type being
    renamed.
    """

    VACATION = "VACATION", _("Holiday")
    SICK_LEAVE = "SICK_LEAVE", _("Sick leave")
    PAID_LEAVE = "PAID_LEAVE", _("Paid leave")
    UNPAID_LEAVE = "UNPAID_LEAVE", _("Unpaid leave")
    SUSPENSION = "SUSPENSION", _("Contract suspended")

    # Written before the catalogue existed. Not offered to new absences and not
    # removed either: the rows that carry them have to stay readable, and a
    # record whose reason stops rendering is a record that lost something.
    PERSONAL = "PERSONAL", _("Personal leave")
    OTHER = "OTHER", _("Other")


class LeaveUnit(models.TextChoices):
    """What an entitlement is counted in.

    Four, and they are not interchangeable. Art. 37.3.a says fifteen **calendar**
    days for a wedding; art. 37.9 says hours equivalent to four days a year;
    art. 48 bis says eight weeks. Storing all of them as "days" and hoping would
    lose the weekend on the first and the whole point on the second.
    """

    DAYS_CALENDAR = "DAYS_CALENDAR", _("calendar days")
    DAYS_WORKING = "DAYS_WORKING", _("working days")
    HOURS = "HOURS", _("hours")
    WEEKS = "WEEKS", _("weeks")


class LeavePeriod(models.TextChoices):
    """What the entitlement resets against.

    Fifteen days *per wedding* and four days *per year* are both "four days" in
    a field that does not say which, and a balance built on the wrong one is
    wrong by a whole year.
    """

    EVENT = "EVENT", _("each time")
    DAY = "DAY", _("a day")
    WEEK = "WEEK", _("a week")
    MONTH = "MONTH", _("a month")
    YEAR = "YEAR", _("a year")


class LeaveType(TenantOwnedModel):
    """One kind of leave, as this company grants it.

    A copy, deliberately. The country's catalogue seeds it and then stops being
    read: a collective agreement improves any of these, the company edits its
    own row, and a change of ours never silently rewrites a figure somebody
    agreed to.

    It replaces a four-value enum --- holiday, sick leave, personal leave,
    other --- in which the eight permits of art. 37.3 all landed on "personal
    leave". That is the same as not having them: nobody could count how many had
    been used, check a duration, or answer an inspector.
    """

    #: Stable across renames, and how the seed knows what it already wrote.
    #: Blank for one the company invented, which has no counterpart to match.
    code = models.CharField(_("code"), max_length=40, blank=True)
    name = models.CharField(_("name"), max_length=120)

    family = models.CharField(
        _("kind"),
        max_length=14,
        choices=[
            ("VACATION", _("Holiday")),
            ("SICK_LEAVE", _("Sick leave")),
            ("PAID_LEAVE", _("Paid leave")),
            ("UNPAID_LEAVE", _("Unpaid leave")),
            ("SUSPENSION", _("Contract suspended")),
        ],
        default="PAID_LEAVE",
        help_text=_(
            "What it behaves like. Holiday spends the holiday balance; sick leave "
            "never stores a certificate."
        ),
    )

    basis = models.CharField(
        _("legal basis"),
        max_length=60,
        blank=True,
        help_text=_("The article it comes from. Empty for one the agreement gives."),
    )

    #: Null means "el tiempo indispensable": the law grants the time the thing
    #: takes and no more. Those are exactly the ones asked for in hours.
    amount = models.DecimalField(
        _("how much"),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Empty means the indispensable time, with no fixed limit."),
    )
    unit = models.CharField(
        _("in"), max_length=14, choices=LeaveUnit, default=LeaveUnit.DAYS_CALENDAR
    )
    period = models.CharField(
        _("per"), max_length=6, choices=LeavePeriod, default=LeavePeriod.EVENT
    )
    extra_when_travelling = models.DecimalField(
        _("extra if travelling"),
        max_digits=4,
        decimal_places=1,
        default=0,
        help_text=_("Art. 37.3.b bis adds two days when the event needs a journey."),
    )

    #: Who puts it into the record. The request-and-approve flow fits what a
    #: person asks for; it does not fit what the company decides (an ERTE, a
    #: disciplinary suspension) or a fact nobody approves (a strike --- the
    #: right is exercised, not granted). Company-recorded kinds never appear in
    #: the worker's request dialog and never sit in the pending queue: whoever
    #: manages working time records them, already in force.
    initiated_by = models.CharField(
        _("who records it"),
        max_length=8,
        choices=[
            ("PERSON", _("The person requests it")),
            ("COMPANY", _("The company records it")),
        ],
        default="PERSON",
    )

    paid = models.BooleanField(_("paid"), default=True)
    vacation_recovery = models.CharField(
        _("recovers holiday"),
        max_length=20,
        blank=True,
        choices=[
            ("UNLIMITED", _("Yes, with no deadline")),
            ("EIGHTEEN_MONTHS", _("Yes, within eighteen months")),
        ],
        help_text=_(
            "Whether overlapping with booked holiday gives the right to take it later, "
            "and by when. Art. 38.3 ET sets two different regimes."
        ),
    )
    needs_justification = models.BooleanField(_("needs a supporting document"), default=False)
    note = models.TextField(_("note"), blank=True, validators=[validate_texto_legible])
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("leave type")
        verbose_name_plural = _("leave types")
        ordering = ["family", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=models.Q(code__gt=""),
                name="one_leave_type_per_code",
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def measured_in_hours(self) -> bool:
        """Whether asking for it in hours is the natural shape.

        The ones with no fixed limit and the ones counted in hours: a medical
        appointment, an exam, the four days of art. 37.9. Used only to decide
        what the form offers first --- any leave can still be part of a day.
        """
        return self.unit == LeaveUnit.HOURS or self.amount is None


#: Absences that claim their days entirely: no work is expected at all.
#:
#: Two kinds do not qualify, and both are people who DO work that day: a
#: part-day absence (hours at the doctor, the rest of the day worked) and a
#: suspension that reduces the working day instead of stopping it (an ERTE at
#: 40 % still expects the other 60 %). Every place that asks "is this person
#: off?" must use this same filter --- the punch block and the roster clash
#: each had their own copy of half of it, and each was wrong in a different
#: way.
STOPS_THE_WHOLE_DAY = models.Q(start_time__isnull=True) & (
    models.Q(reduction_share__isnull=True) | models.Q(reduction_share__gte=100)
)

#: Suspensions that reduce the day rather than stop it. The complement of the
#: reduction part of the filter above, named because the overlap check needs
#: to ask for exactly these.
REDUCES_THE_DAY = models.Q(reduction_share__isnull=False, reduction_share__lt=100)


class AbsenceStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")


class Absence(TenantOwnedModel):
    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="absences",
        verbose_name=_("employee"),
    )
    #: The specific kind, from the company's catalogue. Null on the rows that
    #: existed before there was a catalogue, and on anything created through an
    #: older client: `absence_type` below still carries the family.
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="absences",
        verbose_name=_("leave type"),
    )
    #: The family. Kept alongside the type rather than read through it because
    #: every query in the product asks this question and none of them ask the
    #: other --- and because it has to survive a leave type being renamed. Set
    #: from the type when there is one, so the two cannot disagree.
    absence_type = models.CharField(_("type"), max_length=20, choices=AbsenceType)

    start_date = models.DateField(_("from"))
    end_date = models.DateField(_("to"))

    # Part of a day. Empty on both means whole days, which is what leave was
    # until now --- and why somebody leaving at eleven with a fever could not be
    # recorded at all: the clock-out stood at 11:00, the day added up to three
    # hours, and nothing said why.
    #
    # Only on a single day. "From Monday at two until Wednesday at eleven" is a
    # shape the arithmetic can express and nobody asks for; refusing it keeps
    # every sum in this app honest about what a partial day is.
    start_time = models.TimeField(_("from (time)"), null=True, blank=True)
    end_time = models.TimeField(_("to (time)"), null=True, blank=True)

    # The one suspension that is not all-or-nothing. An ERTE under art. 47 can
    # suspend the contract **or reduce the working day** by a percentage, for
    # months. The second shape does not fit "no work expected": the person still
    # comes in, for less time, and a roster read against their full contract
    # comes out as a breach on every single week.
    #
    # Empty means the whole of it, which is what every other absence is. A
    # figure means the share of the day that stops --- 40 means they work 60 %.
    reduction_share = models.DecimalField(
        _("share reduced (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Only for a suspension that reduces the working day instead of stopping "
            "it. Empty means the whole day. 40 means they still work 60 %."
        ),
    )
    reason = models.TextField(_("reason"), blank=True, validators=[validate_texto_legible])

    #: Quién la metió, que no siempre es de quién es.
    #:
    #: La fila decía de quién son las vacaciones y quién las aprobó, y se
    #: callaba lo del medio: si las pidió esa persona o se las pusieron. Son dos
    #: hechos distintos y el art. 38.3 se apoya justo en esa diferencia ---el
    #: plazo de dos meses existe para que a nadie le fijen las fechas encima---,
    #: así que sin este dato no se puede ni avisar ni, más tarde, explicar por
    #: qué unas vacaciones empezaron cuando empezaron.
    #:
    #: Vacío en las de antes: para ellas el dato no existe y ponerlo a alguien
    #: sería inventarlo.
    requested_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="absences_requested",
        verbose_name=_("recorded by"),
    )

    status = models.CharField(
        _("status"), max_length=10, choices=AbsenceStatus, default=AbsenceStatus.PENDING
    )
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="absences_resolved",
        verbose_name=_("resolved by"),
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)

    justification = models.FileField(
        _("supporting document"),
        upload_to="justifications/%Y/%m/",
        blank=True,
        validators=[validate_extension, validate_content, validate_size],
        help_text=_(
            "Not available for sick leave: the medical certificate is not stored "
            "here. Since RD 1060/2022 the worker no longer hands it to the "
            "employer --- the INSS sends the data to the company directly."
        ),
    )

    class Meta:
        verbose_name = _("absence")
        verbose_name_plural = _("absences")
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["tenant", "employee", "status"]),
            models.Index(fields=["employee", "status", "start_date", "end_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="absence_ends_after_it_starts",
            ),
            # In the database, not just in a form. A medical certificate is
            # health data (art. 9 GDPR), and the ways into this table are many:
            # an import, a shell, a serializer somebody forgets to validate. A
            # check that lives here cannot be walked around.
            models.CheckConstraint(
                condition=~models.Q(absence_type=AbsenceType.SICK_LEAVE)
                | models.Q(justification=""),
                name="no_medical_certificate_is_stored",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_absence_type_display()} {self.start_date} → {self.end_date}"

    @property
    def stops_the_whole_day(self) -> bool:
        """Whether nothing at all is expected on these days.

        Everything except a part-day absence and an ERTE that reduces rather
        than suspends. Those two are why clocking in is not simply forbidden
        whenever there is approved leave.
        """
        return not self.is_partial and (self.reduction_share is None or self.reduction_share >= 100)

    @property
    def working_share(self) -> float:
        """The fraction of the ordinary day still expected, as 0..1.

        One for anything that is not a partial reduction, so a caller can
        multiply by it without asking which kind it has in its hands.
        """
        if self.reduction_share is None:
            return 1.0
        return max(0.0, 1 - float(self.reduction_share) / 100)

    @property
    def is_partial(self) -> bool:
        """Part of one day rather than whole days."""
        return self.start_time is not None and self.end_time is not None

    @property
    def hours(self) -> float:
        """How long a partial absence lasts. Zero for a whole-day one.

        Zero and not the length of the working day: how long a whole day is
        depends on the roster, the contract and the person, and answering it
        here would be inventing the one figure this model does not hold.
        """
        if not self.is_partial:
            return 0.0
        started = self.start_time.hour * 60 + self.start_time.minute
        ended = self.end_time.hour * 60 + self.end_time.minute
        return (ended - started) / 60

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": _("The end date cannot precede the start date.")})

        partial = self.start_time is not None or self.end_time is not None
        if partial:
            if self.start_time is None or self.end_time is None:
                raise ValidationError(
                    {"end_time": _("Give both times, or neither: half of a range is not one.")}
                )
            if self.end_time <= self.start_time:
                raise ValidationError({"end_time": _("It ends before it starts.")})
            if self.start_date != self.end_date:
                raise ValidationError(
                    {
                        "end_date": _(
                            "Part of a day is one day. For several days, leave the times "
                            "empty and they count whole."
                        )
                    }
                )

        # Said properly, because "invalid field" would send somebody looking for
        # the bug rather than reading the reason.
        if self.absence_type == AbsenceType.SICK_LEAVE and self.justification:
            raise ValidationError(
                {
                    "justification": _(
                        "The medical certificate is not stored. Recording the absence, "
                        "its dates and its status is enough for working-time purposes, "
                        "and since RD 1060/2022 the worker does not hand the certificate "
                        "to the employer: the INSS sends the data to the company."
                    )
                }
            )

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class RecoveredHoliday(TenantOwnedModel):
    """Días de vacaciones que una baja se comió, y que no se pierden.

    Art. 38.3 ET. Si durante las vacaciones aparece una incapacidad temporal,
    esos días **no se han disfrutado**: se disfrutan después. Hasta el
    13/08/2026 el saldo los daba por gastados, que es quitarle días a alguien
    justo cuando está de baja.

    Dos regímenes distintos, y se confunden con facilidad porque el párrafo
    largo es el que NO caduca:

    - **Sin plazo** (párrafo 2.º): incapacidad derivada del embarazo, el parto o
      la lactancia natural, y las suspensiones de los arts. 48.4, 48.5 y 48.7.
      Se disfrutan al terminar la suspensión «aunque haya terminado el año
      natural a que correspondan».
    - **Dieciocho meses** (párrafo 3.º): el resto de contingencias --- enfermedad
      común, accidente no laboral, accidente de trabajo, enfermedad profesional.
      Hasta dieciocho meses desde el fin del año en que se originaron.

    Cuál de los dos aplica lo dice el catálogo (`LeaveType.vacation_recovery`),
    que lo copia del marco legal del país. Aquí no hay ninguna lista de códigos:
    un país con otras reglas trae las suyas y esto no cambia.

    **No devuelve los días solo.** Se detecta, se avisa, y un responsable lo
    confirma. Un automatismo que devuelve días es de los que después nadie sabe
    explicar delante de una inspección --- pero el derecho es del trabajador y no
    puede depender de que alguien se acuerde, así que lo pendiente se ve en la
    cola de decisiones y en la pantalla de la persona desde el primer día.
    """

    class Regime(models.TextChoices):
        UNLIMITED = "UNLIMITED", _("No deadline (art. 38.3, second paragraph)")
        EIGHTEEN_MONTHS = "EIGHTEEN_MONTHS", _("Eighteen months (art. 38.3, third paragraph)")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Waiting to be confirmed")
        CONFIRMED = "CONFIRMED", _("Confirmed")
        DISMISSED = "DISMISSED", _("Not applicable")

    employee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="recovered_holidays",
        verbose_name=_("employee"),
    )
    #: Las vacaciones que se pisaron, y la baja que las pisó. Las dos, porque
    #: sin la segunda no se puede explicar de dónde sale el derecho.
    holiday = models.ForeignKey(
        Absence,
        on_delete=models.CASCADE,
        related_name="recoveries",
        verbose_name=_("holiday affected"),
    )
    sick_leave = models.ForeignKey(
        Absence,
        on_delete=models.CASCADE,
        related_name="recoveries_caused",
        verbose_name=_("leave that overlapped"),
    )

    first_day = models.DateField(_("from"))
    last_day = models.DateField(_("to"))
    #: En la unidad en que la empresa cuenta las vacaciones, que es la única en
    #: la que el saldo sabe restar.
    days = models.PositiveSmallIntegerField(_("days"))
    working_days = models.BooleanField(_("counted in working days"), default=True)

    regime = models.CharField(_("regime"), max_length=20, choices=Regime)
    #: Nulo en el régimen sin plazo. No es «sin fecha todavía»: es que no la hay.
    expires_on = models.DateField(_("must be taken by"), null=True, blank=True)

    status = models.CharField(
        _("status"), max_length=12, choices=Status, default=Status.PENDING, db_index=True
    )
    confirmed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="holiday_recoveries_confirmed",
        verbose_name=_("confirmed by"),
    )
    confirmed_at = models.DateTimeField(_("confirmed at"), null=True, blank=True)
    note = models.CharField(_("note"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("recovered holiday")
        verbose_name_plural = _("recovered holidays")
        constraints = [
            # Un mismo solapamiento no puede anotarse dos veces: la detección
            # corre cada vez que se aprueba o se cambia una baja.
            models.UniqueConstraint(
                fields=["holiday", "sick_leave", "first_day"],
                name="one_recovery_per_overlap",
            )
        ]

    def __str__(self) -> str:
        return f"{self.days} d · {self.employee_id} · {self.first_day}"


@receiver(post_delete, sender=Absence)
def _borrar_el_justificante_al_borrar_la_fila(sender, instance, **kwargs):
    """El fichero se va con su fila. Siempre, y solo si la fila se fue de verdad.

    Django dejó de borrar ficheros al borrar filas en la 1.3, y tiene razones:
    dos filas pueden apuntar al mismo fichero, y una transacción que se revierte
    no devuelve lo borrado. Pero aquí no hacerlo tiene un coste concreto. Un
    justificante es a menudo un dato del art. 9 del RGPD, y quien retira su
    solicitud está diciendo exactamente que no quiere que se quede. Sin esto, el
    fichero sobrevive sin que nada lo apunte: ni fila, ni pantalla, ni comando.
    La empresa no podría atender una supresión (art. 17) ni cumplir su propio
    plazo de conservación (art. 5.1.e), porque no sabría que existe.

    **`post_delete` y no `Absence.delete()`**, porque `QuerySet.delete()` no
    llama al método del modelo: el borrado en masa ---una purga por retención,
    una empresa que se va--- se saltaría la limpieza justo cuando más ficheros
    hay en juego. La señal la reciben las dos vías.

    **Y dentro de `on_commit`**, que es la parte que no se puede omitir: borrar
    el fichero antes de que la transacción confirme deja, si algo la revierte,
    una fila viva apuntando a un fichero que ya no está. Eso es peor que el
    problema que arregla, porque la pantalla ofrece una descarga que falla y
    nadie sabe por qué.
    """
    fichero = instance.justification
    if not fichero:
        return

    nombre = fichero.name

    def quitarlo():
        try:
            fichero.storage.delete(nombre)
        except Exception:
            # El almacén puede estar caído o el fichero ya no estar. La fila ya
            # se ha ido y la respuesta ya ha salido, así que tumbar aquí no
            # arregla nada: queda anotado para que alguien lo barra.
            logger.warning("No se pudo borrar el justificante %s", nombre, exc_info=True)

    transaction.on_commit(quitarlo)
