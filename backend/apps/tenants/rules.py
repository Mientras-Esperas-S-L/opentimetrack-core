"""Working-time rules, as data.

ADR-0012 §3: the Core knows rules configurable per company and per collective
agreement, **not constants scattered through the code**. Each one carries its
legal basis so that anybody reading a warning can tell what is being applied and
why --- and can argue with it.

The values here are **starting points, not truths**. A collective agreement may
improve any of them, and the sector-specific regimes of RD 1561/1995 modify
several outright: driving time, on-call work, shift work handovers. The company
owns its compliance and has its own advisers; this holds the figures it gives us
and says out loud when a roster departs from them.

That is also why nothing here blocks. A product that refused to save a roster
breaking the twelve-hour rest would be unusable in transport, in healthcare
on-call, and in any shift changeover --- all of them lawful under their own
regime. It warns, it says on what basis, and it leaves the decision where it
belongs.
"""

from __future__ import annotations

from datetime import time

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class SpecialRegime(models.TextChoices):
    """Los regímenes de jornada especial del RD 1561/1995.

    **No cambian ninguna cifra por su cuenta.** Este producto ya deja que la
    empresa ajuste sus números y avisa cuando se apartan de la regla general;
    lo que faltaba era **por qué** se apartan. Un descanso diario de diez horas
    en vez de doce no dice nada por sí solo: dicho junto a «transporte por
    carretera», dice que es el art. 8.3 y no un descuido.

    Meter aquí las quince cifras de los quince regímenes sería otra cosa, mucho
    más grande y bastante peor: cada sector tiene además su convenio, y un
    número nuestro pisando el suyo se leería como la ley.

    El de **ampliación** y el de **limitación** están en la misma lista a
    propósito: los dos son razones para apartarse de la regla general, solo que
    en direcciones contrarias.
    """

    NONE = "", _("General rules")
    # Ampliaciones (arts. 4 a 10).
    URBAN_PROPERTY = "URBAN_PROPERTY", _("Caretaking of urban property")
    GUARDS = "GUARDS", _("Guards and security")
    FARMING = "FARMING", _("Farm work")
    RETAIL_HOSPITALITY = "RETAIL_HOSPITALITY", _("Retail and hospitality")
    ROAD_TRANSPORT = "ROAD_TRANSPORT", _("Road transport")
    RAIL = "RAIL", _("Rail transport")
    SEA = "SEA", _("Work at sea")
    AIR = "AIR", _("Air transport")
    HEALTHCARE = "HEALTHCARE", _("Healthcare, with on-call duty")
    # Limitaciones (arts. 23 a 34).
    HAZARDOUS = "HAZARDOUS", _("Exposure to environmental hazards")
    COLD_STORAGE = "COLD_STORAGE", _("Cold storage rooms")
    MINING = "MINING", _("Mining and underground work")
    CONSTRUCTION = "CONSTRUCTION", _("Construction and public works")


class WorkingTimeRules(BaseModel):
    """The figures a company works to, with the article each one comes from."""

    tenant = models.OneToOneField(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="working_time_rules",
        verbose_name=_("company"),
    )

    #: De dónde salió cada cifra, cuando la puso una ficha de convenio.
    #:
    #: `{"daily_rest_hours": {"basis": "Art. 16", "note": "«Entre el final…»",
    #: "agreement": "Convenio estatal de jardinería"}}`
    #:
    #: El docstring de esta clase prometía «la cifra con el artículo del que
    #: viene» y el artículo no se guardaba: se tomaba siempre del marco del
    #: país. Medido con la ficha de jardinería: el convenio fija el descanso
    #: entre jornadas por su art. 16 y la pantalla lo atribuía al art. 34.3 ET.
    #:
    #: La cifra coincidía en ese caso ---doce horas las dos--- y el problema no
    #: es la cifra: es la procedencia. Cuando el convenio se renueve, nadie
    #: sabrá que ese valor venía de él; y ante una inspección, la empresa tiene
    #: que poder decir qué norma aplica, no una parecida.
    #:
    #: La `note` va también porque es donde la asesoría deja la cita textual y
    #: el razonamiento de la conversión, que era trabajo hecho y no se veía.
    from_agreement = models.JSONField(
        _("figures taken from an agreement"), default=dict, blank=True
    )

    weekly_hours = models.DecimalField(
        _("weekly hours"),
        max_digits=4,
        decimal_places=1,
        default=40,
        # The article and the explanation live in `apps.legal`, keyed by
        # country, and reach the screen through the API. Repeating them here
        # would be a second copy to keep in step --- which is what the frontend
        # was already doing, wrongly.
        help_text=_("Hours a week. See the citation served with the rules."),
    )
    daily_rest_hours = models.PositiveSmallIntegerField(
        _("rest between working days (hours)"),
        default=12,
        help_text=_("Hours between the end of a working day and the start of the next."),
    )
    weekly_rest_hours = models.PositiveSmallIntegerField(
        _("weekly rest (hours)"),
        default=36,
        help_text=_("Uninterrupted hours of weekly rest."),
    )
    break_after_hours = models.DecimalField(
        _("a continuous day needs a break after (hours)"),
        max_digits=3,
        decimal_places=1,
        default=6,
        help_text=_("A continuous day longer than this is owed a break."),
    )
    break_minutes = models.PositiveSmallIntegerField(_("break (minutes)"), default=15)
    break_counts_as_work = models.BooleanField(
        _("the break counts as working time"),
        default=False,
        help_text=_(
            "Only when the agreement or the contract says so. Assuming it would "
            "overstate the hours worked."
        ),
    )
    annual_overtime_hours = models.PositiveSmallIntegerField(
        _("overtime hours per year"),
        default=80,
        help_text=_("Overtime hours allowed per year."),
    )
    night_starts_at = models.TimeField(
        _("night work starts at"),
        default=time(22, 0),
        help_text=_("Start of the night window."),
    )
    night_ends_at = models.TimeField(_("night work ends at"), default=time(6, 0))
    correction_consent_days = models.PositiveSmallIntegerField(
        _("days to answer a proposed correction"),
        default=7,
        help_text=_(
            "Days to answer a proposed change before the company may apply it "
            "anyway, recorded as made without agreement."
        ),
    )
    complementary_hours_share = models.PositiveSmallIntegerField(
        _("complementary hours, share of the contract (%)"),
        default=30,
        help_text=_(
            "Cap on hours a part-time contract may work beyond what was agreed, "
            "as a percentage of it."
        ),
    )
    # Flexibility, not leniency. A window round the rostered start turns a 9:20
    # into a variation rather than an incident, which is how a company stops
    # fighting every five-minute slip. It does NOT hide overtime: overtime is
    # time worked BEYOND the expected day plus this margin, and it still
    # surfaces --- the difference between a lawful margin and a rigged rounding.
    entry_tolerance_minutes = models.PositiveSmallIntegerField(
        _("entry tolerance (minutes)"),
        default=0,
        help_text=_(
            "A punch within this many minutes of the rostered start counts as on time. 0 is strict."
        ),
    )
    exit_tolerance_minutes = models.PositiveSmallIntegerField(
        _("exit tolerance (minutes)"),
        default=0,
        help_text=_("Leaving within this many minutes of the rostered end is not early."),
    )

    # Art. 88 LOPDGDD: derecho a la desconexión digital. Un recordatorio de
    # «tienes la jornada abierta» se dispara al pasar el fin del turno, así que
    # un turno que acaba a las 22:00 podía sonar a las 23:30 --- y el aviso de
    # las 23:30 ya no recuerda nada, solo molesta.
    #
    # Fuera de esta ventana no se manda nada. No se acumula para el día
    # siguiente: un recordatorio de ayer no es un recordatorio.
    quiet_from = models.TimeField(
        _("no notifications from"),
        default=time(21, 0),
        help_text=_("Art. 88 LOPDGDD: the right to disconnect. Nothing is sent after this."),
    )
    quiet_until = models.TimeField(
        _("no notifications until"),
        default=time(7, 0),
        help_text=_("Nothing is sent before this either."),
    )

    roster_notice_days = models.PositiveSmallIntegerField(
        _("notice for roster changes (days)"),
        default=5,
        help_text=_("Days of notice before a roster change."),
    )

    #: El régimen del RD 1561/1995 bajo el que trabaja esta empresa, si alguno.
    #:
    #: Vacío es «las reglas generales», que es lo que le toca a la mayoría. Lo
    #: que aporta declararlo no es cambiar cifras ---no cambia ninguna--- sino
    #: dejar dicho **por qué** las de esta empresa se apartan de las del Estatuto.
    special_regime = models.CharField(
        _("special working time regime"),
        max_length=20,
        choices=SpecialRegime,
        blank=True,
        default="",
        help_text=_("RD 1561/1995. It changes no figure by itself: it says why yours differ."),
    )

    #: Tope de tiempo de presencia, en horas semanales de promedio al mes.
    #:
    #: «El tiempo de presencia no podrá exceder en ningún caso de veinte horas
    #: semanales de promedio en un periodo de referencia de un mes» (art. 8.b
    #: RD 1561/1995). Es de transporte por carretera, y por eso solo se
    #: comprueba cuando ese es el régimen declarado: aplicarlo a una oficina
    #: sería inventarle un límite que su sector no tiene.
    #:
    #: Un cero lo apaga, para el convenio que fije el promedio de otra forma.
    standby_weekly_hours = models.PositiveSmallIntegerField(
        _("on-call hours a week, monthly average"),
        default=20,
        help_text=_("Art. 8.b RD 1561/1995, road transport only. 0 turns it off."),
    )

    #: En cuánto tiempo hay que compensar lo que se trabaja de más o de menos
    #: por distribución irregular de la jornada.
    #:
    #: **Es de la empresa y no nuestra.** El art. 34.2 dice que la compensación
    #: «será exigible según lo acordado en convenio colectivo o, a falta de
    #: previsión al respecto, por acuerdo entre la empresa y los representantes
    #: de los trabajadores», y solo **en defecto de pacto** pone los doce meses.
    #: Así que el número por defecto es el legal y el convenio lo cambia.
    #:
    #: Este campo es el sitio que faltaba. La cuenta del saldo se descartó en su
    #: día ---y con razón--- porque el producto no sabía si había pacto, y decir
    #: «te quedan tantas horas» a una empresa cuyo convenio dice otra cosa es
    #: decir algo falso con aire de dato. Preguntándolo, deja de serlo.
    #:
    #: Un cero apaga la comprobación: hay convenios que remiten a un cómputo
    #: distinto del plazo, y forzar un número inventado sería peor que callar.
    irregular_settlement_months = models.PositiveSmallIntegerField(
        _("settle irregular hours within (months)"),
        default=12,
        help_text=_(
            "Art. 34.2 ET, unless the collective agreement says otherwise. 0 turns it off."
        ),
    )

    # La frontera entre «cerró tarde» y «se olvidó de fichar la salida». No la
    # fija ningún artículo, y por eso es de la empresa y no nuestra.
    #
    # Dieciséis cubre la jornada partida más larga que se ve ---de 8:00 a 20:00
    # son doce horas de reloj--- con sitio para una salida tardía, y se queda
    # por debajo de veinticuatro para que un día entero de silencio se cace.
    # Pero hay plantillas de guardias de veinticuatro horas: bomberos,
    # residencias, vigilancia. Ahí dieciséis parte la guardia en dos y el
    # registro sale mal, que es justo el fallo que esto vino a arreglar.
    #
    # Subirlo tiene precio y conviene que lo pague quien decide: cuanto más
    # alto, más tarda en detectarse un olvido. Una empresa con guardias de
    # veinticuatro necesita algo más de veinticuatro, no cuarenta.
    max_open_hours = models.PositiveSmallIntegerField(
        _("longest a working day may stay open (hours)"),
        default=16,
        # Cero no quiere decir nada aquí, y se aceptaba: `PositiveSmallInteger`
        # lo admite y no había suelo. Con cero, los dos que leen este ajuste
        # dejaban de coincidir ---fichar caía a las dieciséis de por defecto y el
        # informe se quedaba con el cero--- así que una jornada de noche bien
        # fichada salía en pantalla y en el documento como «entrada sin salida».
        validators=[MinValueValidator(1)],
        help_text=_(
            "After this, an unclosed working day is read as a forgotten clock-out "
            "rather than a shift still running. Raise it for 24-hour on-call rosters."
        ),
    )

    class Meta:
        verbose_name = _("working time rules")
        verbose_name_plural = _("working time rules")

    def __str__(self) -> str:
        return f"{self.tenant_id}: {self.weekly_hours} h/week"

    @classmethod
    def for_company(cls, company) -> WorkingTimeRules:
        """The company's rules, creating them the first time from its country.

        Every company has them, so a missing row is a gap in setup rather than a
        meaningful state. Returning defaults beats making every caller handle
        `None` and quietly skip the checks.

        The figures come from `apps.legal`, keyed on `Tenant.country`. The field
        defaults below stay as Spain's --- they are what a row created by a
        migration or a fixture gets --- but a company created through the product
        starts on its own country's law.
        """
        from apps.legal import for_company as framework_for

        # Recordadas en la propia empresa mientras dure la petición.
        #
        # Son las mismas reglas para toda ella y esto se llama desde dentro de
        # los bucles: una lectura de horas extra pendientes pedía **482 veces**
        # la misma fila. El objeto `Tenant` vive lo que la petición, así que el
        # recuerdo se muere con ella y no hay nada que invalidar.
        #
        # Un proceso largo que cambie las reglas y siga usando el mismo objeto
        # vería las de antes. Es el precio, y se paga barato: quien las cambia
        # es la pantalla de ajustes, que trae su propia instancia.
        recordadas = getattr(company, "_working_time_rules", None)
        if recordadas is not None:
            return recordadas

        framework = framework_for(company)
        rules, _created = cls.objects.get_or_create(tenant=company, defaults=framework.defaults)
        company._working_time_rules = rules
        return rules


# ---------------------------------------------------------------- under eighteen
#
# They used to be six constants here, and the reasoning for keeping them out of
# `WorkingTimeRules` was right and still is: no agreement can lower them, so a
# setting for them would be a setting whose only use is breaking the law.
#
# What was wrong is that they were **Spain's** floors written as the product's.
# They now live in `apps.legal.es`, next to the articles that impose them, and a
# company in another country gets that country's --- or, failing that, the
# directive's.
#
# These names are kept as a thin forwarding layer so the existing call sites and
# their tests read the same. New code should ask the framework directly:
#
#     from apps.legal import for_company
#     for_company(company).minors.max_daily_hours

from apps.legal import DIRECTIVE  # noqa: E402
from apps.legal.es import ESPANA  # noqa: E402

MINOR_MAX_DAILY_HOURS = ESPANA.minors.max_daily_hours
MINOR_BREAK_AFTER_HOURS = ESPANA.minors.break_after_hours
MINOR_BREAK_MINUTES = ESPANA.minors.break_minutes
MINOR_WEEKLY_REST_HOURS = ESPANA.minors.weekly_rest_hours
MINOR_NIGHT_WORK_FORBIDDEN = ESPANA.minors.night_work_forbidden
MINOR_OVERTIME_FORBIDDEN = ESPANA.minors.overtime_forbidden

__all__ = [
    "DIRECTIVE",
    "MINOR_BREAK_AFTER_HOURS",
    "MINOR_BREAK_MINUTES",
    "MINOR_MAX_DAILY_HOURS",
    "MINOR_NIGHT_WORK_FORBIDDEN",
    "MINOR_OVERTIME_FORBIDDEN",
    "MINOR_WEEKLY_REST_HOURS",
    "WorkingTimeRules",
]


class RecordBasis(models.TextChoices):
    """Las tres vías del art. 34.9, y ninguna es «no consta».

    «Mediante negociación colectiva o acuerdo de empresa o, en su defecto,
    decisión del empresario previa consulta con los representantes legales de
    los trabajadores en la empresa, se organizará y documentará este registro de
    jornada.»

    Son excluyentes y están ordenadas: la decisión del empresario es la de «en
    su defecto», y solo esa arrastra la consulta previa. Guardarlas como texto
    libre dejaría la diferencia en manos de cómo lo escribiera cada uno, y es
    justo la diferencia que decide si faltaba una consulta.
    """

    COLLECTIVE = "COLLECTIVE", _("collective agreement")
    COMPANY = "COMPANY", _("company-level agreement")
    EMPLOYER = "EMPLOYER", _("employer decision after consulting the representatives")


class RecordArrangement(models.Model):
    """Cómo se organizó el registro de jornada en esta empresa, y desde cuándo.

    El art. 34.9 pide dos cosas y el producto solo hacía una. Registrar la
    jornada, sí. **Documentar cómo se organizó ese registro**, no: no había
    dónde escribirlo, y es lo primero que una inspección pide después de los
    propios registros --- antes que ningún fichaje, porque decide si el sistema
    tiene amparo.

    Se guarda la constancia, no el acta. Que exista un documento, de qué fecha y
    con qué referencia es el hecho comprobable; el acta la custodia la empresa
    con sus otros papeles. Meter aquí un almacén de documentos traería su propia
    decisión de conservación ---esto no es registro de jornada, así que los
    cuatro años del artículo no le aplican--- y esa decisión no se toma de
    pasada.
    """

    tenant = models.OneToOneField(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="record_arrangement",
        verbose_name=_("company"),
    )

    basis = models.CharField(
        _("how it was organised"),
        max_length=12,
        choices=RecordBasis,
        blank=True,
        help_text=_("Art. 34.9 ET. Empty means it has not been declared yet."),
    )

    #: Cuál. «El convenio del metal de Sevilla» o «acuerdo de 3 de marzo con el
    #: comité»: sin esto la vía elegida no se puede comprobar contra nada.
    reference = models.CharField(_("which one"), max_length=200, blank=True)

    #: Desde cuándo rige. No es la fecha de hoy: un sistema puesto en marcha en
    #: 2023 y declarado ahora sigue rigiendo desde 2023, y la diferencia importa
    #: si alguien pregunta por un periodo anterior.
    in_force_since = models.DateField(_("in force since"), null=True, blank=True)

    #: La consulta previa a la representación, que solo pide la tercera vía.
    consulted_on = models.DateField(_("representatives consulted on"), null=True, blank=True)

    note = models.TextField(_("note"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("record arrangement")
        verbose_name_plural = _("record arrangements")

    def __str__(self) -> str:
        return f"{self.tenant_id} · {self.basis or 'sin declarar'}"

    @classmethod
    def for_company(cls, company):
        arrangement, _created = cls.objects.get_or_create(tenant=company)
        return arrangement

    @property
    def missing_consultation(self) -> bool:
        """Decisión del empresario sin constancia de haber consultado.

        Es el hueco concreto que el artículo señala, y el único que el producto
        puede afirmar mirando sus propios datos: las otras dos vías son un
        acuerdo, y un acuerdo no lleva consulta previa porque **es** la
        negociación.
        """
        return self.basis == RecordBasis.EMPLOYER and self.consulted_on is None


class ComputationRuleChange(models.Model):
    """Desde cuándo aplica cada valor de las dos reglas que deciden el cómputo.

    **Solo estas dos, y hay una razón para no versionar las dieciocho.** La
    distinción es la misma que separó el huso del resto en la vuelta 93: hay
    reglas que deciden **qué dice el registro** y reglas que deciden **si eso
    cumple**.

    `break_counts_as_work` y `max_open_hours` son del primer grupo: cambian
    cuántas horas figura que se trabajó y a qué día pertenece un turno de noche.
    Eso es un hecho, y el art. 34.9 lo quiere reproducible --- medido antes de
    esto, marcar que la pausa cuenta convertía un abril cerrado de 7:00 en 8:00 h,
    y bajar el tope pasaba un turno nocturno bien fichado a «entrada sin salida»
    con cero horas.

    Las otras dieciséis ---descanso diario, tope de horas extra, preaviso del
    cuadrante--- son del segundo, y **deben** recalcularse con lo vigente hoy: si
    un convenio nuevo mejora el descanso, se quiere ver qué días de antes no lo
    cumplirían. Congelarlas escondería precisamente eso.

    **La fecha la declara quien cambia la regla.** El sistema no puede saber
    desde cuándo aplica un convenio, y poner «desde hoy» por su cuenta sería
    tomar una decisión laboral que no le toca.

    Sin ninguna fila, todo el pasado se lee con los valores actuales de
    `WorkingTimeRules`, que es exactamente lo que hacía antes: esto no reescribe
    nada al llegar.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="computation_rule_changes",
        verbose_name=_("company"),
    )
    effective_from = models.DateField(
        _("in force since"),
        help_text=_("The day this way of counting starts to apply. Days before it keep theirs."),
    )
    break_counts_as_work = models.BooleanField(_("the break counts as working time"))
    max_open_hours = models.PositiveSmallIntegerField(
        _("longest a working day may stay open (hours)"),
        validators=[MinValueValidator(1)],
    )
    #: Quién lo declaró. Un cambio que mueve las horas de un periodo cerrado no
    #: puede ser anónimo.
    recorded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("declared by"),
    )
    note = models.CharField(
        _("note"),
        max_length=300,
        blank=True,
        help_text=_("What agreement or decision this comes from."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("change in how time is counted")
        verbose_name_plural = _("changes in how time is counted")
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "effective_from"],
                name="one_computation_change_per_day",
            )
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id} desde {self.effective_from}"

    @classmethod
    def in_force_on(cls, company, day):
        """Cómo se contaba ese día, o los valores de hoy si no consta.

        Devuelve algo con `break_counts_as_work` y `max_open_hours`, sea una fila
        del historial o las reglas actuales. Quien llama no tiene que saber cuál
        de las dos le ha tocado.
        """
        vigente = (
            cls.objects.filter(tenant=company, effective_from__lte=day)
            .order_by("-effective_from")
            .first()
        )
        return vigente or WorkingTimeRules.for_company(company)
