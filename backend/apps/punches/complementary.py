"""Las horas complementarias de un contrato a tiempo parcial, y su tope.

Es la única protección que el trabajo a tiempo parcial tiene de verdad. El art.
12.4.c prohíbe las horas extraordinarias en un contrato parcial; lo que sí se
puede pedir por encima de lo pactado son **complementarias**, y si esas no
tienen techo la prohibición de las extras no le compra nada a nadie.

**El techo va sobre el periodo del contrato, no sobre el mes.** El art. 12.5.c
dice «el treinta por ciento de las horas ordinarias de trabajo objeto del
contrato», y el objeto del contrato se pacta por semana, por mes o por año ---
art. 12.1 ---. Un contrato de 800 horas al año tiene 240 complementarias al año,
no 20 al mes: repartirlas por meses inventaría un límite mensual que nadie pactó
y que la ley no impone. Es la misma razón por la que `agreed_hours` devuelve el
periodo en vez de convertirlo a semanas.

**Se cuentan derivándolas, no leyendo una marca.** El campo `hours_nature`
existe y la API lo acepta, pero ninguna pantalla lo manda: si la cuenta
dependiera de él, sería cero para siempre y el aviso no llegaría nunca. Y no
hace falta, porque el art. 12.5.a las define por lo que son ---las realizadas
como adición a las ordinarias pactadas---, así que salen de restar. Una marca
explícita dice de qué tipo es una hora; no hace falta para saber cuántas hay por
encima del contrato.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from datetime import time as dt_time

from django.utils import timezone

from apps.users.models import HoursPeriod


def _window(day: date, period: str) -> tuple[date, date]:
    """El tramo natural del periodo que contiene ese día, los dos extremos dentro.

    Naturales y no móviles: la semana empieza el lunes, el mes el día uno y el
    año en enero. Una ventana móvil ---«los últimos treinta días»--- daría un
    tope que cambia cada mañana y que nadie puede comprobar en un calendario.
    """
    if period == HoursPeriod.WEEK:
        monday = day - timedelta(days=day.weekday())
        return monday, monday + timedelta(days=6)
    if period == HoursPeriod.MONTH:
        return day.replace(day=1), day.replace(day=monthrange(day.year, day.month)[1])
    return date(day.year, 1, 1), date(day.year, 12, 31)


def complementary_used(*, employee, company, day: date | None = None) -> dict | None:
    """Lo trabajado por encima del contrato en el periodo en curso, contra el tope.

    Devuelve `None` cuando la pregunta no aplica, que no es lo mismo que cero:

    - **No es tiempo parcial.** Las complementarias son una figura del art. 12 y
      no existen fuera de él. Una jornada reducida por guarda legal trabaja menos
      horas y **no** es tiempo parcial: su contrato sigue siendo completo.
    - **No hay jornada pactada** contra la que medir, que es el caso de un
      régimen variable.

    Lo que devuelve, cuando aplica: la ventana, lo pactado en ella, lo trabajado,
    la diferencia por arriba, el tope y si se ha pasado.
    """
    from apps.punches.models import Punch, PunchInterval, PunchType
    from apps.tenants.rules import WorkingTimeRules

    if not employee.part_time:
        return None

    rules = WorkingTimeRules.for_company(company)
    agreed = employee.agreed_hours(rules)
    if agreed is None:
        return None
    contracted, period = agreed

    day = day or timezone.localdate()
    first, last = _window(day, period)

    zone = company.tzinfo
    punches = Punch.objects.filter(
        employee=employee,
        timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        timestamp__lt=datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=zone),
        is_active=True,
    ).order_by("timestamp")

    # Emparejar los eventos en tramos trabajados. Uno abierto se deja fuera en
    # vez de adivinarle un final: inventar la salida metería en el total horas
    # que nadie registró, y este total decide si se avisa de un tope legal.
    #
    # Las pausas que no son tiempo de trabajo (art. 3.d) tampoco suman: el tramo
    # que abre un evento marcado `BREAK` es precisamente el que no cuenta.
    worked = timedelta()
    opening = None
    for punch in punches:
        if punch.punch_type == PunchType.IN:
            opening = punch
        elif opening is not None:
            if opening.interval == PunchInterval.WORK:
                worked += punch.timestamp - opening.timestamp
            opening = None

    hours = worked.total_seconds() / 3600
    over = max(0.0, hours - contracted)
    cap = contracted * (rules.complementary_hours_share / 100)

    return {
        "first": first,
        "last": last,
        "period": period,
        "contracted_hours": round(contracted, 1),
        "worked_hours": round(hours, 1),
        "complementary_hours": round(over, 1),
        "cap_hours": round(cap, 1),
        "share": rules.complementary_hours_share,
        # Con el tope a cero no hay nada que comparar, y avisar de que se ha
        # pasado de cero en cuanto trabaja un minuto de más sería ruido.
        "over_the_cap": cap > 0 and over > cap,
    }
