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


def local_date_of(instant, where) -> date:
    """El día que era, para quien lo vivió. `local_today` para un instante dado.

    `instante.date()` tiene la misma trampa que `date.today()` y se ve menos:
    un `DateTimeField` se guarda en UTC, así que algo creado a las 00:30 de
    Madrid devuelve **el día anterior**. Da igual mientras solo se enseñe, y
    deja de dar igual en cuanto se resta ---«¿cuántos días de aviso hubo?»---,
    que es donde un día de menos cambia la respuesta.
    """
    return timezone.localtime(instant, where.tzinfo).date()
