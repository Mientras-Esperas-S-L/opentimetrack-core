"""En qué centro de trabajo estaba cada persona, y desde cuándo.

La persona lleva su centro **actual** en una columna, y para casi todo eso es lo
correcto: dónde ficha hoy, qué pantalla ve, a qué inspección respondería ahora. Este
módulo mantiene al lado el historial, que hace falta para lo que se lee **de un
periodo pasado**: los dos festivos locales de cada día, la zona en la que se lee la
jornada de cada día, y el informe del art. 34.9 pedido por centro.

La diferencia con `adscription.py` ---el mismo patrón para el departamento--- es que
aquí la pregunta es **por día** y no solo por periodo: en el mes de un traslado los
primeros días llevan los festivos de un centro y el resto los del otro, y un informe
que resolviera el mes entero con un solo centro se equivocaría en la mitad.

**El historial empieza el día que se estrena.** Del pasado no hay dato, y ponerle a
cada asignación una fecha inventada sería afirmar algo que no consta; por eso la
asignación de arranque va sin fecha de inicio, que significa «no consta desde cuándo»
y cuenta para cualquier periodo. Es exactamente como se comportaba el producto antes.
"""

from __future__ import annotations

from datetime import date, timedelta


def remember_workplace(employee, *, on: date | None = None) -> None:
    """Anota el centro que tiene ahora, cerrando el anterior si cambió.

    Idempotente: llamarlo dos veces con el mismo centro no crea una asignación nueva ni
    mueve fechas. Importa porque se llama desde el guardado de la ficha, que ocurre
    muchas veces sin tocar el centro.

    `on` es el día en que el cambio ocurrió, y no siempre es hoy: una aplicación de
    gestión que empuje un traslado sabe desde cuándo es, y anotarlo con la fecha de hoy
    dejaría unos días leyéndose con el centro equivocado.
    """
    from apps.users.models import WorkplaceAssignment

    # Sin empresa no hay adscripción que anotar: el superusuario de plataforma no
    # pertenece a ninguna, y preguntarle su zona horaria revienta.
    if employee.tenant_id is None:
        return

    vigente = (
        WorkplaceAssignment.objects.filter(employee=employee, ends_on__isnull=True)
        .order_by("-starts_on")
        .first()
    )
    if vigente and vigente.workplace_id == employee.workplace_id:
        return

    from apps.common.clock import local_today

    cuando = on or local_today(employee)
    if vigente:
        # Se cierra **el día anterior**: la asignación nueva empieza ese día, y dos
        # vigentes el mismo día harían que una persona tuviera dos juegos de festivos.
        vigente.ends_on = cuando - timedelta(days=1)
        vigente.save(update_fields=["ends_on"])

    if employee.workplace_id:
        WorkplaceAssignment.objects.create(
            tenant=employee.tenant,
            employee=employee,
            workplace_id=employee.workplace_id,
            # Sin fecha solo la primera, cuando no había historial: a partir de ahí
            # cada cambio sabe cuándo ocurrió.
            starts_on=cuando if vigente else None,
        )


def workplace_on(employee, day: date):
    """El centro en el que estaba **ese día**, o el actual si no consta otro.

    Cae en el centro de hoy para quien no tenga historial, que es lo que había antes de
    este módulo: para esas personas la respuesta es la misma que daba el producto y
    nadie pierde festivos por haberse estrenado el historial ayer.
    """
    from apps.users.models import WorkplaceAssignment

    tramos = list(WorkplaceAssignment.objects.filter(employee=employee))
    if not tramos:
        return employee.workplace

    for tramo in sorted(tramos, key=lambda t: t.starts_on or date.min, reverse=True):
        if tramo.covers_day(day):
            return tramo.workplace
    # Un día anterior a todo lo que consta: el más antiguo es la mejor respuesta que
    # hay, y desde luego mejor que ninguna.
    return min(tramos, key=lambda t: t.starts_on or date.min).workplace


def workplaces_over(employee, first: date, last: date) -> dict:
    """`{día: centro}` para el tramo, resuelto de una vez.

    Preguntar día a día sería una consulta por día y por persona: un mes de una
    plantilla de cien son tres mil. El historial de alguien cabe en una consulta y se
    reparte aquí.
    """
    from apps.users.models import WorkplaceAssignment

    tramos = list(WorkplaceAssignment.objects.filter(employee=employee))
    return _repartir(tramos, first, last) if tramos else {}


def workplaces_by_person(people, first: date, last: date) -> dict:
    """`{persona: {día: centro}}` para toda esa gente, en **una** consulta.

    Lo mismo que `holidays_by_workplace` hace con los festivos y por el mismo motivo:
    `workplaces_over` por cabeza es una consulta por persona, y la revisión del
    cuadrante la llamaba dentro de su bucle ---nueve consultas más al pasar de tres
    personas a doce---. La guarda de `test_no_crece_con_la_plantilla` lo vio.

    Las personas sin historial no salen en el resultado: quien lo lee cae entonces en
    su centro de hoy, que es la respuesta correcta para ellas.
    """
    from apps.users.models import WorkplaceAssignment

    por_persona: dict = {}
    for tramo in WorkplaceAssignment.objects.filter(employee__in=people).select_related(
        "workplace"
    ):
        por_persona.setdefault(tramo.employee_id, []).append(tramo)

    resultado = {}
    for persona_id, tramos in por_persona.items():
        resultado[persona_id] = _repartir(tramos, first, last)
    return resultado


def _repartir(tramos, first: date, last: date) -> dict:
    """De una lista de tramos al `{día: centro}` del periodo."""
    ordenados = sorted(tramos, key=lambda t: t.starts_on or date.min, reverse=True)
    mas_antiguo = ordenados[-1]
    por_dia = {}
    dia = first
    while dia <= last:
        elegido = next((t for t in ordenados if t.covers_day(dia)), mas_antiguo)
        por_dia[dia] = elegido.workplace
        dia += timedelta(days=1)
    return por_dia


def people_in_workplace(people, workplace_id, first: date, last: date):
    """De esa lista, quienes estuvieron en ese centro durante el periodo.

    Cae en el centro actual para quien no tenga historial, por lo mismo que en la
    adscripción de departamento: un informe al que le falta una persona no cumple el
    art. 34.9, y uno que trae a alguien de más se ve a simple vista.
    """
    from apps.users.models import WorkplaceAssignment

    con_historia = set(
        WorkplaceAssignment.objects.filter(employee__in=people).values_list(
            "employee_id", flat=True
        )
    )

    tramos: dict = {}
    for tramo in WorkplaceAssignment.objects.filter(employee__in=people, workplace_id=workplace_id):
        tramos.setdefault(tramo.employee_id, []).append(tramo)

    return [
        quien
        for quien in people
        if (
            any(t.covers(first, last) for t in tramos.get(quien.id, []))
            if quien.id in con_historia
            else str(quien.workplace_id) == str(workplace_id)
        )
    ]
