"""La puerta de integración no publica «un objeto» y ya.

El esquema es lo que lee quien escribe un conector: es la documentación del
protocolo abierto, y `responses={200: dict}` sale como un objeto sin campos. Con
eso, la forma de la respuesta hay que deducirla probando --- o descubrirla el día
que cambia, en producción.

Se vigila solo la puerta de integración (`/api/app/…` y el fichaje delegado),
que es la que consume software ajeno. Las pantallas propias van con el frontend
en el mismo repositorio y se enteran de un cambio al momento.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

#: Lo que un conector llama. Cada entrada es (ruta, método).
LA_PUERTA = [
    ("/api/app/attendance/", "get"),
    ("/api/app/people/", "get"),
    ("/api/app/people/{reference}/", "get"),
    ("/api/app/people/{reference}/", "put"),
    ("/api/app/people/{reference}/", "delete"),
    ("/api/punches/delegated/", "post"),
]


@pytest.fixture
def esquema(db, settings):
    settings.PUBLISH_API_SCHEMA = True
    respuesta = APIClient().get("/api/schema/?format=json")
    assert respuesta.status_code == 200
    return respuesta.json()


def test_la_sonda_encuentra_la_puerta(esquema):
    """Contraste: si las rutas cambian de nombre, esto avisa en vez de pasar."""
    faltan = [r for r, _m in LA_PUERTA if r not in esquema["paths"]]
    assert faltan == [], f"estas rutas ya no están en el esquema: {faltan}"


@pytest.mark.parametrize(("ruta", "metodo"), LA_PUERTA)
def test_cada_respuesta_dice_su_forma(esquema, ruta, metodo):
    operacion = esquema["paths"][ruta][metodo]
    for codigo, respuesta in operacion["responses"].items():
        if not codigo.startswith("2"):
            continue
        contenido = (respuesta.get("content") or {}).get("application/json", {})
        forma = contenido.get("schema", {})
        assert forma.get("$ref"), (
            f"{metodo.upper()} {ruta} responde {codigo} con un objeto sin campos: "
            f"{forma!r}. Quien escriba un conector no puede saber qué le llega."
        )
