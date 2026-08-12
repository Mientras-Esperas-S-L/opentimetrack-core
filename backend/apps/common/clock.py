"""Whose "today" is it?

The server runs in UTC and Django's active timezone is the company's, set by
the middleware --- but neither is the person's. A worker in Las Palmas at 00:30
local is at 01:30 in Madrid and at 23:30 *yesterday* in UTC, and every check
that starts from "today" answers differently depending on which of the three
somebody happened to reach for.

`date.today()` is the trap: it is the container's UTC date, wrong for everybody
in Spain between midnight and 01:00 (02:00 in summer). It crept in four times
before this module existed.
"""

from __future__ import annotations

from datetime import date

from django.utils import timezone


def local_today(where) -> date:
    """Today, for anything that knows its zone: a person, a workplace, a company.

    A person answers with their workplace's zone, falling back to the
    company's, which is what makes this the right default for anything measured
    per person --- the same instant is Monday for the Madrid office and Sunday
    for the Canary delegation.
    """
    return timezone.now().astimezone(where.tzinfo).date()
