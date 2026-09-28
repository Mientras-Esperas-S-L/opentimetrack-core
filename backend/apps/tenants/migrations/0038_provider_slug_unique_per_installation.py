"""Un identificador de proveedor por instalación, no por empresa.

La dirección de entrada lleva solo el identificador, así que dos empresas cuyo
proveedor se llamaba igual compartían uno y la entrada se iba a la primera. Aquí
se desdoblan los repetidos que ya existan: se queda con el suyo el más antiguo y
los demás reciben un sufijo.
"""

from django.db import migrations


def desdoblar(apps, schema_editor):
    SsoProvider = apps.get_model("tenants", "SsoProvider")
    todos = SsoProvider._base_manager.all().order_by("created_at", "pk")
    usados = set()
    for proveedor in todos:
        base = proveedor.slug or "provider"
        slug, n = base, 2
        while slug in usados:
            slug = f"{base[:56]}-{n}"
            n += 1
        usados.add(slug)
        if slug != proveedor.slug:
            proveedor.slug = slug
            proveedor.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [("tenants", "0037_identity_name_help_text")]

    operations = [migrations.RunPython(desdoblar, migrations.RunPython.noop)]
