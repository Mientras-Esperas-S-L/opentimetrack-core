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


# ------------------------------------------------------ el hueco que no se veía


def _marcadas_dudosas(idioma: str) -> set[str]:
    """Las entradas que gettext marcó `fuzzy` al reconstruir el catálogo."""
    ruta = Path(settings.BASE_DIR) / "locale" / idioma / "LC_MESSAGES" / "django.po"
    dudosas = set()
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        if "Project-Id-Version" in bloque or not re.search(r"^#, fuzzy", bloque, re.M):
            continue
        cabeza = re.search(r"^msgid (.*?)(?=^msgstr )", bloque + "\nmsgstr ", re.M | re.S)
        if cabeza:
            texto = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', cabeza.group(1)))
            dudosas.add(texto.replace("\\n", "\n").replace('\\"', '"'))
    return dudosas


@pytest.mark.parametrize("idioma", (*IDIOMAS, "es"))
def test_ninguna_cadena_visible_se_queda_en_dudosa(idioma):
    """Un `fuzzy` pasaba el guard de arriba sin estar traducido.

    Cuando se añade una cadena parecida a otra, `makemessages` le pega la
    traducción de la vieja y la marca `#, fuzzy`. Eso deja un `msgstr` **no
    vacío**, así que `_sin_traducir` la da por hecha y la prueba de arriba pasa.

    Lo que hace `msgfmt` con ella, comprobado y no supuesto: **la omite del
    `.mo`**, de modo que la cadena sale en el idioma de partida. No enseña la
    traducción equivocada ---que sería peor--- pero tampoco está traducida, y
    nadie se entera.

    Pasó de verdad: al añadir los periodos de actividad, `activity starts` heredó
    «Registro de actividad» y `that week` heredó «a la semana». Las dos habrían
    salido en castellano dentro del catalán sin que ningún guard dijera nada.

    El castellano entra aquí aunque no esté en `IDIOMAS`: es el idioma al que cae
    todo lo demás, así que un hueco suyo no cae a ningún sitio.
    """
    visibles = _visibles_del_codigo()
    dudosas = sorted(visibles & _marcadas_dudosas(idioma))

    assert dudosas == [], (
        f"{len(dudosas)} mensajes visibles están marcados `fuzzy` en {idioma}, "
        "así que salen sin traducir:\n\n  "
        + "\n  ".join(repr(d[:90]) for d in dudosas[:15])
        + "\n\nRevisa la traducción heredada, corrígela y quita la línea "
        "`#, fuzzy` junto con el `#| msgid` que la acompaña."
    )


def test_el_lector_de_dudosas_sabe_encontrarlas():
    """El contraste. Sin él, un parseo roto daría verde para siempre.

    Se comprueba contra un catálogo escrito aquí, y no contra los del proyecto:
    hoy no tienen ni una dudosa ---esa es la idea--- así que no sirven de patrón
    positivo.
    """
    catalogo = (
        'msgid ""\nmsgstr ""\n"Project-Id-Version: x\\n"\n\n'
        '#, fuzzy\n#| msgid "lo viejo"\nmsgid "lo nuevo"\nmsgstr "traducción heredada"\n\n'
        'msgid "lo seguro"\nmsgstr "traducción buena"\n'
    )
    import tempfile

    with tempfile.TemporaryDirectory() as carpeta:
        destino = Path(carpeta) / "locale" / "xx" / "LC_MESSAGES"
        destino.mkdir(parents=True)
        (destino / "django.po").write_text(catalogo, encoding="utf-8")

        original = settings.BASE_DIR
        try:
            settings.BASE_DIR = carpeta
            assert _marcadas_dudosas("xx") == {"lo nuevo"}
            # Y que no se lleva por delante la que está bien.
            assert "lo seguro" not in _marcadas_dudosas("xx")
        finally:
            settings.BASE_DIR = original


# ------------------------------------------------- lo que ni gettext comprueba


def _con_huecos_distintos(idioma: str) -> list[tuple[str, set, set]]:
    """Entradas cuya traducción no usa los mismos `%(nombre)s` que el original.

    Devuelve `(msgid, los del original, los de la traducción)`.
    """
    ruta = Path(settings.BASE_DIR) / "locale" / idioma / "LC_MESSAGES" / "django.po"
    huecos = re.compile(r"%\((\w+)\)s")
    malas = []
    for bloque in ruta.read_text(encoding="utf-8").split("\n\n"):
        if "Project-Id-Version" in bloque:
            continue
        cabeza = re.search(r"^msgid (.*?)(?=^msgstr )", bloque + "\nmsgstr ", re.M | re.S)
        cola = re.search(r"^msgstr (.*)$", bloque, re.M | re.S)
        if not cabeza or not cola:
            continue

        def junta(trozo: str) -> str:
            return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', trozo))

        original, traducida = junta(cabeza.group(1)), junta(cola.group(1))
        if not traducida:
            continue
        suyos, otros = set(huecos.findall(original)), set(huecos.findall(traducida))
        if suyos != otros:
            malas.append((original, suyos, otros))
    return malas


@pytest.mark.parametrize("idioma", (*IDIOMAS, "es"))
def test_las_traducciones_usan_los_mismos_huecos(idioma):
    """Una traducción heredada de otra cadena parecida se cuela sin marca.

    Pasó el 28/08 con dos: al añadir el aviso del tope del contrato formativo,
    `makemessages` le dejó puesta la traducción del aviso de horas
    complementarias, que habla de `%(over)s` y `%(when)s` --- huecos que el
    mensaje nuevo no tiene ---. Y al del solape de acuerdos le dejó la del solape
    de temporadas.

    **Ninguno estaba marcado `fuzzy`**, así que el guard de dudosas no los veía;
    y `msgfmt --check-format` tampoco dijo nada. Se quedan ahí: una cadena
    diciendo algo que no le corresponde, y con huecos que quien la formatee no va
    a poder rellenar.

    Comprobar los huecos es barato y no depende de saber el idioma: si el
    original dice `%(cap)s` y la traducción no, alguien copió de otro sitio.
    """
    malas = _con_huecos_distintos(idioma)

    assert malas == [], (
        f"{len(malas)} traducción(es) en {idioma} con huecos que no son los del original:\n\n  "
        + "\n  ".join(
            f"{original[:70]!r}\n      original: {sorted(suyos)}  traducción: {sorted(otros)}"
            for original, suyos, otros in malas[:10]
        )
    )


def test_el_lector_de_huecos_sabe_encontrarlos():
    """El contraste, sobre un catálogo escrito aquí: los del proyecto están sanos."""
    catalogo = (
        'msgid ""\nmsgstr ""\n"Project-Id-Version: x\\n"\n\n'
        'msgid "hay %(cuantos)s cosas"\nmsgstr "hi ha %(otros)s coses"\n\n'
        'msgid "hay %(cuantos)s más"\nmsgstr "n\'hi ha %(cuantos)s més"\n'
    )
    import tempfile

    with tempfile.TemporaryDirectory() as carpeta:
        destino = Path(carpeta) / "locale" / "xx" / "LC_MESSAGES"
        destino.mkdir(parents=True)
        (destino / "django.po").write_text(catalogo, encoding="utf-8")

        original = settings.BASE_DIR
        try:
            settings.BASE_DIR = carpeta
            malas = _con_huecos_distintos("xx")
            assert [m[0] for m in malas] == ["hay %(cuantos)s cosas"]
        finally:
            settings.BASE_DIR = original
