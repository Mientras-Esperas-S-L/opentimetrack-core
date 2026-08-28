"""El saldo de la distribución irregular de la jornada (art. 34.2 ET).

Una empresa puede repartir la jornada de forma desigual: semanas de más y
semanas de menos. Lo que la ley no permite es que la cuenta no se cierre.

    «La compensación de las diferencias, por exceso o por defecto, entre la
    jornada realizada y la duración máxima de la jornada ordinaria de trabajo
    legal o pactada será exigible según lo acordado en convenio colectivo o, a
    falta de previsión al respecto, por acuerdo entre la empresa y los
    representantes de los trabajadores. **En defecto de pacto, las diferencias
    derivadas de la distribución irregular de la jornada deberán quedar
    compensadas en el plazo de doce meses desde que se produzcan.**»

**Esto no es el 10 % del párrafo primero.** Aquel es un margen ---cuánta jornada
se puede mover--- y para medirlo haría falta la distribución *ordinaria* contra
la que comparar, que no existe en el modelo porque el cuadrante **es** la
distribución. Sigue sin calcularse, y sigue siendo una decisión.

**Solo con jornada pactada por año, y esa es la parte que hay que entender.**

Una cifra anual ---«1.700 horas al año», que es como lo escriben muchos
convenios--- ya viene **neta**: es lo que se trabaja, con las vacaciones y los
festivos ya descontados. Compararla con lo trabajado en el año es una resta
honesta.

Una cifra semanal no. Cuarenta horas por cincuenta y dos semanas son 2.080, y
nadie trabaja 2.080 horas: hay vacaciones, festivos y bajas de por medio. Para
saber cuánta jornada correspondía a cada semana concreta haría falta descontar
todo eso, y ahí se vuelve al problema de siempre ---la referencia sale del
cuadrante, y el cuadrante es lo que se quiere medir---. Así que con jornada
semanal **no se contesta**, en vez de contestar una resta que suma vacaciones
como si fueran horas debidas.

**El plazo lo declara la empresa.** El art. 34.2 pone los doce meses solo «en
defecto de pacto», así que decirle a una empresa con convenio propio que lleva
horas sin compensar sería inventar. Vive en `WorkingTimeRules.
irregular_settlement_months`, y un cero apaga la cuenta.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as dt_time

from django.utils import timezone

from apps.users.models import HoursPeriod

#: Por debajo de esto, el saldo es ruido y no una deuda: media hora en un año de
#: fichajes no es una diferencia que nadie tenga que devolver.
RUIDO_HORAS = 0.5


def _horas_trabajadas(employee, company, first: date, last: date) -> float:
    """Tiempo de trabajo efectivo entre dos días, los dos incluidos."""
    from apps.punches.models import Punch, PunchInterval, PunchType

    zone = company.tzinfo
    punches = Punch.objects.filter(
        employee=employee,
        timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        timestamp__lt=datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=zone),
        is_active=True,
    ).order_by("timestamp")

    # Igual que en el tope de complementarias: un tramo sin cerrar se deja fuera
    # en vez de adivinarle un final, y una pausa que no es tiempo de trabajo
    # (art. 3.d) no suma.
    trabajado = timedelta()
    opening = None
    for punch in punches:
        if punch.punch_type == PunchType.IN:
            opening = punch
        elif opening is not None:
            if opening.interval == PunchInterval.WORK:
                trabajado += punch.timestamp - opening.timestamp
            opening = None
    return trabajado.total_seconds() / 3600


def irregular_balance(*, employee, company, day: date | None = None) -> dict | None:
    """El saldo del año ya vencido, el que tendría que estar compensado.

    Se mira el **año natural completo** anterior al plazo: si el plazo son doce
    meses y hoy es agosto de 2026, el año 2024 tendría que estar cuadrado desde
    hace rato y 2025 está todavía en plazo hasta que pasen sus doce meses.

    Devuelve `None` cuando la pregunta no aplica, que no es lo mismo que cero:

    - **La empresa apagó la cuenta** poniendo el plazo a cero.
    - **La jornada no se pactó por año**, y entonces no hay una cifra neta con la
      que restar. Ver el porqué en la cabecera del módulo.
    - **El año que tocaría mirar es anterior al contrato**, así que no hay nada
      que cuadrar.
    """
    from apps.tenants.rules import WorkingTimeRules

    rules = WorkingTimeRules.for_company(company)
    meses = rules.irregular_settlement_months
    if not meses:
        return None

    agreed = employee.agreed_hours(rules)
    if agreed is None or agreed[1] != HoursPeriod.YEAR:
        return None
    pactadas = float(agreed[0])

    day = day or timezone.localdate()
    ano = _ultimo_ano_vencido(day, meses)
    primero, ultimo = date(ano, 1, 1), date(ano, 12, 31)

    if employee.contract_start and employee.contract_start > primero:
        # Un año a medias no se puede comparar con una cifra anual entera, y
        # prorratearla sería inventar la parte que le tocaba.
        return None

    trabajado = _horas_trabajadas(employee, company, primero, ultimo)
    saldo = trabajado - pactadas

    return {
        "year": ano,
        "months": meses,
        "worked_hours": round(trabajado, 1),
        "agreed_hours": round(pactadas, 1),
        "balance_hours": round(saldo, 1),
        "settled": abs(saldo) < RUIDO_HORAS,
    }


def _vence(ano: int, meses: int) -> date:
    """Cuándo se acaba el plazo de compensar las diferencias de ese año.

    Se cuenta desde el 31 de diciembre porque las diferencias se producen a lo
    largo del año y esa es la última fecha en que pudo producirse alguna: contar
    desde enero le quitaría once meses de plazo a quien tuvo el desfase en
    noviembre.
    """
    total = 11 + meses  # diciembre es el mes 12, o sea el índice 11
    year, mes = ano + total // 12, total % 12 + 1
    dia = 31
    while dia > 28:
        try:
            return date(year, mes, dia)
        except ValueError:
            dia -= 1
    return date(year, mes, dia)


def _ultimo_ano_vencido(day: date, meses: int) -> int:
    """El año más reciente cuyo plazo ya pasó.

    Se busca hacia atrás en vez de restar uno: **con plazos largos hay que
    retroceder más de un año**. Con veinticuatro meses, en agosto de 2026, ni
    2025 ni 2024 han vencido ---el de 2024 lo hace el 31 de diciembre de 2026---
    y el año que toca cuadrar es 2023. Restar uno fijo habría hablado del año
    equivocado, y lo dijo la prueba del convenio con plazo doble.
    """
    ano = day.year - 1
    while _vence(ano, meses) >= day:
        ano -= 1
    return ano
