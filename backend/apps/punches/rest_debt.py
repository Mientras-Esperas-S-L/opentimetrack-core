"""Lo que se debe en descanso, y hasta cuándo hay para devolverlo.

**El patrón que más se repetía en lo que quedaba del inventario:** el producto
sabía decir «esto se aparta de la regla» y no sabía decir «y quedan cuatro horas
por devolver antes del 9 de septiembre». Lo segundo es lo que una empresa
necesita para cumplir; lo primero solo sirve para saber que no cumple.

Empieza por las **horas extraordinarias compensadas con descanso** (art. 35.1),
que es la fuente con el plazo más claro ---«dentro de los cuatro meses siguientes
a su realización», en defecto de pacto en convenio--- y la única cuya deuda ya
estaba anotada: cada hora extra dice desde el primer día **cómo se salda**, con
dinero o con descanso, porque el art. 3.f del real decreto de registro obliga a
decirlo. Lo que faltaba era el otro lado de la cuenta.

**Por qué se deriva en vez de guardarse.** Un libro de deudas con sus apuntes
sería otro sitio donde la misma verdad puede quedarse vieja: la deuda ya está en
los fichajes y lo devuelto está en las ausencias. Sumarlas cuando alguien
pregunta no puede desincronizarse de aquello que cuenta.

Las otras cinco fuentes ---distribución irregular, nocturnidad, festivo
trabajado, ampliación sectorial y relevo de turno--- se enganchan aquí: cada una
aporta sus horas debidas y su plazo, y lo devuelto se anota igual, con el permiso
de descanso compensatorio. Esta vuelta trae solo la primera, y es a propósito:
las demás necesitan decidir antes **cuánto** se debe en cada caso, que es una
pregunta distinta en cada artículo.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as dt_time

from apps.common.clock import local_today

#: Los cuatro meses del art. 35.1 ET, en días. En defecto de pacto: el convenio
#: puede dar otro plazo, y por eso la empresa lo puede cambiar.
PLAZO_ART_35_1 = 120

#: El permiso con el que se anota lo devuelto. Uno solo para todas las fuentes:
#: quien descansa está descansando, y de qué deuda venía es cosa de la cuenta.
DESCANSO_COMPENSATORIO = "es.compensatory_rest"

#: Menos de esto no se persigue. Un desajuste de minutos al cerrar una jornada no
#: es una deuda de descanso, y avisar de seis minutos es la forma más rápida de
#: que nadie vuelva a leer un aviso.
RUIDO_HORAS = 0.5


def _horas_de(tramos) -> float:
    return sum(t for t in tramos if t > 0)


def overtime_rest_debt(*, employee, company, day: date | None = None) -> dict | None:
    """Horas extra pendientes de devolver en descanso, con su fecha límite.

    Devuelve `None` cuando no hay ni una hora extra marcada para compensar con
    descanso: sin deuda no hay nada que contar, y un saldo a cero de algo que
    nunca ha pasado ocupa sitio en la pantalla sin decir nada.

    La ventana es **móvil**: las horas hechas hace más de cuatro meses ya están
    fuera de plazo y no se suman a lo que queda por devolver ---se cuentan
    aparte, porque son las que hacen falta para avisar de que el plazo pasó---.
    """
    from apps.absences.models import Absence, AbsenceStatus
    from apps.punches.models import HoursNature, OvertimeSettlement, Punch, PunchType
    from apps.tenants.rules import WorkingTimeRules

    # `local_today` y no `date.today()`: esto último da la fecha UTC del
    # contenedor, y el plazo de cuatro meses se cuenta en el calendario de la
    # empresa. A las 01:00 de Madrid en verano son dos días distintos.
    hoy = day or local_today(company)
    reglas = WorkingTimeRules.for_company(company)
    plazo = int(reglas.overtime_rest_days or 0)
    if not plazo:
        # Un cero apaga la cuenta, como en el resto de los plazos de empresa: hay
        # convenios que remiten a un cómputo distinto, y forzar los cuatro meses
        # del real decreto sobre uno que dice otra cosa sería decir algo falso
        # con aire de dato.
        return None
    zone = company.tzinfo

    desde = hoy - timedelta(days=plazo)

    eventos = Punch.objects.filter(
        employee=employee,
        is_active=True,
        timestamp__lt=datetime.combine(hoy + timedelta(days=1), dt_time.min, tzinfo=zone),
    ).order_by("timestamp")

    #: (horas, día en que se hicieron) de cada tramo extra que se salda con
    #: descanso. El día sale de la **apertura**: una jornada que cruza la
    #: medianoche se debe desde que empezó.
    debidas: list[tuple[float, date]] = []
    abiertos: dict[str, Punch] = {}
    for punch in eventos:
        if punch.punch_type == PunchType.IN:
            abiertos.setdefault(punch.interval, punch)
            continue
        opening = abiertos.pop(punch.interval, None)
        if opening is None:
            continue
        if opening.hours_nature != HoursNature.OVERTIME:
            continue
        if opening.overtime_settlement != OvertimeSettlement.REST:
            continue
        horas = (punch.timestamp - opening.timestamp).total_seconds() / 3600
        debidas.append((horas, opening.timestamp.astimezone(zone).date()))

    if not debidas:
        return None

    en_plazo = _horas_de([h for h, cuando in debidas if cuando >= desde])
    vencidas = _horas_de([h for h, cuando in debidas if cuando < desde])

    # Lo devuelto: las ausencias de descanso compensatorio, contadas en horas.
    # Solo las aprobadas: una pendiente todavía no ha devuelto nada.
    devuelto = 0.0
    sin_convertir = 0
    for ausencia in Absence.objects.filter(
        employee=employee,
        leave_type__code=DESCANSO_COMPENSATORIO,
        status=AbsenceStatus.APPROVED,
        start_date__gte=desde,
        start_date__lte=hoy,
    ):
        if ausencia.is_partial:
            devuelto += float(ausencia.hours or 0)
            continue
        # Un día entero de descanso devuelve **las horas que ese día tocaba
        # trabajar**, que salen del cuadrante. `Absence.hours` contesta cero para
        # los días completos, y hace bien: cuánto dura un día depende del turno,
        # del contrato y de la persona, y ese modelo no lo sabe.
        horas, dias_sin_turno = _horas_del_cuadrante(employee, ausencia)
        devuelto += horas
        sin_convertir += dias_sin_turno

    quedan = max(0.0, en_plazo - devuelto)
    #: El día en que vence lo más antiguo que sigue sin devolverse, que es la
    #: fecha que hace falta para no llegar tarde.
    mas_antigua = min((cuando for _, cuando in debidas if cuando >= desde), default=None)

    return {
        "owed_hours": round(en_plazo, 1),
        "settled_hours": round(devuelto, 1),
        "remaining_hours": round(quedan, 1),
        "overdue_hours": round(vencidas, 1),
        "due_on": (mas_antigua + timedelta(days=plazo)).isoformat() if mas_antigua else None,
        "days": plazo,
        #: Días de descanso compensatorio que **no se han podido convertir** a
        #: horas por no haber turno previsto. Se dicen en vez de estimarlos: una
        #: jornada inventada haría que el saldo pareciera saldado sin estarlo.
        "unconverted_days": sin_convertir,
        "citation": "Art. 35.1 ET",
    }


def _horas_del_cuadrante(employee, ausencia) -> tuple[float, int]:
    """Las horas que tocaba trabajar en los días que ocupa esa ausencia.

    Devuelve `(horas, días sin turno)`. Los segundos no se estiman: sin turno
    previsto no hay de dónde sacar cuánto dura ese día, y ponerle una jornada
    tipo haría que un saldo pareciera devuelto sin estarlo.
    """
    from apps.shifts.models import Shift

    # `Shift.minutes` ya suma los tramos del turno, partidos incluidos. Repetir
    # esa suma aquí habría duplicado la única pieza que sabe leer un cuadrante.
    turnos = {
        turno.day: turno.minutes
        for turno in Shift.objects.filter(
            employee=employee,
            day__gte=ausencia.start_date,
            day__lte=ausencia.end_date,
        )
    }

    horas = 0.0
    sin_turno = 0
    dia = ausencia.start_date
    while dia <= ausencia.end_date:
        minutos = turnos.get(dia)
        if minutos:
            horas += minutos / 60
        else:
            sin_turno += 1
        dia += timedelta(days=1)
    return horas, sin_turno
