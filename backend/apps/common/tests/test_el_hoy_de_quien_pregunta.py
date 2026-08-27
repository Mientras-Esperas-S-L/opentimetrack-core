"""`date.today()` no vuelve a colarse, ni en el producto ni en las pruebas.

`apps/common/clock.py` lo dice en su primera línea: «`date.today()` es la trampa:
es la fecha UTC del contenedor, equivocada para todos en España entre medianoche y
la 01:00 (las 02:00 en verano). Se colaron cuatro veces antes de que este módulo
existiera». Después de eso apareció una quinta ---en la puerta de integración, que
respondía «ayer» a las 00:30 de Madrid--- y veinticinco más en las pruebas.

Las de las pruebas no son inocuas. Una prueba que siembra un rango con
`date.today()` y luego pregunta al producto ---que responde con
`local_today(empresa)`--- está comparando **dos días distintos** durante esas dos
horas. El fallo sale de madrugada, en una máquina y no en otra, y se lee como un
defecto del producto.

Por qué hace falta un guard y no basta con haberlos quitado: nada en el lenguaje
señala `date.today()` como sospechoso. Es la llamada obvia, la que cualquiera
escribe sin pensar, y la correcta pide un argumento que hay que ir a buscar. Sin
esto vuelve.

Se comprueba con `ast` y no con `grep`, y esa es la mitad del trabajo: los comentarios
que explican por qué **no** se usa `date.today()` contienen el texto
`date.today()`. Un grep cuenta cinco «usos» en producción que son cinco
advertencias de no usarlo, y el 27/08 me hizo perder una hora persiguiéndolos.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from django.conf import settings

#: Vacía, y así debería seguir. Si algún día hace falta una excepción, va aquí con
#: el motivo escrito al lado, y no como una supresión suelta en la línea ---que
#: no dice por qué y nadie vuelve a mirar---.
#:
#: Escrito así y no con el nombre de la directiva: `ruff` 0.16.4 la lee **dentro
#: de este comentario** y avisa de que está mal formada, en cada ejecución.
PERMITIDOS: dict[str, str] = {}


def _llamadas_a_today(codigo: str) -> list[int]:
    """Las líneas donde se llama a `algo.today()` sin argumentos.

    Sin argumentos a propósito: `date.today()` es la trampa, y
    `alguna_cosa.today(zona)` no lo es. Y por `ast`, así que un `date.today()`
    dentro de una cadena o de un comentario no cuenta.
    """
    hallados: list[int] = []

    class Visita(ast.NodeVisitor):
        def visit_Call(self, nodo: ast.Call) -> None:
            destino = nodo.func
            if isinstance(destino, ast.Attribute) and destino.attr == "today" and not nodo.args:
                hallados.append(nodo.lineno)
            self.generic_visit(nodo)

    Visita().visit(ast.parse(codigo))
    return sorted(hallados)


def test_nadie_usa_date_today():
    raiz = Path(settings.BASE_DIR) / "apps"
    culpables = []
    for fichero in sorted(raiz.rglob("*.py")):
        if "/migrations/" in str(fichero):
            continue
        relativo = str(fichero.relative_to(settings.BASE_DIR))
        if relativo in PERMITIDOS:
            continue
        for linea in _llamadas_a_today(fichero.read_text(encoding="utf-8")):
            culpables.append(f"{relativo}:{linea}")

    assert culpables == [], (
        "hay llamadas a `.today()`, que devuelve la fecha UTC del contenedor:\n\n  "
        + "\n  ".join(culpables)
        + "\n\nUsa `local_today(X)` de `apps.common.clock`, con la empresa, el centro "
        "de trabajo o la persona ---responde con la zona de quien pregunta---. En un "
        "módulo donde todavía no hay ninguno, ancla la zona a mano y déjalo dicho."
    )


# ------------------------------------------------------------------ contraste


def test_el_detector_encuentra_lo_que_busca():
    """Porque la comprobación de arriba acaba de dar cero, y cero no prueba nada
    por sí solo: se le da un caso conocido y tiene que verlo."""
    assert _llamadas_a_today("import datetime\nx = datetime.date.today()\n") == [2]
    assert _llamadas_a_today("from datetime import date\ny = date.today()\n") == [2]


def test_el_detector_no_cuenta_lo_que_solo_lo_menciona():
    """La otra mitad, y la que de verdad importa: cuanto mejor documentado está un
    antipatrón, más falsos positivos da buscarlo por texto.

    Los cinco «usos» que un grep encuentra hoy en el código de producción son
    cinco comentarios avisando de que no se use.
    """
    assert _llamadas_a_today("# ojo: date.today() da la fecha del contenedor\nx = 1\n") == []
    assert _llamadas_a_today('"""No usar date.today() aquí."""\nx = 1\n') == []
    assert _llamadas_a_today('MENSAJE = "date.today() está prohibido"\n') == []


def test_el_detector_deja_pasar_today_con_argumentos():
    """`local_today(empresa)` no se llama `today`, pero algo podría. Lo que la
    trampa tiene de trampa es que no pregunta de quién es el día."""
    assert _llamadas_a_today("x = reloj.today(empresa)\n") == []


@pytest.mark.parametrize("modulo", ["apps/common/clock.py"])
def test_el_modulo_que_lo_resuelve_sigue_ahi(modulo):
    """Si alguien retira `local_today`, el guard de arriba seguiría en verde y no
    habría con qué sustituir lo que prohíbe."""
    from apps.common.clock import local_date_of, local_today

    assert callable(local_today)
    assert callable(local_date_of)
    assert (Path(settings.BASE_DIR) / modulo).is_file()
