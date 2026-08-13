"""Celery, para quien lo quiera. Nadie está obligado.

El producto tiene trabajos que se repiten --- recordar un fichaje, purgar
metadatos de seguridad cuando cumplen su plazo --- y hay dos maneras honradas de
repetirlos:

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


@app.task(name="punches.send_reminders")
def send_punch_reminders() -> int:
    """Los recordatorios que tocan ahora. Idempotente: `PunchReminder` impide
    que ejecutarla dos veces avise dos veces."""
    from django.core.management import call_command

    return call_command("send_punch_reminders")


@app.task(name="punches.purge_security_metadata")
def purge_security_metadata() -> int:
    """IP y dispositivo de los fichajes que ya cumplieron su plazo."""
    from django.core.management import call_command

    return call_command("purge_security_metadata")
