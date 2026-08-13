"""Filtering a list by a range of days.

Every screen that shows history needs it, and until now none of them had it:
the clock events, the trail and the absences all answered with whatever the
first page happened to hold. Fifty rows is about a day and a half of a small
company's punches, so "the record" on screen was a slice with no way to reach
the rest and nothing saying so.

The subtlety is where a day ends. `?from=2026-08-01` means the first of August
**where the company is**, not in UTC, and the two differ for anywhere east or
west of Greenwich --- inside Spain already, for a company in the Canary Islands.
Filtering a `DateTimeField` against a bare date would quietly move the boundary
by an hour or two and drop punches near midnight from the range they belong to.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, time, timedelta

import django_filters
from django.utils.translation import gettext_lazy as _
from rest_framework.filters import SearchFilter


def _sin_acentos(texto: str) -> str:
    """«García» → «Garcia». La misma cuenta que hace el navegador.

    Se descompone y se tiran las marcas: así la eñe se queda en ene, que es
    lo que teclea quien busca sin acordarse de la tilde.
    """
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


class LocalDayRangeFilter(django_filters.FilterSet):
    """Adds `from` and `to`, inclusive, read in the company's own zone.

    Subclasses set `day_field` to the `DateTimeField` being sliced.

    Both ends are inclusive because that is what somebody typing two dates into
    a form means. `to=2026-08-31` includes everything on the 31st, which is why
    the upper bound is the start of the next day and the comparison is `lt`.
    """

    day_field = "timestamp"

    date_from = django_filters.DateFilter(method="filter_from", label=_("from this day, inclusive"))
    date_to = django_filters.DateFilter(method="filter_to", label=_("to this day, inclusive"))

    @property
    def _zone(self):
        # The company is on the request; falling back to UTC would silently
        # shift the boundary rather than fail, so this is only for the schema
        # generator, which builds the filterset without a request.
        company = getattr(getattr(self.request, "user", None), "tenant", None)
        return company.tzinfo if company else None

    def _boundary(self, day, *, plus_a_day=False):
        zone = self._zone
        if zone is None:
            return None
        if plus_a_day:
            day = day + timedelta(days=1)
        return datetime.combine(day, time.min, tzinfo=zone)

    def filter_from(self, queryset, name, value):
        edge = self._boundary(value)
        return queryset if edge is None else queryset.filter(**{f"{self.day_field}__gte": edge})

    def filter_to(self, queryset, name, value):
        edge = self._boundary(value, plus_a_day=True)
        return queryset if edge is None else queryset.filter(**{f"{self.day_field}__lt": edge})


class BusquedaSinAcentos(SearchFilter):
    """`?search=` ignorando los acentos, en los dos lados.

    Nadie teclea «García» con tilde buscando a García, y hasta ahora eso
    devolvía cero: `search=garcia` no encontraba a Ana García, ni `ibanez` a
    Rocío Ibáñez. Con una plantilla española eso es la mitad de los apellidos
    ---y también los nombres de centro («Almacén»), que se buscan igual.

    En el buscador de personas quedaba tapado porque la lista completa cabe en
    una página y el recorte que hace el navegador sí ignora los acentos. Deja
    de taparlo en cuanto la empresa no cabe en una página: entonces lo que no
    esté en la página cargada solo lo puede encontrar el servidor.

    Los dos lados, que es la parte que se olvida: la columna se compara sin
    acentos ---`unaccent` de PostgreSQL--- y el término también se le quitan
    aquí. Si solo se hiciera la columna, teclear «García» **con** tilde dejaría
    de encontrarla, que es cambiar un fallo por el contrario.

    El coste es un recorrido de la tabla, porque `unaccent()` sobre la columna
    no usa el índice. Para una plantilla es irrelevante ---son miles de filas,
    no millones--- y la alternativa (una columna normalizada con su índice)
    solo hace falta si algún día esto se queda corto.
    """

    def get_search_terms(self, request):
        return [_sin_acentos(t) for t in super().get_search_terms(request)]

    def construct_search(self, field_name, queryset):
        busqueda = super().construct_search(field_name, queryset)
        # Solo las de texto suelto. Un `=` (exacto), un `@` (texto completo) o
        # un `$` (expresión regular) piden otra cosa y se dejan como están.
        for lookup in ("icontains", "istartswith"):
            if busqueda.endswith(f"__{lookup}"):
                return f"{busqueda[: -len(lookup)]}unaccent__{lookup}"
        return busqueda
