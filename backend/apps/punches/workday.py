"""A qué día pertenece cada fichaje. La jornada, no el día natural.

Un turno de noche entra el martes a las 22:00 y sale el miércoles a las 06:00.
Contando por día natural eso son dos trozos: dos horas el martes y seis el
miércoles. Ninguno de los dos dice nada útil, y juntos dicen algo falso ---que
esa persona trabajó dos días---.

**La jornada entera cuenta en el día en que empieza.** Esas ocho horas son del
martes; el miércoles, a efectos de jornada, no trabajó. Es lo que se hace, y no
por convención: casi todo lo que mide el Estatuto se mide por jornada y no por
día natural. Las nueve horas ordinarias como máximo (art. 34.3) son de la
jornada; partirlas por la medianoche da dos cifras que no significan nada. Las
doce horas de descanso entre jornadas (art. 34.3) van del final de una al
principio de la siguiente, y sin la jornada como unidad no hay de dónde a dónde
medir. El día y medio de descanso semanal (art. 37.1), igual.

Lo que **no** sigue esta regla, y conviene no mezclar: el plus de nocturnidad.
Las horas nocturnas son las que caen entre las 22:00 y las 06:00 (art. 36.1) y
se cuentan donde caigan, cruzando la medianoche sin problema. Son dos lecturas
distintas de los mismos fichajes:

- la **jornada** ---su total, sus extras, sus descansos--- al día en que arranca
- las **horas nocturnas** ---el complemento--- cada una en su franja real

Queda un caso que decide el convenio y no este módulo: un turno que entra el
sábado a las 22:00 y sale el domingo a las 06:00, ¿son horas de domingo para el
plus de festivo? Hay convenios de las dos formas. Como los instantes reales se
guardan enteros, las dos lecturas siguen siendo derivables; lo que este módulo
fija es a qué día se atribuye la jornada, que es otra pregunta.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.common.clock import local_date_of
from apps.punches.models import Punch, PunchInterval, PunchType


def _abandonada(apertura, ahora, tope_horas: int) -> bool:
    """Si una jornada abierta lleva tanto tiempo así que ya no puede ser la misma.

    Sin esto, quien se olvidó de fichar la salida el lunes vería su entrada del
    martes leída como parte del lunes, y a partir de ahí todo corrido. El tope
    es el mismo que usa la deducción de entrada o salida, y por la misma razón.
    """
    return (ahora - apertura).total_seconds() > tope_horas * 3600


def assign_workdays(punches, where, *, max_open_hours: int) -> dict[int, date]:
    """De cada fichaje, el día de la jornada a la que pertenece.

    `punches` tiene que venir **ordenado por instante** y traer contexto por los
    dos lados: la jornada de ayer puede meterse en hoy, y la de hoy en mañana.
    Quien llame se encarga de pedir la ventana ancha; `punches_of_the_workday`
    lo hace.

    Un fichaje que no pertenece a ninguna jornada abierta ---una salida suelta,
    una pausa sin entrada--- se atribuye a su propio día local. Es un registro
    incompleto y el sitio donde menos daño hace es donde de verdad ocurrió.
    """
    de_quien: dict[int, date] = {}
    dia_abierto: date | None = None
    abierta_en = None

    for punch in punches:
        propio = local_date_of(punch.timestamp, where)

        if dia_abierto is not None and _abandonada(abierta_en, punch.timestamp, max_open_hours):
            # La anterior se quedó sin cerrar. Se abandona aquí en vez de
            # arrastrarla, que es lo que convertiría un olvido en días corridos.
            dia_abierto = None
            abierta_en = None

        if punch.interval == PunchInterval.WORK and punch.punch_type == PunchType.IN:
            if dia_abierto is None:
                dia_abierto = propio
                abierta_en = punch.timestamp
            de_quien[punch.id] = dia_abierto
            continue

        if punch.interval == PunchInterval.WORK and punch.punch_type == PunchType.OUT:
            de_quien[punch.id] = dia_abierto if dia_abierto is not None else propio
            dia_abierto = None
            abierta_en = None
            continue

        # Pausas, esperas y desconexiones: van con la jornada que las contiene.
        # Una pausa a las 03:00 de un turno de noche es del martes, como el
        # turno; contarla en el miércoles la sacaría de la jornada a la que
        # descuenta.
        de_quien[punch.id] = dia_abierto if dia_abierto is not None else propio

    return de_quien


def current_workday(employee, *, max_open_hours: int) -> date:
    """De qué día es la jornada de ahora mismo.

    La del último fichaje de jornada mientras siga dentro del tope, y si no hay
    ninguno, la de hoy. No es lo mismo que «hoy», y ahí estaba el fallo: a las
    tres de la mañana, quien entró ayer a las 22:00 tiene abierta la jornada de
    **ayer**, y preguntando por «hoy» su pantalla decía «sin empezar» mientras
    estaba trabajando.

    Del último fichaje y no de la última entrada, porque justo después de fichar
    la salida de un turno de noche la jornada que acaba de cerrarse sigue siendo
    la que interesa: a las 06:00 lo que hay que enseñar es «has terminado, ocho
    horas», no «sin empezar».

    El tope hace de caducidad, que es para lo que la empresa lo pone: pasado ese
    rato la jornada anterior deja de ser la de ahora y se vuelve a mirar hoy.
    """
    from apps.common.clock import local_today

    margen = timedelta(hours=max_open_hours)
    ahora = timezone.now()

    # El doble de ancha que el tope: para saber de qué jornada es el último
    # fichaje hace falta ver la entrada que la abrió, y esa puede estar un tope
    # entero por detrás de él.
    eventos = list(
        Punch.objects.filter(
            employee=employee,
            is_active=True,
            timestamp__gte=ahora - margen * 2,
        ).order_by("timestamp")
    )
    de_jornada = [
        p for p in eventos if p.interval == PunchInterval.WORK and ahora - p.timestamp <= margen
    ]
    if not de_jornada:
        return local_today(employee)

    de_quien = assign_workdays(eventos, employee, max_open_hours=max_open_hours)
    return de_quien.get(de_jornada[-1].id) or local_today(employee)


def punches_of_the_workday(employee, day: date, *, max_open_hours: int):
    """Los fichajes de las jornadas que **empezaron** ese día.

    Pide una ventana más ancha que el día ---un margen de `max_open_hours` por
    cada lado--- porque una jornada que empieza el día pedido puede terminar al
    siguiente, y una que empezó el anterior puede terminar dentro. Después se
    queda solo con lo que la atribución asigna al día pedido.

    La zona es la de la persona, que es la de su centro de trabajo y cae a la de
    la empresa cuando no tiene: una oficina en Madrid y otra en Las Palmas van
    una hora aparte, y una hora es la diferencia entre que un fichaje caiga el
    lunes o el domingo.
    """
    margen = timedelta(hours=max_open_hours)
    inicio = datetime.combine(day, time.min, tzinfo=employee.tzinfo)
    ventana = (
        Punch.objects.filter(
            employee=employee,
            is_active=True,
            timestamp__gte=inicio - margen,
            timestamp__lt=inicio + timedelta(days=1) + margen,
        )
        .order_by("timestamp")
        .select_related("employee")
    )

    eventos = list(ventana)
    de_quien = assign_workdays(eventos, employee, max_open_hours=max_open_hours)
    return [p for p in eventos if de_quien.get(p.id) == day]
