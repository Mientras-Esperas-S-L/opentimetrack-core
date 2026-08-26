"""Lo que corre solo, programado en los dos sitios donde puede correr.

Hay dos formas de programar los trabajos ---cron, que es la de por defecto, y
Celery--- y la documentación es la única que ata las dos. Cuando la vuelta 99
añadió la purga de testigos caducados, la añadió al `beat_schedule` de Celery y
no a la crontab del documento: en la instalación normal, el trabajo que venía a
impedir que una tabla creciera sin techo no corría.

Se cuenta y se compara, en vez de comprobar nombre por nombre, porque los
nombres no coinciden a propósito ---la tarea se llama `flush_expired_tokens` y el
comando `flushexpiredtokens`, que lo trae simplejwt---. Lo que importa es que no
haya un trabajo en una vía que falte en la otra.
"""

import re
from pathlib import Path

from django.core.management import get_commands
from django.test import override_settings

#: En el contenedor la documentación va montada aparte, porque solo se monta
#: `backend/`; fuera de él, el fichero está en el repositorio. Se prueban los dos
#: y se falla diciendo dónde se buscó: una prueba que se salta a sí misma cuando
#: no encuentra lo que compara no comprueba nada.
CANDIDATOS = (
    Path("/docs/trabajos-periodicos.md"),
    Path(__file__).resolve().parents[4] / "docs" / "trabajos-periodicos.md",
)


def documento() -> Path:
    for ruta in CANDIDATOS:
        if ruta.is_file():
            return ruta
    raise AssertionError(
        "no se encuentra `trabajos-periodicos.md`, que es lo que esta prueba compara. "
        f"Buscado en: {', '.join(str(r) for r in CANDIDATOS)}. En el contenedor lo monta "
        "`compose.yml` como `/docs`; si se ha quitado ese volumen, hay que devolverlo."
    )


def comandos_de_la_crontab() -> list[str]:
    """Los `manage.py <algo>` del primer bloque ```cron``` del documento.

    El primero y no todos: el segundo es el ejemplo con contenedores, que repite
    uno solo de los trabajos para enseñar la forma.
    """
    bloques = re.findall(r"```cron\n(.*?)```", documento().read_text(), re.DOTALL)
    assert bloques, "el documento ya no tiene un bloque de crontab"
    return re.findall(r"manage\.py\s+(\S+)", bloques[0])


@override_settings(SCHEDULER="celery")
def test_los_trabajos_de_celery_estan_tambien_en_la_crontab():
    from config.celery import register_periodic_jobs

    class Espia:
        def __init__(self):
            self.tareas = []

        def add_periodic_task(self, _cuando, firma, name=None, **kwargs):
            self.tareas.append(name or firma)

    espia = Espia()
    register_periodic_jobs(espia)

    assert len(espia.tareas) == len(comandos_de_la_crontab()), (
        f"Celery programa {len(espia.tareas)} trabajos {[str(t) for t in espia.tareas]} y la "
        f"crontab de `docs/trabajos-periodicos.md` tiene {len(comandos_de_la_crontab())}. "
        "Quien añada un trabajo tiene que añadirlo en las dos vías: cron es la de por "
        "defecto, así que lo que solo esté en Celery no corre en la instalación normal."
    )


def test_cada_comando_de_la_crontab_existe():
    """Una línea de crontab con una errata no falla: cron la ejecuta, el comando
    no existe, y el error se va al correo de root que nadie lee."""
    conocidos = get_commands()
    for comando in comandos_de_la_crontab():
        assert comando in conocidos, f"la crontab del documento llama a `{comando}`, que no existe"


@override_settings(SCHEDULER="cron")
def test_con_cron_beat_no_programa_nada():
    """Dos programadores lanzando el mismo trabajo es la vía rápida a ejecutarlo
    dos veces, y el documento promete que esto no pasa."""
    from config.celery import register_periodic_jobs

    class Espia:
        def __init__(self):
            self.tareas = []

        def add_periodic_task(self, *args, **kwargs):
            self.tareas.append(args)

    espia = Espia()
    register_periodic_jobs(espia)
    assert espia.tareas == []
