"""Cuánto se trabaja a distancia, y cuándo eso hace aplicable la Ley 10/2021.

El art. 1 de la Ley 10/2021 no regula «el teletrabajo» en general: fija **cuándo
se aplica**. Se aplica al trabajo a distancia que se preste, «en un periodo de
referencia de tres meses, un mínimo del treinta por ciento de la jornada».

Por debajo de ese umbral se puede trabajar desde casa y la ley no entra. Por
encima, entra entera: hace falta **acuerdo por escrito y previo** (art. 5), con
el contenido mínimo del art. 7 --- inventario de medios, gastos, horario, centro
de trabajo al que queda adscrita la persona, medios de control ---.

Eso convierte una pregunta jurídica en una cuenta, que es lo que este producto
puede hacer: sumar el tiempo marcado a distancia, dividirlo por el trabajado, y
decir si se ha pasado del umbral.

**La ventana es móvil, y aquí sí.** En el tope de horas complementarias se
razonó lo contrario --- ventanas naturales, porque un tope que cambia cada
mañana no se puede comprobar en un calendario --- y son cosas distintas: aquel
es un límite que no se puede rebasar, y este es un umbral que dice si una ley
aplica hoy. La ley habla de «un periodo de referencia de tres meses» sin atarlo
al calendario, y lo que interesa saber es si **ahora mismo** hace falta acuerdo.

**Sobre el tiempo trabajado, no sobre los días.** Media jornada en casa y media
en la oficina son eso, media y media: contar días enteros redondearía a favor o
en contra según la costumbre de cada quien, y el registro tiene la hora exacta.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as dt_time

from django.utils import timezone

#: Art. 1 de la Ley 10/2021.
UMBRAL = 30.0
MESES_DE_REFERENCIA = 3


def _tres_meses_antes(day: date) -> date:
    """El mismo día, tres meses atrás, sin inventarse fechas que no existen.

    El 31 de mayo menos tres meses no es el 31 de febrero. Se retrocede al
    último día del mes que toque, que es lo que hace cualquiera con un
    calendario delante.
    """
    mes = day.month - MESES_DE_REFERENCIA
    year = day.year
    if mes <= 0:
        mes += 12
        year -= 1
    dia = day.day
    while dia > 28:
        try:
            return date(year, mes, dia)
        except ValueError:
            dia -= 1
    return date(year, mes, dia)


def remote_share(*, employee, company, day: date | None = None) -> dict | None:
    """Qué parte de la jornada se ha trabajado a distancia en los últimos tres meses.

    Devuelve `None` cuando no hay nada trabajado en la ventana: cero de cero no
    es «el 0 % a distancia», es que no hay con qué responder, y un 0 % dicho
    sobre una ventana vacía se lee como un hecho.
    """
    from apps.punches.models import Punch, PunchInterval, PunchType, WorkMode

    day = day or timezone.localdate()
    first = _tres_meses_antes(day)

    zone = company.tzinfo
    punches = Punch.objects.filter(
        employee=employee,
        timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        timestamp__lt=datetime.combine(day + timedelta(days=1), dt_time.min, tzinfo=zone),
        is_active=True,
    ).order_by("timestamp")

    # Igual que en el tope de complementarias: un tramo sin cerrar se deja
    # fuera en vez de adivinarle un final, y una pausa que no es tiempo de
    # trabajo (art. 3.d) no suma por ningún lado --- ni al total ni a la parte
    # a distancia ---, que si no el porcentaje saldría de una jornada que
    # incluye el desayuno.
    trabajado = timedelta()
    a_distancia = timedelta()
    opening = None
    for punch in punches:
        if punch.punch_type == PunchType.IN:
            opening = punch
        elif opening is not None:
            if opening.interval == PunchInterval.WORK:
                cuanto = punch.timestamp - opening.timestamp
                trabajado += cuanto
                if opening.work_mode == WorkMode.REMOTE:
                    a_distancia += cuanto
            opening = None

    if not trabajado:
        return None

    share = a_distancia.total_seconds() / trabajado.total_seconds() * 100
    return {
        "first": first,
        "last": day,
        "worked_hours": round(trabajado.total_seconds() / 3600, 1),
        "remote_hours": round(a_distancia.total_seconds() / 3600, 1),
        "share": round(share, 1),
        "threshold": UMBRAL,
        "law_applies": share >= UMBRAL,
    }
