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
