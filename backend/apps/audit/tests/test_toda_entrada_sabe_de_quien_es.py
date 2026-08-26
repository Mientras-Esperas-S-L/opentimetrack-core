"""Una entrada de auditoría sin empresa no se guarda, y nadie se entera.

`record()` deduce la empresa del actor. Cuando no hay actor hay que pasarla, y
si falta la entrada **se descarta con un aviso en el log**: la operación sale
bien, la pantalla no cambia, las pruebas pasan y el rastro se queda vacío. Es la
peor forma de fallar que tiene esta tabla, porque lo que se pierde solo se echa
de menos el día que alguien pregunta quién cambió algo.

Cazado el 25/08/2026 en `tenants/people_api.py`: una aplicación integrada daba
de alta a una persona, le cambiaba el correo ---que es su identificador de
acceso--- y la daba de baja ---y a partir de ahí no podía fichar---, y no había
ni una línea. Las dos llamadas pasaban `actor=None`, que es correcto (quien
actúa es una aplicación y no tiene fila en `users`) y omitían `company=`, que no
lo era.

Esta sonda lee el código en vez de ejecutarlo, a propósito: el defecto no se ve
en ninguna respuesta y una prueba de comportamiento tendría que existir para
cada sitio que llama. Aquí basta con no volver a escribirlo.
"""

from __future__ import annotations

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[3] / "apps"


def _llamadas_a_record():
    """Cada `record(...)` del código de producción, con su fichero y su línea."""
    for fichero in sorted(RAIZ.rglob("*.py")):
        if "migrations" in fichero.parts or "tests" in fichero.parts:
            continue
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            nombre = getattr(nodo.func, "id", None) or getattr(nodo.func, "attr", None)
            if nombre == "record":
                yield fichero, nodo


def test_la_sonda_encuentra_las_llamadas():
    """Contraste: una sonda que no ve nada pasaría siempre.

    Sin esto, un cambio de nombre en `record()` ---o un `rglob` que apunte al
    sitio equivocado--- dejaría la comprobación de abajo recorriendo una lista
    vacía y diciendo que todo está bien.
    """
    assert len(list(_llamadas_a_record())) > 20


def test_si_no_hay_actor_hay_empresa():
    sin_empresa = []
    for fichero, llamada in _llamadas_a_record():
        argumentos = {k.arg for k in llamada.keywords if k.arg}
        actor = next((k.value for k in llamada.keywords if k.arg == "actor"), None)
        actor_es_none = isinstance(actor, ast.Constant) and actor.value is None
        if actor_es_none and "company" not in argumentos:
            sin_empresa.append(f"{fichero.relative_to(RAIZ)}:{llamada.lineno}")

    assert sin_empresa == [], (
        "Estas llamadas a record() se descartarían enteras, porque sin actor no "
        "hay empresa que deducir. Pásale company=: " + ", ".join(sin_empresa)
    )
