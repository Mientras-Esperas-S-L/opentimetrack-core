"""Public holidays: the fourteen days a year nobody is expected to work.

Art. 37.2 ET: fourteen at most, of which **two are local**. Four are national
and irrenunciables --- New Year, 1 May, 12 October and Christmas --- the region
sets the rest of the twelve, and the town hall picks the last two.

That shape decides the design. A holiday belongs to a **place**, not to a
company: two sites of the same firm in different provinces do not share their
last two days, and one in the Canary Islands does not share several more. So a
row either names a workplace or applies to everybody.

## Where the days come from

Three layers, and only two of them can be automated.

**National and regional** are published once a year in a single resolution in
the BOE, in October for the year after. Those ship with the product as files
under `holidays/`, transcribed and cited exactly like the collective agreement
fichas, and an administrator imports the year they need.

**Local** cannot. The two days are proposed by each town hall and approved by
the region, and they end up scattered across half a hundred provincial
bulletins and eight thousand municipalities, plenty of them as a PDF. There is
no national register of them worth reading by machine. So they are typed in,
per workplace, and the product says so rather than pretending.

## What a holiday does here

It is **not** a prohibition. Working a public holiday is lawful and generates
compensation --- rest, pay, or both, depending on the agreement --- so the
roster reports it and does not refuse it, the same as everything else in this
product.

What it does change is arithmetic: a holiday inside a stretch of leave is not a
day of holiday spent, because it was not a day the person was going to work.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TenantOwnedModel


class HolidayScope(models.TextChoices):
    """Where the day came from, which is not the same as who it applies to.

    Kept because provenance is a question people ask --- "why is the 28th off?"
    --- and because it is what an import has to be able to replace without
    touching the two days somebody typed in by hand.
    """

    NATIONAL = "NATIONAL", _("National")
    REGIONAL = "REGIONAL", _("Regional")
    LOCAL = "LOCAL", _("Local")
    COMPANY = "COMPANY", _("Company")


class PublicHoliday(TenantOwnedModel):
    """One day off, for everybody or for one workplace."""

    day = models.DateField(_("day"))
    name = models.CharField(_("name"), max_length=120)

    scope = models.CharField(
        _("origin"),
        max_length=10,
        choices=HolidayScope,
        default=HolidayScope.LOCAL,
    )

    #: Empty means the whole company. A local holiday names its workplace,
    #: because the two days of one town are not the two days of another.
    workplace = models.ForeignKey(
        "users.Workplace",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="holidays",
        verbose_name=_("workplace"),
        help_text=_("Empty applies it to the whole company."),
    )

    note = models.CharField(_("note"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("public holiday")
        verbose_name_plural = _("public holidays")
        ordering = ["day"]
        indexes = [models.Index(fields=["tenant", "day"])]
        constraints = [
            # Two constraints rather than one because Postgres treats NULLs as
            # distinct: a single unique on (tenant, day, workplace) would happily
            # accept the same company-wide day twice.
            models.UniqueConstraint(
                fields=["tenant", "day"],
                condition=models.Q(workplace__isnull=True),
                name="one_company_holiday_per_day",
            ),
            models.UniqueConstraint(
                fields=["tenant", "day", "workplace"],
                condition=models.Q(workplace__isnull=False),
                name="one_workplace_holiday_per_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.day} {self.name}"


def holidays_by_workplace(first, last) -> dict:
    """Los festivos del tramo, agrupados por centro, en una consulta.

    La respuesta de `holidays_for` depende solo del **centro** de la persona, no
    de la persona, así que preguntarla por cabeza es preguntar lo mismo muchas
    veces. La revisión del cuadrante lo hacía dentro de su bucle y crecía una
    consulta por empleado: doce para tres personas, veintiuna para doce, y más
    de doscientas para una plantilla de doscientas. Justo la pantalla que se
    abre para ver qué incumple el cuadrante de toda la empresa.

    La clave `None` son los festivos de toda la empresa, que le tocan a todo el
    mundo además de los suyos.
    """
    por_centro: dict = {}
    filas = PublicHoliday.objects.filter(day__gte=first, day__lte=last).values_list(
        "workplace_id", "day"
    )
    for workplace_id, dia in filas:
        por_centro.setdefault(workplace_id, set()).add(dia)
    return por_centro


def holidays_for(person, first, last, por_centro=None) -> set:
    """The days in the range that are holidays **for that person**.

    Their workplace's, plus the company-wide ones. Asked of the person rather
    than of the company because that is the only level at which the answer is
    single: two sites of the same firm do not share their last two days.

    `por_centro` es lo que devuelve `holidays_by_workplace`, ya traído de una
    vez. Sin él consulta por su cuenta, que está bien para una llamada suelta y
    era un N+1 dentro de un bucle.
    """
    if por_centro is None:
        rows = PublicHoliday.objects.filter(day__gte=first, day__lte=last).filter(
            models.Q(workplace__isnull=True) | models.Q(workplace_id=person.workplace_id)
        )
        return set(rows.values_list("day", flat=True))

    # Los de la empresa entera más los de su centro.
    return por_centro.get(None, set()) | por_centro.get(person.workplace_id, set())
