"""Catalán y gallego no se quedan atrás en lo que ve una persona.

El criterio, que ya estaba tomado y ahora se comprueba: **se traduce lo que llega
a alguien y se deja sin traducir la etiqueta de un campo**. Funciona porque lo que
falta cae al castellano y no al inglés ---`LANGUAGE_CODE` es `es` y Django encadena
por ahí---, lo cual comprueba `test_lo_que_no_esta_traducido_cae_al_castellano_y_no_al_ingles`.

Sin este guard el criterio no se sostiene solo. El 27/08/2026 había **207
mensajes visibles sin traducir** en los dos catálogos: nadie los había dejado
así a propósito, simplemente se fueron añadiendo funciones y los catálogos no
crecieron con ellas. Y no se veía, porque cada uno caía al castellano y la pantalla
seguía siendo legible.

**Lo que decide el grupo es qué envuelve la cadena, no en qué fichero está.** Un
`verbose_name` dentro de `models.CharField(...)` es una etiqueta de campo; el mismo
texto en un `TextChoices` sale en el calendario, en el informe y en un correo. En
este proyecto los modelos viven en `models.py`, en `corrections.py`, en
`applications.py`, en `holidays.py`, en `rules.py` y en `payroll.py`, así que
clasificar por ruta metía dieciocho etiquetas en el grupo equivocado ---y, peor,
escondía ciento cuarenta y siete cadenas visibles entre ellas---.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from django.conf import settings

#: Las funciones de gettext que se usan aquí.
TRADUCTORAS = {"_", "gettext", "gettext_lazy", "ngettext", "ngettext_lazy", "pgettext"}

IDIOMAS = ("ca", "gl")


def _es_campo(nodo: ast.Call) -> bool:
    destino = nodo.func
    nombre = destino.attr if isinstance(destino, ast.Attribute) else getattr(destino, "id", "")
    return nombre.endswith("Field")


def clasifica(codigo: str) -> dict[str, str]:
    """`{cadena: 'campo' | 'visible'}`.

    Si la misma cadena aparece en los dos sitios gana `visible`: da igual que sea
    la etiqueta de un campo en algún lado si en otro se le enseña a alguien.
    """
    arbol = ast.parse(codigo)
    padres: dict[int, ast.AST] = {}
    for nodo in ast.walk(arbol):
        for hijo in ast.iter_child_nodes(nodo):
            padres[id(hijo)] = nodo

    salida: dict[str, str] = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        destino = nodo.func
        nombre = destino.attr if isinstance(destino, ast.Attribute) else getattr(destino, "id", "")
        if nombre not in TRADUCTORAS or not nodo.args:
            continue
        primero = nodo.args[0]
        if not isinstance(primero, ast.Constant) or not isinstance(primero.value, str):
            continue

        dentro_de_campo = False
        actual = padres.get(id(nodo))
        while actual is not None:
            if isinstance(actual, ast.Call) and _es_campo(actual):
                dentro_de_campo = True
                break
            actual = padres.get(id(actual))

        cadena = primero.value
        if salida.get(cadena) != "visible":
            salida[cadena] = "campo" if dentro_de_campo else "visible"
    return salida


def _visibles_del_codigo() -> set[str]:
    todas: dict[str, str] = {}
    for fichero in sorted((Path(settings.BASE_DIR) / "apps").rglob("*.py")):
        if "/migrations/" in str(fichero) or "/tests/" in str(fichero):
            continue
        try:
            for cadena, grupo in clasifica(fichero.read_text(encoding="utf-8")).items():
                if todas.get(cadena) != "visible":
                    todas[cadena] = grupo
        except SyntaxError:
            continue
    return {c for c, g in todas.items() if g == "visible"}


def _sin_traducir(idioma: str) -> set[str]:
    ruta = Path(settings.BASE_DIR) / "locale" / idioma / "LC_MESSAGES" / "django.po"
    faltan = set()
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        if "Project-Id-Version" in bloque:
            continue
        cabeza = re.search(r"^msgid (.*?)(?=^msgstr )", bloque + "\nmsgstr ", re.M | re.S)
        cola = re.search(r"^msgstr (.*)$", bloque, re.M | re.S)
        if not cabeza or not cola:
            continue
        def junta(trozo: str) -> str:
            return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', trozo))
        if not junta(cola.group(1)):
            faltan.add(junta(cabeza.group(1)).replace("\\n", "\n").replace('\\"', '"'))
    return faltan


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_lo_que_ve_una_persona_esta_traducido(idioma):
    visibles = _visibles_del_codigo()
    faltan = sorted(visibles & _sin_traducir(idioma))

    assert faltan == [], (
        f"{len(faltan)} mensajes que ve una persona no están en {idioma}:\n\n  "
        + "\n  ".join(repr(f[:90]) for f in faltan[:25])
        + (f"\n  ... y {len(faltan) - 25} más" if len(faltan) > 25 else "")
        + "\n\nSe traduce lo que llega a alguien; la etiqueta de un campo se puede "
        "dejar, porque cae al castellano. Si no hay quien lo revise, tradúcelo lo "
        "mejor que puedas y déjalo marcado con `# revisar:` como los demás."
    )


# ------------------------------------------------------------------ contraste


def test_la_clasificacion_distingue_el_campo_de_lo_que_se_enseña():
    """Las dos comprobaciones de arriba acaban de dar cero, y cero no prueba nada
    por sí solo. Este es el caso conocido: el mismo texto en los dos sitios."""
    codigo = (
        "from django.db import models\n"
        "from django.utils.translation import gettext_lazy as _\n"
        "class Cosa(models.Model):\n"
        "    campo = models.CharField(_('etiqueta de campo'), max_length=1)\n"
        "class Estado(models.TextChoices):\n"
        "    UNO = 'UNO', _('sale en pantalla')\n"
    )
    grupos = clasifica(codigo)
    assert grupos["etiqueta de campo"] == "campo"
    assert grupos["sale en pantalla"] == "visible"


def test_una_cadena_en_los_dos_sitios_cuenta_como_visible():
    """Porque el coste de traducir de más es una traducción de sobra, y el de
    traducir de menos es una pantalla en dos idiomas."""
    codigo = (
        "from django.db import models\n"
        "from django.utils.translation import gettext_lazy as _\n"
        "campo = models.CharField(_('mismo texto'), max_length=1)\n"
        "aviso = _('mismo texto')\n"
    )
    assert clasifica(codigo)["mismo texto"] == "visible"


def test_el_lector_del_catalogo_ve_los_huecos():
    """Y que sabe leer un `.po`: si devolviera un conjunto vacío por un error de
    parseo, las dos pruebas de arriba pasarían para siempre."""
    for idioma in IDIOMAS:
        faltan = _sin_traducir(idioma)
        # Quedan las etiquetas de campo, a propósito. Si esto llega a cero algún
        # día será porque alguien las tradujo, y entonces habrá que quitar esta
        # comprobación a mano en vez de dejarla mentir.
        assert len(faltan) > 50, (
            f"{idioma}: el lector encuentra solo {len(faltan)} huecos, y deberían "
            "quedar las etiquetas de campo sin traducir. ¿Se ha roto el parseo?"
        )
