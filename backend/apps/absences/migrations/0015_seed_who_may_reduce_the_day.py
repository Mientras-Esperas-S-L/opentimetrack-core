"""Qué tipos pueden reducir la jornada, y el que faltaba.

Aparte de la migración que añade la columna, y no por gusto: hacer el `ALTER
TABLE` y tocar las filas en la misma transacción hace que **la vuelta atrás
falle** en PostgreSQL ---«cannot ALTER TABLE because it has pending trigger
events»---, y una migración que no se puede deshacer es una migración a la que
hay que entrar con miedo.

Hasta ahora quién podía reducir lo decidía `initiated_by`: solo lo que registraba
la empresa. Con el campo nuevo hay que **decir cuáles**, o el ERTE y el mecanismo
RED dejarían de poder hacerlo en cuanto se aplique --- una regresión silenciosa
en el sitio más caro, porque el cuadrante volvería a medir contra la jornada
entera a quien la tiene reducida.

Y se siembra el que faltaba: la reducción por guarda legal del art. 37.6, que la
pide quien trabaja y por eso el criterio anterior la dejaba fuera.

Los valores van escritos aquí y no importados de `apps.legal.es`: una migración
tiene que seguir haciendo lo mismo dentro de diez versiones del catálogo.
"""

from django.db import migrations

#: Los que ya reducían por el criterio viejo, y siguen.
YA_REDUCIAN = ("es.erte", "es.red")

NUEVO = {
    "code": "es.childcare_reduced_hours",
    "name": "Reducción de jornada por guarda legal",
    "family": "SUSPENSION",
    "basis": "Art. 37.6 ET",
    # No la parte no trabajada: la reducción lleva reducción de salario.
    "paid": False,
    "initiated_by": "PERSON",
    "can_reduce_the_day": True,
    "needs_justification": False,
    "unit": "DAYS_CALENDAR",
    "period": "EVENT",
    "note": (
        "Entre un octavo y la mitad de la jornada, por cuidado de un menor de doce "
        "años, de una persona con discapacidad que no desempeñe actividad retribuida, "
        "o de un familiar hasta el segundo grado que no pueda valerse. Pon cuánto se "
        "reduce en la solicitud ---25 si se reduce un cuarto, no 75--- y las fechas: "
        "este derecho se acaba, y sin fecha de fin el cuadrante seguiría midiendo "
        "contra la jornada reducida para siempre. La concreción horaria la elige quien "
        "trabaja (art. 37.7)."
    ),
}


def marcar_los_que_reducen(apps, schema_editor):
    LeaveType = apps.get_model("absences", "LeaveType")
    LeaveType.objects.filter(code__in=YA_REDUCIAN).update(can_reduce_the_day=True)

    # El nuevo, solo donde hay catálogo español y solo si no está ya: una
    # empresa puede haberlo creado a mano con el mismo código.
    Tenant = apps.get_model("tenants", "Tenant")
    con_catalogo = (
        LeaveType.objects.filter(code="es.erte").values_list("tenant_id", flat=True).distinct()
    )
    ya_lo_tienen = set(
        LeaveType.objects.filter(code=NUEVO["code"]).values_list("tenant_id", flat=True)
    )
    espanolas = set(
        Tenant.objects.filter(id__in=list(con_catalogo), country="ES").values_list("id", flat=True)
    )

    LeaveType.objects.bulk_create(
        [LeaveType(tenant_id=quien, **NUEVO) for quien in espanolas - ya_lo_tienen]
    )


def desmarcar(apps, schema_editor):
    """Al revés se quita el sembrado y el campo se va con la columna.

    No se borran las ausencias que lo usaran: eso sería tirar el registro de
    alguien por deshacer una migración.
    """
    LeaveType = apps.get_model("absences", "LeaveType")
    LeaveType.objects.filter(code=NUEVO["code"], absences__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("absences", "0014_leavetype_can_reduce_the_day"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(marcar_los_que_reducen, desmarcar),
    ]
