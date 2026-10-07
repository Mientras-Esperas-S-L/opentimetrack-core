"""El trabajo de los recordatorios no llena el log de nada.

Corre cada cinco minutos. Escribía «0 reminders sent» en cada vuelta: 288 líneas
al día, y como WARNING bajo Celery, que pasa la salida estándar de un trabajo a su
log con ese nivel. Una línea que sale siempre no se lee, y entre ellas se pierde la
que importa.
"""

from __future__ import annotations

import logging
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_sin_recordatorios_que_mandar_el_comando_no_dice_nada(caplog):
    salida = StringIO()
    with caplog.at_level(logging.INFO):
        call_command("send_punch_reminders", stdout=salida)

    assert salida.getvalue() == ""
    assert not [r for r in caplog.records if r.levelno >= logging.INFO]


def test_cuando_manda_alguno_lo_cuenta_en_el_log(caplog):
    from apps.tenants.models import Tenant

    Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    with (
        caplog.at_level(logging.INFO),
        mock.patch(
            "apps.punches.management.commands.send_punch_reminders.send_reminders",
            return_value=2,
        ),
    ):
        call_command("send_punch_reminders", stdout=StringIO())

    assert [r.getMessage() for r in caplog.records if r.levelno == logging.INFO] == [
        "2 reminders sent"
    ]


def test_con_mas_detalle_lo_escribe_por_empresa():
    salida = StringIO()
    call_command("send_punch_reminders", stdout=salida, verbosity=2)
    assert "0 reminders sent" in salida.getvalue()
