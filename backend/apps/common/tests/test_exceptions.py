"""Todos los errores de la API salen con la misma forma."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import translation
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.views import APIView

from apps.common.exceptions import (
    BusinessRuleError,
    _mensaje_de_espera,
    api_exception_handler,
)


def _manejar(exc):
    return api_exception_handler(exc, {"view": APIView()})


def test_el_error_lleva_siempre_codigo_mensaje_y_detalles():
    respuesta = _manejar(NotFound())

    assert respuesta.status_code == 404
    assert set(respuesta.data["error"]) == {"code", "message", "details"}


def test_una_regla_de_negocio_responde_409_y_no_400():
    """400 es «lo has escrito mal»; 409 es «no se puede hacer». No es lo mismo."""
    exc = BusinessRuleError(
        code="punch_blocked_by_absence",
        message="No puedes fichar: tienes una ausencia aprobada para hoy.",
        details={"date": "2026-05-26"},
    )

    respuesta = _manejar(exc)

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "punch_blocked_by_absence"
    assert respuesta.data["error"]["details"]["date"] == "2026-05-26"


def test_los_errores_de_validacion_conservan_el_campo_que_falla():
    respuesta = _manejar(ValidationError({"email": ["Este campo es obligatorio."]}))

    assert respuesta.status_code == 400
    assert "email" in respuesta.data["error"]["details"]


def test_el_aviso_de_demasiados_intentos_dice_cuanto_falta():
    """Y lo dice en castellano, no en el original de DRF.

    «Solicitud fue regulada (throttled). Se espera que esté disponible en 58
    segundos.» lo lee quien acaba de fallar cinco veces la contraseña: el peor
    momento para pedirle que descifre nada. Lo único accionable es el plazo, y
    ese se conserva.
    """
    with translation.override("es"):
        assert "58 segundos" in _mensaje_de_espera(58)
        assert "throttled" not in _mensaje_de_espera(58)
        # Sin plazo conocido tampoco se queda mudo.
        assert _mensaje_de_espera(0)


@pytest.mark.parametrize("minutos", [1, 2, 5, 45, 59])
def test_la_espera_en_minutos_nunca_sale_en_blanco(minutos):
    """El fallo que cazó esta prueba: para 2, 5 o 45 minutos el texto era «».

    El catálogo declara la regla plural de CLDR ---`nplurals=3`---, donde la
    forma 1 es la de los millones y la 2 la corriente: 1 usa la 0, un millón la
    1, y **todo lo demás** la 2. Estaban rellenas la 0 y la 1, así que la única
    que se usa de verdad estaba vacía, y gettext con una forma vacía no cae al
    inglés: devuelve la cadena vacía.

    Se llega por el límite de peticiones por hora, donde la espera puede pasar
    de la hora: quien lo agota se quedaba mirando un error sin texto.
    """
    with translation.override("es"):
        mensaje = _mensaje_de_espera(minutos * 60)

    assert mensaje.strip(), f"mensaje vacío para {minutos} minutos"
    assert str(minutos) in mensaje


def test_ninguna_forma_plural_del_catalogo_se_queda_sin_traducir():
    """La comprobación general, que es la que aguanta.

    Arreglar la entrada de los minutos no impide que la siguiente plural nazca
    igual: es un descuido de una línea y msgfmt lo da por bueno ---contaba 615
    mensajes traducidos con esa forma vacía dentro---. Así que se leen las tres
    formas de cada plural del catálogo.
    """
    catalogo = Path(settings.BASE_DIR) / "locale" / "es" / "LC_MESSAGES" / "django.po"
    bloques = catalogo.read_text(encoding="utf-8").split("\n\n")

    plurales = [b for b in bloques if "msgid_plural" in b]
    # Contraste: si un día no hay plurales, esta prueba no está comprobando nada.
    assert plurales, "no se encontró ninguna entrada plural; ¿cambió el formato?"

    def sin_rellenar(bloque: str) -> bool:
        """`msgstr[N] ""` **y nada detrás**.

        La primera versión de esto miraba solo la línea, y daba falso positivo
        en cuanto una traducción era larga: gettext parte las cadenas en varias
        líneas y la primera es siempre `msgstr[N] ""` con el texto debajo entre
        comillas. O sea que la comprobación se ponía roja por una traducción
        correcta --- que es el mismo daño que dejarla pasar vacía, porque a la
        segunda vez que ladra sin motivo se desactiva.
        """
        lineas = bloque.splitlines()
        for i, linea in enumerate(lineas):
            if not re.match(r'^msgstr\[\d\] ""$', linea):
                continue
            sigue = lineas[i + 1] if i + 1 < len(lineas) else ""
            if not sigue.startswith('"'):
                return True
        return False

    sin_traducir = [b for b in plurales if sin_rellenar(b)]
    assert not sin_traducir, "hay formas plurales vacías:\n\n" + "\n\n".join(sin_traducir)

    # Y el contraste, porque una comprobación que acaba de dar un falso positivo
    # merece que se demuestre que **sigue** cazando el caso de verdad: el fallo
    # original era una forma vacía y sola al final del bloque.
    roto = 'msgid "x"\nmsgid_plural "xs"\nmsgstr[0] "uno"\nmsgstr[1] "unos"\nmsgstr[2] ""'
    assert sin_rellenar(roto), "la comprobación ya no vería el fallo que la trajo"


def test_el_catalogo_no_lleva_entradas_marcadas_fuzzy():
    """Una traducción `fuzzy` **no se usa**: gettext cae al inglés y se calla.

    Y las escribe `makemessages` solo, adivinando a partir de una cadena
    parecida. Las adivinanzas son malas por construcción: «collective agreement»
    salió como «Aplicada con acuerdo», y cambiar el texto de un error existente
    ---«Nobody worked in that period.»--- dejó el mensaje en inglés en
    producción durante dos vueltas de auditoría, con el `.po` diciendo que
    estaba traducido.

    O sea que es un vacío que se comprueba limpio por dos vías a la vez: el
    fichero parece completo y `msgfmt --statistics` cuenta la entrada como
    traducida. Solo la marca lo delata.
    """
    # Los cuatro catálogos, no solo el castellano. Al añadir catalán, gallego y
    # euskera, `makemessages` dejó los tres con la cabecera marcada `fuzzy`, que
    # es como los crea: una comprobación que mirara solo el castellano habría
    # dado verde con los tres recién nacidos así.
    dudosas = []
    for idioma in ("es", "ca", "gl"):
        catalogo = Path(settings.BASE_DIR) / "locale" / idioma / "LC_MESSAGES" / "django.po"
        if not catalogo.exists():
            continue
        for bloque in catalogo.read_text(encoding="utf-8").split("\n\n"):
            if re.search(r"^#,.*\bfuzzy\b", bloque, flags=re.MULTILINE):
                dudosas.append(f"[{idioma}] {bloque}")

    assert not dudosas, (
        "hay traducciones marcadas fuzzy, que en ejecución no se usan:\n\n" + "\n\n".join(dudosas)
    )

    # El contraste, porque esto acaba de dar cero y cero no prueba nada por sí
    # solo: la marca se busca donde de verdad la escribe gettext.
    ejemplo = '#: apps/x.py:1\n#, fuzzy\nmsgid "a"\nmsgstr "b"'
    assert re.search(r"^#,.*\bfuzzy\b", ejemplo, flags=re.MULTILINE)


@pytest.mark.parametrize("idioma", ["ca", "gl"])
def test_lo_que_no_esta_traducido_cae_al_castellano_y_no_al_ingles(idioma):
    """La razón de que un catálogo a medias sea utilizable.

    Los catálogos nuevos traducen los mensajes que llegan a las personas y
    dejan sin traducir las etiquetas internas del modelo. Eso solo vale si lo
    que falta cae al **castellano**: si cayera al inglés ---que es el idioma en
    que se escriben los `msgid`--- una empresa catalana vería su producto en dos
    idiomas extranjeros a la vez.

    Cae al castellano porque `LANGUAGE_CODE` es `es` y Django encadena por ahí.
    Es un comportamiento del que depende toda la decisión, así que se comprueba
    en vez de darse por sabido.
    """
    sin_traducir = "night worker"  # etiqueta de modelo, fuera del subconjunto

    with translation.override(idioma):
        assert translation.gettext(sin_traducir) == "trabajador nocturno"


@pytest.mark.parametrize("idioma", ["ca", "gl"])
def test_los_mensajes_que_ve_una_persona_si_estan_traducidos(idioma):
    """El contraste del de arriba: si todo cayera al castellano, aquel pasaría
    igual y no probaría nada."""
    with translation.override(idioma):
        traducido = translation.gettext(
            "You clocked a moment ago. Check the screen before clocking again."
        )

    assert traducido != "Acabas de fichar. Mira la pantalla antes de volver a pulsar."
    assert traducido
