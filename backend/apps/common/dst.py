"""Las dos noches del año que no duran veinticuatro horas.

En España los relojes se adelantan el último domingo de marzo ---ese día tiene
23 horas--- y se atrasan el último de octubre, que tiene 25. Para casi todo el
producto da igual. Para un turno de noche no: quien entra a las 22:00 y sale a
las 06:00 trabaja siete horas en marzo y nueve en octubre.

**Los números que da el producto ya son correctos**, y conviene decirlo porque
es lo primero que uno duda. Los fichajes guardan instantes reales, así que la
jornada sale de siete y de nueve horas como debe. Lo que el cuadrante dice
---ocho--- también es correcto: es lo que se planificó, en reloj de pared.

El problema es que nadie explica la diferencia. La noche de octubre, cada
persona de la plantilla de noche aparece con sesenta minutos de horas extra, y
quien tiene que autorizarlas ve una docena de filas idénticas sin ningún motivo
a la vista. Y la de marzo, una hora menos trabajada que tampoco se explica.

Esas horas son reales y la ley va por el tiempo efectivamente trabajado, así
que no hay que corregir la cifra: hay que decir de dónde sale. Qué se hace
después con ella ---pagarla, compensarla, o que el convenio diga que la noche
cuenta por su nominal--- es una decisión de la empresa, y para tomarla hace
falta saber que hubo cambio de hora.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta


def local_day_hours(day: date, where) -> float:
    """Cuántas horas dura ese día en la zona de quien lo vive.

    Casi siempre 24. El día en que los relojes se adelantan, 23; el que se
    atrasan, 25. Fuera de Europa hay husos con saltos de media hora, así que
    devuelve un decimal y no un entero.
    """
    inicio = datetime.combine(day, time.min, tzinfo=where.tzinfo)
    siguiente = datetime.combine(day + timedelta(days=1), time.min, tzinfo=where.tzinfo)

    # A UTC antes de restar, y esto es la trampa entera de este módulo: restar
    # dos datetime **con el mismo `tzinfo`** es aritmética de reloj de pared,
    # no de tiempo real. Está en la documentación de Python y nadie la recuerda:
    # «if both are aware and have the same tzinfo attribute, the common tzinfo
    # attribute is ignored». La primera versión de esta función devolvía 24
    # horas los 365 días del año, incluida la del cambio, y parecía correcta.
    return (siguiente.astimezone(UTC) - inicio.astimezone(UTC)).total_seconds() / 3600


def clock_change_minutes(day: date, where) -> int:
    """Los minutos que ese día gana o pierde. 0 en los 363 días normales.

    Negativo cuando el día se acorta ---marzo, los relojes se adelantan--- y
    positivo cuando se alarga. Es el signo que hace falta para explicar una
    diferencia: en octubre sobran sesenta minutos, en marzo faltan.
    """
    return round((local_day_hours(day, where) - 24) * 60)


def real_gap(desde: datetime, hasta: datetime, where) -> timedelta:
    """Lo que de verdad pasa entre dos horas de reloj de pared.

    Un cuadrante guarda horas de pared: «acaba a las 22:00, empieza a las
    10:00». Restar esos dos datetime da doce horas los 365 días del año, porque
    son naive y la resta no sabe de husos --- y la madrugada del último domingo
    de marzo, entre esas dos horas de pared solo pasan **once**.

    Ahí es donde importa: el suelo del art. 34.3 son doce horas de descanso
    entre jornadas, y un cuadrante que programe esas doce de pared la noche del
    cambio deja a la persona con once reales sin que nada avise. La de octubre
    va al revés ---trece--- y no incumple nada, pero conviene que la cuenta sea
    la misma en los dos sentidos.

    Acepta datetime naive, que es como salen de un turno, y también aware, que
    es como salen de la base. `where` puede ser la empresa, la persona o la
    propia zona.
    """
    aqui = getattr(where, "tzinfo", where)
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=aqui)
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=aqui)
    # A UTC antes de restar, por lo mismo que explica `local_day_hours`: dos
    # datetime con el mismo `tzinfo` se restan como reloj de pared.
    return hasta.astimezone(UTC) - desde.astimezone(UTC)


def change_across(start, end, where) -> int:
    """Los minutos que el reloj se movió **entre esos dos instantes**.

    Es la forma que hace falta de verdad, y no la del día: un turno que entra el
    28 de marzo a las 22:00 cruza el cambio de la madrugada del 29, así que
    preguntar por «el cambio del día del turno» daría cero justo en el caso que
    importa. La jornada cuenta en el día en que empieza ---ver
    `apps.punches.workday`--- y ese día no es el del cambio.

    Positivo cuando el reloj se adelanta, que es cuando el turno dura **menos**
    de lo que dice el cuadrante. Negativo cuando se atrasa y dura más.

    `where` no es opcional y esa es la segunda cara de la trampa de arriba: los
    instantes salen de la base en UTC, y UTC no cambia de hora nunca. Comparar
    sus desfases da cero los 365 días del año. Hay que preguntárselo a la zona
    de quien vivió el turno, que es la que se movió.
    """
    aqui = getattr(where, "tzinfo", where)
    desde = start.astimezone(aqui).utcoffset()
    hasta = end.astimezone(aqui).utcoffset()
    if desde is None or hasta is None:
        return 0
    return round((hasta - desde).total_seconds() / 60)
