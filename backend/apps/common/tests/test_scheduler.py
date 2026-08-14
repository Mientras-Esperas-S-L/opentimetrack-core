"""Cron o Celery, a elección de quien instala.

Lo que importa comprobar no es Celery —eso lo prueban ellos— sino que las dos
vías **hacen lo mismo**: que la tarea no reimplemente el trabajo sino que llame
al mismo comando, y que con `SCHEDULER=cron` beat no programe nada, porque dos
programadores lanzando el mismo trabajo lo ejecutan dos veces.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.management import call_command


def test_the_setting_only_admits_the_two_it_documents():
    """Un `SCHEDULER=cellery` mal escrito no puede acabar en un despliegue sin
    recordatorios y sin que nadie se entere. Falla al arrancar, no en silencio.

    Recarga el módulo de verdad en vez de repetir aquí la comprobación: un test
    que reimplementa lo que comprueba pasa aunque borres el código.
    """
    import importlib
    import os

    from django.core.exceptions import ImproperlyConfigured

    base = importlib.import_module("config.settings.base")
    try:
        with (
            patch.dict(os.environ, {"SCHEDULER": "cellery"}),
            pytest.raises(ImproperlyConfigured),
        ):
            importlib.reload(base)
    finally:
        # La recarga murió a medias; se deja el módulo entero otra vez.
        with patch.dict(os.environ, {"SCHEDULER": "cron"}):
            importlib.reload(base)


def test_the_celery_task_calls_the_same_command_as_cron():
    """Una sola implementación. Si la tarea hiciera el trabajo por su cuenta, un
    despliegue con Celery tendría un producto distinto del de al lado."""
    from config.celery import send_punch_reminders

    with patch("django.core.management.call_command", return_value=3) as called:
        assert send_punch_reminders() == 3

    assert called.call_args.args == ("send_punch_reminders",)


def test_with_cron_beat_schedules_nothing(settings):
    settings.SCHEDULER = "cron"
    from config.celery import register_periodic_jobs

    class Sender:
        def __init__(self):
            self.scheduled = []

        def add_periodic_task(self, *args, **kwargs):
            self.scheduled.append(kwargs.get("name"))

    sender = Sender()
    register_periodic_jobs(sender)
    assert sender.scheduled == []


def test_with_celery_beat_schedules_both_jobs(settings):
    settings.SCHEDULER = "celery"
    settings.REMINDER_EVERY_MINUTES = 5
    from config.celery import register_periodic_jobs

    class Sender:
        def __init__(self):
            self.scheduled = []

        def add_periodic_task(self, *args, **kwargs):
            self.scheduled.append(kwargs.get("name"))

    sender = Sender()
    register_periodic_jobs(sender)
    assert sender.scheduled == [
        "recordatorios de fichaje",
        "purga de metadatos de seguridad",
    ]


@pytest.mark.django_db
def test_the_management_command_runs_with_no_companies_at_all():
    """La vía de cron, de punta a punta. Sin empresas no hay nada que avisar, y
    eso no es un error: es la primera noche de un despliegue nuevo.

    Con la aserción escrita, que antes no la había: «no reventar» también lo
    cumple un comando que se traga una excepción, y lo que hay que fijar es que
    tampoco mande nada.
    """
    from django.core import mail

    mail.outbox.clear()
    call_command("send_punch_reminders")
    assert mail.outbox == [], "avisó a alguien en una instalación sin empresas"
