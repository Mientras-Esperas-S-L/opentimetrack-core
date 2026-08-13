"""La extensión que permite buscar sin acentos.

`unaccent` viene con PostgreSQL y desde la versión 13 está marcada como de
confianza, así que la instala el dueño de la base sin hacer falta un superusuario.

Va en `common` porque no es de nadie en concreto: la usan el buscador de
personas, el de departamentos, el de centros y el de aplicaciones.
"""

from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [UnaccentExtension()]
