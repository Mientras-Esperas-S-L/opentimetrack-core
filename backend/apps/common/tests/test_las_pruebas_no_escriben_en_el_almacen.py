"""Lo que suben las pruebas no acaba en el almacén de desarrollo.

`MEDIA_ROOT` sale de `base.py` como `BASE_DIR / "media"` y pytest corre con los
ajustes de desarrollo, así que cada justificante que subía una prueba se quedaba
ahí. Medido: **4.936 ficheros de los que solo 12 los referenciaba una ausencia**
--- 8,1 MiB de huérfanos --- y creciendo tanda a tanda: 4.391 el 26/08 por la
mañana, 4.625 unas horas después, 4.936 hoy.

El producto no tiene la culpa: borra el fichero en `transaction.on_commit`, y en
una prueba con `django_db` esa transacción no se confirma nunca, así que la
limpieza no llega a ejecutarse. La limpieza es correcta; el sitio donde escriben
las pruebas, no.

Con el almacén en un temporal de la sesión deja de importar, y de paso una prueba
ya no puede leer por accidente lo que subió otra.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def test_el_almacen_de_las_pruebas_no_es_el_de_desarrollo():
    de_desarrollo = Path(settings.BASE_DIR) / "media"
    actual = Path(settings.MEDIA_ROOT)

    assert actual != de_desarrollo, (
        "las pruebas están escribiendo en el almacén de desarrollo: lo que suban "
        "se queda ahí para siempre, porque el borrado del producto va en on_commit "
        "y en una prueba esa transacción no se confirma"
    )
    assert de_desarrollo not in actual.parents, f"{actual} está dentro de {de_desarrollo}"


@pytest.mark.django_db
def test_y_un_fichero_subido_aterriza_en_el_temporal():
    """El contraste: que el almacén siga funcionando. Un `MEDIA_ROOT` apuntando
    a un sitio no escribible pasaría la prueba de arriba y rompería el producto."""
    nombre = default_storage.save("justifications/prueba.txt", ContentFile(b"x"))
    try:
        ruta = Path(default_storage.path(nombre))
        assert ruta.is_file(), "no se pudo escribir en el almacén de las pruebas"
        assert Path(settings.MEDIA_ROOT) in ruta.parents
    finally:
        default_storage.delete(nombre)
