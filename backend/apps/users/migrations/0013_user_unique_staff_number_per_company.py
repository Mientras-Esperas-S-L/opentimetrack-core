"""El número de empleado, único dentro de cada empresa.

Es el puente con las aplicaciones que fichan en nombre de alguien: el conector
manda «EMP-0042» y el servidor tiene que saber a quién se refiere. Repetido, la
resolución devuelve a quien salga primero y los fichajes acaban en la ficha de
otra persona --- un fallo que no avisa y que solo se descubre cuando alguien
mira su registro y ve jornadas que no hizo.
"""

from django.db import migrations, models


def blank_the_duplicates(apps, schema_editor):
    """Deja el número al más antiguo y vacía el de los demás.

    No se puede elegir ganador entre dos personas que comparten el ancla de
    identidad, así que no se elige: se conserva en quien lo tuvo primero y se
    vacía en el resto, que es un estado honesto --- «esta persona no tiene
    número» --- y que un administrador puede corregir viéndolo. La alternativa
    era no poder aplicar la restricción, y entonces el fallo sigue ahí.
    """
    from collections import defaultdict

    User = apps.get_model("users", "User")
    vistos = defaultdict(list)
    for person in User.objects.exclude(employee_id="").order_by("date_joined", "id"):
        vistos[(person.tenant_id, person.employee_id)].append(person)

    repetidos = [p for grupo in vistos.values() for p in grupo[1:]]
    for person in repetidos:
        person.employee_id = ""
    if repetidos:
        User.objects.bulk_update(repetidos, ["employee_id"])


class Migration(migrations.Migration):
    dependencies = [("users", "0012_user_wants_punch_reminders")]

    operations = [
        migrations.RunPython(blank_the_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("employee_id", ""), _negated=True),
                fields=("tenant", "employee_id"),
                name="unique_staff_number_per_company",
            ),
        ),
    ]
