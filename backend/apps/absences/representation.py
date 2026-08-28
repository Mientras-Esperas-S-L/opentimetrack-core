"""El crédito horario de quien representa a la plantilla (art. 68.e ET).

«Un crédito de horas mensuales retribuidas cada uno de los miembros del comité o
delegado de personal **en cada centro de trabajo**», con una escala por tamaño:
quince horas hasta cien personas, veinte hasta doscientas cincuenta, treinta hasta
quinientas, treinta y cinco hasta setecientas cincuenta, y cuarenta de ahí en
adelante.

**Por centro y no por empresa**, que es lo que más se confunde. El comité es del
centro, así que una empresa de seiscientas personas repartidas en cuatro naves de
ciento cincuenta da veinte horas a cada representante, no treinta y cinco. Un
producto que contara la plantilla entera le daría a cada uno quince horas de más,
y nadie lo notaría hasta una inspección.

**Es un suelo.** «Podrá pactarse en convenio colectivo la acumulación de horas»,
y ampliarlo es corriente: la cifra que manda es la de la empresa cuando la ha
puesto en su catálogo, y esta escala entra cuando no la ha puesto. Cuando la
puesta se queda por debajo, se avisa: eso es lo que hace un suelo.
"""

from __future__ import annotations

#: El permiso al que se aplica, en el catálogo español.
FUNCIONES_DE_REPRESENTACION = "es.union_duties"


def representation_hours(employee, company) -> dict | None:
    """Las horas mensuales que le corresponden, y de dónde salen.

    `None` para quien no está marcado como representante ---la mayoría--- y para
    los países cuyo marco no fija ninguna escala.
    """
    from apps import legal
    from apps.users.models import User

    if not employee.is_worker_representative:
        return None

    escala = getattr(legal.for_company(company), "representation", None)
    if escala is None:
        return None

    # Del **centro** de la persona. Sin centro asignado no se puede contestar
    # sin inventar el tramo, así que se cuenta la empresa y se dice que se ha
    # hecho: una cifra con su salvedad es un dato, y una sin ella es un hecho
    # que puede estar mal.
    if employee.workplace_id:
        cuantos = User.objects.filter(
            tenant=company, is_active=True, workplace_id=employee.workplace_id
        ).count()
        por_centro = True
    else:
        cuantos = User.objects.filter(tenant=company, is_active=True).count()
        por_centro = False

    return {
        "hours": escala.hours_for(cuantos),
        "headcount": cuantos,
        "by_workplace": por_centro,
        "citation": escala.basis,
    }
