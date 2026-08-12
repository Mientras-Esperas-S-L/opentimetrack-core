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

from datetime import datetime, time, timedelta

import django_filters
from django.utils.translation import gettext_lazy as _


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
