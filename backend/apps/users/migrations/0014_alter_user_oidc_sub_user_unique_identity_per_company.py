"""La identidad federada pasa a ser única por empresa, y a guardarse en blanco.

Dos cambios que van juntos:

- `oidc_sub` deja de ser único en toda la plataforma. Lo era a secas, y eso
  contradecía lo que la propia clase declara para el correo: una persona puede
  trabajar para dos empresas, y en un sistema pensado para integradores eso no es
  el caso raro. Con la restricción global, la segunda empresa no podía darla de
  alta y su conector recibía un 500 sin código al que reaccionar.

- Y deja de admitir `NULL`: quien no tiene identidad federada guarda la cadena
  vacía, como `employee_id`. Es la convención de esta misma clase y la que la
  restricción parcial necesita para excluirlos.

El paso de datos no es opcional: la base de desarrollo tenía 279 filas con NULL
sobre 280, así que sin él la migración se cae al pasar el campo a NOT NULL.
"""

from django.db import migrations, models


def vaciar_los_nulos(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(oidc_sub__isnull=True).update(oidc_sub="")


def volver_a_ponerlos(apps, schema_editor):
    """La vuelta atrás no distingue quién era NULL y quién cadena vacía.

    No se puede: la información se perdió al vaciarlos, y las dos cosas
    significaban lo mismo --- sin identidad federada. Se deja en blanco, que es
    lo que el campo admite en las dos direcciones.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("tenants", "0021_remove_tenantlimits_max_admins_and_more"),
        ("users", "0013_user_unique_staff_number_per_company"),
    ]

    operations = [
        # En tres pasos, y el orden importa. Vaciar los nulos con el índice
        # único todavía puesto choca a la segunda fila: todas pasarían a valer
        # lo mismo. Así que primero se quita la unicidad global, luego se
        # rellenan, y solo entonces el campo pasa a NOT NULL.
        migrations.AlterField(
            model_name="user",
            name="oidc_sub",
            field=models.CharField(
                blank=True, max_length=255, null=True, verbose_name="identity provider subject"
            ),
        ),
        migrations.RunPython(vaciar_los_nulos, volver_a_ponerlos),
        migrations.AlterField(
            model_name="user",
            name="oidc_sub",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="identity provider subject"
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("oidc_sub", ""), _negated=True),
                fields=("tenant", "oidc_sub"),
                name="unique_identity_per_company",
            ),
        ),
    ]
