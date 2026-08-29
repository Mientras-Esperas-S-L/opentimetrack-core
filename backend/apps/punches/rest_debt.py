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

Las otras fuentes se enganchan aquí: cada una aporta sus horas debidas y su
plazo, y lo devuelto se anota igual, con el permiso de descanso compensatorio. La
segunda es el **festivo trabajado** (art. 37.2), y trae consigo la pregunta que
tienen todas las demás: **cuánto se debe**. El artículo hace los catorce días
retribuidos y no recuperables, y trabajar uno es lícito, pero no dice cómo se
compensa ---eso lo fija el convenio---. Así que la empresa lo declara, y mientras
no lo declare **no se lleva ningún saldo**: no habría de dónde sacar la cifra.

La tercera es la **distribución irregular** (art. 34.2), y es la única cuya
deuda ya estaba calculada entera: `irregular_balance` dice desde la vuelta 158
cuántas horas de un año vencido siguen sin compensar. Lo que faltaba era llevarlas
a la cuenta de lo que se debe en descanso, que es como se devuelven.

Quedan la nocturnidad (art. 36.2), la ampliación sectorial y el relevo de turno
(art. 19.a RD 1561/1995). Las dos primeras necesitan que la empresa declare
**cuánto** compensa, como el festivo; la del relevo tiene su cifra ---lo que le
falta al descanso para llegar a las doce horas--- pero hay que sacarla de un
recorrido del cuadrante que hoy vive dentro de la revisión.

**Lo debido se desglosa por origen; lo devuelto es uno solo.** Un descanso
disfrutado salda deuda, y no dice de cuál: repartirlo entre las fuentes exigiría
una regla de imputación que nadie ha acordado, y restarlo de cada una lo contaría
dos veces. Así que las fuentes dicen lo que generan ---y con qué artículo y qué
plazo, que es lo que hace falta para entenderlo--- y el saldo se calcula sobre el
total.
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


def _overtime_owed(*, employee, company, hoy: date) -> dict | None:
    """Horas extra pendientes de devolver en descanso, con su fecha límite.

    Devuelve `None` cuando no hay ni una hora extra marcada para compensar con
    descanso: sin deuda no hay nada que contar, y un saldo a cero de algo que
    nunca ha pasado ocupa sitio en la pantalla sin decir nada.

    La ventana es **móvil**: las horas hechas hace más de cuatro meses ya están
    fuera de plazo y no se suman a lo que queda por devolver ---se cuentan
    aparte, porque son las que hacen falta para avisar de que el plazo pasó---.
    """
    from apps.punches.models import HoursNature, OvertimeSettlement, Punch, PunchType
    from apps.tenants.rules import WorkingTimeRules

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

    #: El día en que vence lo más antiguo que sigue sin devolverse, que es la
    #: fecha que hace falta para no llegar tarde.
    mas_antigua = min((cuando for _, cuando in debidas if cuando >= desde), default=None)

    return {
        "source": "overtime",
        "owed_hours": round(en_plazo, 1),
        "overdue_hours": round(vencidas, 1),
        "due_on": (mas_antigua + timedelta(days=plazo)).isoformat() if mas_antigua else None,
        "days": plazo,
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


def _holiday_owed(*, employee, company, hoy: date) -> dict | None:
    """Descanso que se debe por festivos trabajados, cuando así lo compensa la empresa.

    El art. 37.2 hace los catorce días **retribuidos y no recuperables**, y
    trabajar uno es perfectamente lícito: lo que genera es una compensación. Lo
    que el artículo **no** dice es de qué tipo ni cuánta, y ahí manda el
    convenio. Por eso hay dos preguntas que contesta la empresa ---si compensa
    con descanso o con dinero, y cuántas horas de descanso por hora trabajada---
    y sin la primera no se lleva ningún saldo.

    **Se cuenta lo fichado, no lo planificado.** El cuadrante avisa desde que se
    asigna el turno ---y hace bien, es cuando alguien puede cambiarlo--- pero la
    compensación se debe por haber trabajado, no por haberlo previsto. Quien
    tenía turno un festivo y estuvo de baja no ha ganado ningún descanso.

    Sin plazo: el art. 37.2 no da ninguno, y el convenio que lo dé lo dirá en su
    ficha. Contar aquí un plazo inventado convertiría en «fuera de plazo» algo
    que no lo está.
    """
    from apps.punches.models import Punch, PunchInterval, PunchType
    from apps.tenants.holidays import holidays_by_workplace, holidays_for
    from apps.tenants.rules import WorkingTimeRules

    reglas = WorkingTimeRules.for_company(company)
    if reglas.holiday_worked_compensation != WorkingTimeRules.HOLIDAY_REST:
        return None

    # Un año hacia atrás: los catorce festivos caben, y más allá lo que quede sin
    # devolver ya es una conversación entre personas y no un saldo que leer.
    desde = hoy - timedelta(days=365)
    zone = company.tzinfo

    por_centro = holidays_by_workplace(desde, hoy)
    festivos = holidays_for(employee, desde, hoy, por_centro)
    if not festivos:
        return None

    eventos = Punch.objects.filter(
        employee=employee,
        is_active=True,
        timestamp__gte=datetime.combine(desde, dt_time.min, tzinfo=zone),
        timestamp__lt=datetime.combine(hoy + timedelta(days=1), dt_time.min, tzinfo=zone),
    ).order_by("timestamp")

    trabajadas = 0.0
    abiertos: dict[str, Punch] = {}
    for punch in eventos:
        if punch.punch_type == PunchType.IN:
            abiertos.setdefault(punch.interval, punch)
            continue
        opening = abiertos.pop(punch.interval, None)
        if opening is None or opening.interval != PunchInterval.WORK:
            continue
        # El día del que abre: una jornada que entra en el festivo a las 22:00 se
        # debe por el festivo, no por el día siguiente.
        cuando = opening.timestamp.astimezone(zone).date()
        if cuando in festivos:
            trabajadas += (punch.timestamp - opening.timestamp).total_seconds() / 3600

    if trabajadas <= RUIDO_HORAS:
        return None

    return {
        "source": "holiday",
        "owed_hours": round(trabajadas * float(reglas.holiday_rest_multiplier or 1), 1),
        "overdue_hours": 0,
        # Sin plazo: el art. 37.2 no da ninguno, y el convenio que lo dé lo dirá
        # en su ficha. Contar aquí uno inventado convertiría en «fuera de plazo»
        # algo que no lo está.
        "due_on": None,
        "days": 0,
        "multiplier": float(reglas.holiday_rest_multiplier or 1),
        "citation": "Art. 37.2 ET",
    }


def _descanso_disfrutado(employee, desde: date, hasta: date) -> tuple[float, int]:
    """Lo devuelto en descanso compensatorio, en horas, y los días sin convertir.

    Solo lo aprobado: pedir un descanso no es haberlo disfrutado, y contarlo como
    devuelto haría desaparecer la deuda con solo pedir el día.
    """
    from apps.absences.models import Absence, AbsenceStatus

    horas = 0.0
    sin_convertir = 0
    for ausencia in Absence.objects.filter(
        employee=employee,
        leave_type__code=DESCANSO_COMPENSATORIO,
        status=AbsenceStatus.APPROVED,
        start_date__gte=desde,
        start_date__lte=hasta,
    ):
        if ausencia.is_partial:
            horas += float(ausencia.hours or 0)
            continue
        # Un día entero de descanso devuelve **las horas que ese día tocaba
        # trabajar**, que salen del cuadrante. `Absence.hours` contesta cero para
        # los días completos, y hace bien: cuánto dura un día depende del turno,
        # del contrato y de la persona, y ese modelo no lo sabe.
        de_turno, dias_sin_turno = _horas_del_cuadrante(employee, ausencia)
        horas += de_turno
        sin_convertir += dias_sin_turno
    return horas, sin_convertir


def rest_debt(*, employee, company, day: date | None = None) -> dict | None:
    """Todo lo que se debe en descanso, de dónde viene y cuánto queda.

    Devuelve `None` cuando no hay ninguna fuente con deuda: un saldo a cero de
    algo que no ha pasado nunca ocupa sitio en la pantalla y no dice nada.

    **Lo devuelto se resta una sola vez, del total.** Un descanso disfrutado
    salda deuda y no dice de cuál: repartirlo entre las fuentes exigiría una
    regla de imputación que nadie ha acordado, y restarlo de cada una lo contaría
    dos veces. Las fuentes dicen lo que **generan**, con su artículo y su plazo;
    el saldo se calcula sobre la suma.
    """
    # `local_today` y no `date.today()`: esto último da la fecha UTC del
    # contenedor, y los plazos se cuentan en el calendario de la empresa. A la
    # 01:00 de Madrid en verano son dos días distintos.
    hoy = day or local_today(company)

    fuentes = [
        f
        for f in (
            _overtime_owed(employee=employee, company=company, hoy=hoy),
            _holiday_owed(employee=employee, company=company, hoy=hoy),
            _irregular_owed(employee=employee, company=company, hoy=hoy),
        )
        if f
    ]
    if not fuentes:
        return None

    debidas = sum(f["owed_hours"] for f in fuentes)
    vencidas = sum(f["overdue_hours"] for f in fuentes)

    # La ventana de lo devuelto, tan atrás como la fuente que más mire: un
    # descanso disfrutado en marzo salda igual una deuda de marzo que una de
    # mayo, y recortarlo al plazo más corto lo dejaría fuera de la cuenta.
    atras = max([f["days"] for f in fuentes] + [365])
    devuelto, sin_convertir = _descanso_disfrutado(employee, hoy - timedelta(days=atras), hoy)

    #: De todas las fuentes que tienen fecha, la que vence antes.
    vence = min((f["due_on"] for f in fuentes if f["due_on"]), default=None)

    return {
        "sources": fuentes,
        "owed_hours": round(debidas, 1),
        "settled_hours": round(devuelto, 1),
        "remaining_hours": round(max(0.0, debidas - devuelto), 1),
        "overdue_hours": round(vencidas, 1),
        "due_on": vence,
        "unconverted_days": sin_convertir,
    }


def _irregular_owed(*, employee, company, hoy: date) -> dict | None:
    """Horas trabajadas de más en un año ya vencido, que se devuelven en descanso.

    «Las diferencias derivadas de la distribución irregular de la jornada deberán
    quedar compensadas en el plazo de doce meses desde que se produzcan» (art.
    34.2), salvo que el convenio diga otro plazo.

    La cuenta la hace `irregular_balance` desde la vuelta 158, y contesta `None`
    en los casos en que no se puede hacer: jornada pactada por semana ---una
    cifra semanal no viene neta de vacaciones y restarla convertiría las de
    cualquiera en una deuda---, plazo apagado por la empresa, o alguien que entró
    a mitad del año que toca cuadrar.

    **Solo el exceso.** El saldo del art. 34.2 va en las dos direcciones y las dos
    hay que compensarlas, pero lo que se devuelve **con descanso** es haber
    trabajado de más. Haber trabajado de menos se compensa trabajando, y meterlo
    aquí en negativo restaría de lo que se debe por otras fuentes, que no tienen
    nada que ver.

    Y ya está fuera de plazo por definición: `irregular_balance` mira un año
    **vencido**, así que estas horas van directas a lo vencido y no a lo
    pendiente. Es el único caso en que una fuente nace tarde.
    """
    from apps.punches.irregular import irregular_balance

    saldo = irregular_balance(employee=employee, company=company, day=hoy)
    if not saldo or saldo["settled"]:
        return None

    horas = saldo["balance_hours"]
    if horas <= RUIDO_HORAS:
        return None

    return {
        "source": "irregular",
        "owed_hours": round(horas, 1),
        "overdue_hours": round(horas, 1),
        "due_on": None,
        "days": 0,
        "year": saldo["year"],
        "citation": "Art. 34.2 ET",
    }
