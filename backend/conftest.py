"""Shared test setup."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import override_settings


@pytest.fixture(autouse=True, scope="session")
def _almacen_de_usar_y_tirar(tmp_path_factory):
    """Los ficheros que suben las pruebas van a un directorio temporal.

    `MEDIA_ROOT` sale de `base.py` como `BASE_DIR / "media"`, y pytest corre con
    los ajustes de desarrollo, así que **cada justificante que sube una prueba se
    quedaba en el almacén de desarrollo**. Medido: 4.936 ficheros de los que solo
    12 los referenciaba una ausencia, 8,1 MiB de huérfanos --- y creciendo tanda a
    tanda: 4.391 el 26/08, 4.625 unas horas después, 4.936 hoy.

    El fichero no se borra al terminar la prueba porque el producto lo quita en
    `transaction.on_commit`, y en una prueba con `django_db` la transacción no se
    confirma nunca. O sea: la limpieza del producto es correcta y en pruebas no
    llega a ejecutarse.

    Con el almacén aparte deja de importar. El directorio lo borra pytest al
    terminar la sesión, y de paso una prueba ya no puede leer por accidente lo
    que subió otra.
    """
    with override_settings(MEDIA_ROOT=str(tmp_path_factory.mktemp("media"))):
        yield


@pytest.fixture(autouse=True)
def _empty_rate_limit_buckets():
    """Each test starts with the throttle counters at zero.

    Rate limiting counts in the cache, and the cache does not roll back with
    the transaction. Without this, the fifth test to sign in within a minute
    gets a 429 and the failure reads like a broken login --- and worse, the
    order of the suite starts deciding which tests pass.

    Cleared rather than disabled: a test that wants to prove the limit works
    should be able to, and one that merely signs in should not spend somebody
    else's budget.
    """
    cache.clear()
    yield
