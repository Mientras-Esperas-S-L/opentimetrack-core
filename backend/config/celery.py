"""Celery, para quien lo quiera. Nadie está obligado.

El producto tiene trabajos que se repiten --- recordar un fichaje, purgar
metadatos de seguridad, tirar testigos caducados, borrar el registro que pasó su
plazo de conservación --- y hay dos maneras honradas de repetirlos:

- **cron**, que ya está en cualquier servidor y no añade nada que mantener. Un
  despliegue de una empresa con veinte personas no necesita más, y pedirle un
  broker y dos procesos extra es pedirle que administre infraestructura para
  ejecutar un comando cada cinco minutos.
- **Celery con Redis**, que es lo que quiere quien ya tiene varios servidores,
  quiere ver los trabajos, reintentarlos y no depender de la crontab de una
  máquina concreta.

`SCHEDULER` elige. La lógica es exactamente la misma en los dos casos: las
tareas de abajo no hacen el trabajo, llaman a la misma función que llama el
comando de gestión. Dos formas de disparar, una sola implementación --- si
divergieran, un despliegue tendría un producto distinto del otro.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("opentimetrack")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_configure.connect
def register_periodic_jobs(sender, **kwargs):
    """Lo que celery-beat repite, y cada cuánto.

    Solo se registra si el despliegue eligió Celery. Con `SCHEDULER=cron` el
    worker puede seguir en pie para otras cosas, pero beat no debe programar
    nada: dos programadores lanzando el mismo trabajo es la vía rápida a
    ejecutarlo dos veces.
    """
    from django.conf import settings

    if settings.SCHEDULER != "celery":
        return

    sender.add_periodic_task(
        crontab(minute=f"*/{settings.REMINDER_EVERY_MINUTES}"),
        send_punch_reminders.s(),
        name="recordatorios de fichaje",
    )
    sender.add_periodic_task(
        crontab(hour=3, minute=30),
        purge_security_metadata.s(),
        name="purga de metadatos de seguridad",
    )
    # A las cuatro y no a las tres y media: dos purgas a la vez sobre la misma
    # base no se estorban, pero repartirlas deja los registros legibles cuando
    # una tarda de más.
    sender.add_periodic_task(
        crontab(hour=4, minute=0),
        flush_expired_tokens.s(),
        name="purga de testigos caducados",
    )
    # La última, y a su hora: es la que borra registro de jornada, así que si una
    # noche algo va mal conviene que las otras ya hayan pasado y se lea en el
    # registro cuál fue.
    sender.add_periodic_task(
        crontab(hour=4, minute=30),
        purge_expired_records.s(),
        name="purga del registro que cumplió su plazo",
    )


@app.task(name="punches.send_reminders")
def send_punch_reminders() -> int:
    """Los recordatorios que tocan ahora. Idempotente: `PunchReminder` impide
    que ejecutarla dos veces avise dos veces."""
    from django.core.management import call_command

    return call_command("send_punch_reminders")


@app.task(name="users.flush_expired_tokens")
def flush_expired_tokens() -> None:
    """Tira los testigos de sesión que ya caducaron.

    Faltaba, y crecía sin techo. La rotación está activada, así que cada
    renovación ---una cada cuarto de hora por persona que trabaja--- deja un
    testigo registrado y otro en la lista negra. En la base de desarrollo eran ya
    **3.322 registrados, 1.769 de ellos caducados**, el más antiguo de dos semanas
    atrás; en una empresa de doscientas personas son del orden de dos millones de
    filas al año.

    Y no son filas cualesquiera: cada una dice **de quién** era la sesión y cuándo
    empezó. Guardar eso sin plazo es lo mismo que ya razona
    `purge_security_metadata` para los metadatos de red --- conservar un dato
    porque algún día pueda ser útil no es una base (art. 5.1.e).

    `flushexpiredtokens` lo trae simplejwt hecho: solo faltaba llamarlo. No toca
    los vigentes, así que no echa a nadie de su sesión.
    """
    from django.core.management import call_command

    call_command("flushexpiredtokens")


@app.task(name="punches.purge_security_metadata")
def purge_security_metadata() -> int:
    """IP y dispositivo de los fichajes que ya cumplieron su plazo."""
    from django.core.management import call_command

    return call_command("purge_security_metadata")


@app.task(name="punches.purge_expired_records")
def purge_expired_records() -> int:
    """Los fichajes que pasaron el plazo de conservación de su empresa.

    La única tarea del producto que borra registro de jornada, y por eso la única
    con un suelo escrito en el código: nunca por debajo de los cuatro años del
    art. 34.9 ET, sea lo que sea lo que diga la fila de la empresa.

    Idempotente: la segunda pasada del mismo día no encuentra nada, y no deja
    asiento cuando no borra.
    """
    from django.core.management import call_command

    return call_command("purge_expired_records")
