"""Quién estaba en qué departamento, y desde cuándo.

La persona lleva su departamento **actual** en una columna. Este módulo mantiene
al lado el historial, que solo hace falta para una cosa: los documentos **de un
periodo**. El informe del art. 34.9 se puede pedir por departamento, y ese filtro
leía la adscripción de hoy ---pedir «julio, Jardinería» después de una
reorganización de septiembre devolvía la plantilla de septiembre---.

**El historial empieza el día que se estrena.** Del pasado no hay dato, y
ponerle a cada asignación una fecha inventada sería afirmar algo que no consta;
por eso la asignación de arranque va **sin** fecha de inicio, que significa «no
consta desde cuándo» y cuenta para cualquier periodo. Es exactamente como se
comportaba el producto antes.
"""

from __future__ import annotations

from datetime import date, timedelta


def remember_department(employee, *, on: date | None = None) -> None:
    """Anota el departamento que tiene ahora, cerrando el anterior si cambió.

    Idempotente: llamarlo dos veces con el mismo departamento no crea una
    asignación nueva ni mueve fechas. Eso importa porque se llama desde el
    guardado de la ficha, que se hace muchas veces sin tocar el departamento.
    """
    from apps.users.models import DepartmentAssignment

    # Sin empresa no hay adscripción que anotar: el superusuario de plataforma
    # no pertenece a ninguna, y preguntarle su zona horaria revienta.
    if employee.tenant_id is None:
        return

    vigente = (
        DepartmentAssignment.objects.filter(employee=employee, ends_on__isnull=True)
        .order_by("-starts_on")
        .first()
    )
    if vigente and vigente.department_id == employee.department_id:
        return

    from apps.common.clock import local_today

    cuando = on or local_today(employee)
    if vigente:
        # Se cierra **el día anterior**: la asignación nueva empieza hoy, y dos
        # asignaciones vigentes el mismo día harían que una persona apareciera en
        # dos departamentos en el informe de ese día.
        vigente.ends_on = cuando - timedelta(days=1)
        vigente.save(update_fields=["ends_on"])

    if employee.department_id:
        DepartmentAssignment.objects.create(
            tenant=employee.tenant,
            employee=employee,
            department_id=employee.department_id,
            # Sin fecha solo la primera, cuando no había historial: a partir de
            # ahí cada cambio sabe cuándo ocurrió.
            starts_on=cuando if vigente else None,
        )


def people_in_department(people, department_id, first: date, last: date):
    """De esa lista, quienes estuvieron en ese departamento durante el periodo.

    Cae en la adscripción actual para quien no tenga historial: eso es lo que
    había antes de este módulo y es mejor que dejar fuera a alguien que sí
    trabajó ahí. Un informe al que le falta una persona es un informe que no
    cumple el art. 34.9, y uno que trae a alguien de más se ve a simple vista.
    """
    from apps.users.models import DepartmentAssignment

    con_historia = set(
        DepartmentAssignment.objects.filter(employee__in=people).values_list(
            "employee_id", flat=True
        )
    )

    tramos: dict = {}
    for tramo in DepartmentAssignment.objects.filter(
        employee__in=people, department_id=department_id
    ):
        tramos.setdefault(tramo.employee_id, []).append(tramo)

    return [
        quien
        for quien in people
        if (
            any(t.covers(first, last) for t in tramos.get(quien.id, []))
            if quien.id in con_historia
            else str(quien.department_id) == str(department_id)
        )
    ]
