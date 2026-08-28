"""La columna que dice si un tipo de permiso puede reducir la jornada.

Los datos van en la 0015, aparte: el `ALTER TABLE` y el `UPDATE` en la misma
transacción rompen la vuelta atrás en PostgreSQL.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("absences", "0013_alter_absence_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavetype",
            name="can_reduce_the_day",
            field=models.BooleanField(default=False, verbose_name="may reduce the working day"),
        ),
    ]
