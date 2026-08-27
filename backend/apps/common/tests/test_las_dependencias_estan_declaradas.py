"""Nada se importa de prestado.

Un `import` que funciona porque **otro paquete arrastra la biblioteca** es una
dependencia que nadie ha declarado y que nadie mantiene. Funciona hasta el día en
que ese otro paquete cambia su árbol, y entonces se rompe en el despliegue, no
aquí: la instalación de desarrollo ya la tenía puesta.

El 27/08/2026 había dos:

- **`cryptography`**, importada por `vapid_keys`, que es un comando de
  producción. La traían `pywebpush`, `py-vapid` y `http_ece`.
- **`pillow`**, importada por la prueba que abre la imagen de un justificante para
  comprobar que es lo que dice ser. La traía `reportlab`.

Ninguna de las dos estaba en `requirements/`. Las dos siguen ahí porque se usan;
lo que cambió es que ahora están dichas.

**Por `ast` y no por `grep`**: hay que distinguir un `import` de una mención en un
comentario, y hay bastantes ---este fichero mismo nombra media docena de paquetes
sin importar ninguno---.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from django.conf import settings

#: Cómo se llama el módulo, cuando no se llama como su paquete. La lista es corta
#: a propósito: si crece mucho, es que alguien está declarando envoltorios en vez
#: de dependencias.
NOMBRE_DEL_PAQUETE = {
    "rest_framework": "djangorestframework",
    "rest_framework_simplejwt": "djangorestframework-simplejwt",
    "corsheaders": "django-cors-headers",
    "django_filters": "django-filter",
    "django_extensions": "django-extensions",
    "environ": "django-environ",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "drf_spectacular": "drf-spectacular",
    "py_vapid": "py-vapid",
    "sentry_sdk": "sentry-sdk",
    "storages": "django-storages",
    "argon2": "argon2-cffi",
}

#: Lo que no es un paquete: el propio proyecto y lo que trae Python.
PROPIO = {"apps", "config", "conftest"}

#: Los que se usan **por su efecto y no por su nombre**, así que no aparecen en
#: ningún fichero y hay que decirlo aquí. Cada uno con dónde, y con la forma de
#: comprobar que sigue siendo verdad ---una exención que nadie valida se queda
#: muerta y acaba justificando lo que ya no se usa---.
SE_USAN_DESDE_LA_CONSOLA = {
    "pytest-cov": "el CI mide cobertura con `pytest --cov=apps`; se comprueba abajo",
    "ipython": (
        "`manage.py shell` lo usa si está instalado, sin nombrarlo en ninguna "
        "configuración. Es una comodidad del equipo: quitarlo no rompe nada y el "
        "shell cae al de Python"
    ),
}


def _declarados() -> set[str]:
    declarados = set()
    carpeta = Path(settings.BASE_DIR) / "requirements"
    for fichero in sorted(carpeta.glob("*.txt")):
        for linea in fichero.read_text(encoding="utf-8").splitlines():
            linea = linea.split("#")[0].strip()
            if not linea or linea.startswith("-"):
                continue
            nombre = re.match(r"([A-Za-z0-9_.\-\[\]]+)", linea)
            if nombre:
                declarados.add(nombre.group(1).split("[")[0].lower().replace("_", "-"))
    return declarados


def _importados() -> dict[str, list[str]]:
    """`{módulo: [ficheros que lo importan]}`, solo lo externo."""
    raiz = Path(settings.BASE_DIR)
    importados: dict[str, list[str]] = {}
    for fichero in sorted(raiz.rglob("*.py")):
        if "/migrations/" in str(fichero) or "/node_modules/" in str(fichero):
            continue
        try:
            arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            modulo = None
            if isinstance(nodo, ast.Import):
                modulo = nodo.names[0].name.split(".")[0]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                modulo = nodo.module.split(".")[0]
            if modulo and modulo not in sys.stdlib_module_names and modulo not in PROPIO:
                importados.setdefault(modulo, []).append(str(fichero.relative_to(raiz)))
    return importados


def test_todo_lo_que_se_importa_esta_declarado():
    declarados = _declarados()
    de_prestado = []
    for modulo, ficheros in sorted(_importados().items()):
        paquete = NOMBRE_DEL_PAQUETE.get(modulo, modulo.lower().replace("_", "-"))
        if paquete in declarados:
            continue
        donde = "producción" if any("/tests/" not in f for f in ficheros) else "pruebas"
        de_prestado.append(f"{modulo} (paquete «{paquete}», en {donde}): {ficheros[0]}")

    assert de_prestado == [], (
        "estos módulos se importan y no están en `requirements/`, así que hoy "
        "funcionan porque otro paquete los arrastra:\n\n  "
        + "\n  ".join(de_prestado)
        + "\n\nDeclara el paquete con la versión que ya está instalada ---mírala, no "
        "la supongas: inventarla da un conflicto de resolución--- o, si el nombre "
        "del módulo no coincide con el del paquete, añádelo a `NOMBRE_DEL_PAQUETE`."
    )


def test_lo_declarado_se_usa():
    """Al revés. Una dependencia que ya no se usa sigue instalándose, sigue
    saliendo en los avisos de seguridad y sigue habiendo que decidir si se
    actualiza.

    Se comprueba contra el código **y contra la configuración**: la mitad de lo
    que hay aquí no se importa nunca ---`gunicorn` es un ejecutable, `whitenoise`
    y `django-redis` se nombran en los ajustes, `ruff` y `pytest` se invocan---.
    Así que basta con que el nombre aparezca en algún sitio.
    """
    raiz = Path(settings.BASE_DIR)
    corpus = []
    for patron in ("apps/**/*.py", "config/**/*.py", "*.py", "*.toml", "*.cfg", "*.ini"):
        for fichero in raiz.glob(patron):
            if fichero.is_file():
                corpus.append(fichero.read_text(encoding="utf-8"))
    todo = "\n".join(corpus).lower()

    huerfanos = []
    for paquete in sorted(_declarados()):
        if paquete in SE_USAN_DESDE_LA_CONSOLA:
            continue
        # Se busca por las dos formas, porque un paquete con guiones se importa
        # con guiones bajos.
        if paquete in todo or paquete.replace("-", "_") in todo:
            continue
        huerfanos.append(paquete)

    assert huerfanos == [], (
        "estos paquetes están declarados y no se nombran en ningún sitio:\n\n  "
        + "\n  ".join(huerfanos)
        + "\n\nSi de verdad no se usan, quítalos. Si se usan por su efecto y no por "
        "su nombre ---un ejecutable, un plugin que se carga solo--- ponlos en "
        "`SE_USAN_DESDE_LA_CONSOLA` diciendo dónde."
    )


# ------------------------------------------------------------------ contraste


def test_el_detector_no_confunde_una_mención_con_un_import():
    """El docstring de este fichero nombra `pillow`, `pywebpush` y `reportlab` sin
    importar ninguno. Un `grep` los contaría."""
    codigo = (
        '"""Este módulo no usa pillow ni reportlab."""\n'
        "# import boto3 -> comentado a propósito\n"
        'MENSAJE = "hace falta cryptography"\n'
        "import json\n"
    )
    arbol = ast.parse(codigo)
    externos = [
        n.names[0].name
        for n in ast.walk(arbol)
        if isinstance(n, ast.Import) and n.names[0].name not in sys.stdlib_module_names
    ]
    assert externos == []


def test_el_detector_encuentra_las_dos_formas_de_importar():
    """`import x` y `from x import y`, que es como estaban las dos que faltaban."""
    importados = _importados()
    # `django` entra por las dos vías en todo el proyecto, así que sirve de testigo.
    assert "django" in importados
    assert len(importados["django"]) > 20, "el barrido está mirando muy pocos ficheros"


def test_la_exencion_de_la_cobertura_sigue_siendo_cierta():
    """`pytest-cov` está exento porque se mide cobertura. Si dejara de medirse, la
    exención pasaría a justificar una dependencia que ya no se usa ---y eso es
    justo lo que este fichero viene a impedir---.

    Se comprueba contra `pyproject.toml`, que está siempre: el fichero del CI vive
    en la raíz del repositorio y el contenedor solo monta `backend/`, así que
    dentro no se puede leer. Se mira **si aparece**, y si no, no se finge: lo que
    sostiene la exención es la configuración de cobertura, que sin nadie que la
    use no tendría por qué existir.

    Lo demás de la lista no se puede validar de ninguna forma: `manage.py shell`
    usa `ipython` porque está instalado, sin decirlo en ninguna parte. Esa exención
    se sostiene solo en su propio texto, y así queda dicho.
    """
    ajustes = Path(settings.BASE_DIR) / "pyproject.toml"
    assert ajustes.is_file(), f"no está `pyproject.toml` donde se esperaba: {ajustes}"
    assert "[tool.coverage" in ajustes.read_text(encoding="utf-8"), (
        "ya no hay configuración de cobertura, así que `pytest-cov` sobra: quítalo "
        "de `requirements/dev.txt` y de `SE_USAN_DESDE_LA_CONSOLA`."
    )

    # Y el CI, cuando se puede ver ---fuera del contenedor---, que es la señal
    # buena: es quien de verdad la invoca.
    ci = Path(settings.BASE_DIR).parent / ".github" / "workflows" / "ci.yml"
    if ci.is_file():
        assert "--cov" in ci.read_text(encoding="utf-8"), (
            "el CI ha dejado de medir cobertura. Si es a propósito, `pytest-cov` "
            "sobra: quítalo de `requirements/dev.txt` y de la lista de exentos."
        )
