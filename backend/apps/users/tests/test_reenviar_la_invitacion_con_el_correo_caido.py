"""Reenviar la invitación con el correo caído dice qué pasa, y no contesta 500.

El alta ya sabía sobrevivir a un correo que no sale (`invitation_sent: false`) y
decía que la invitación se reenviase. Pero el reenvío no tenía red: con el relé
caído la excepción subía, la petición contestaba 500 sin cuerpo y la pantalla
decía «No hay conexión con el servidor».

Ahora contesta 502 con su código, no anota una invitación que no salió y deja
la línea en el log con la dirección tapada. Se prueba con el servidor SMTP de
verdad apuntando a un puerto cerrado, que es lo que pasa cuando el relé se cae.
"""

from __future__ import annotations

import logging
import smtplib

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

PASSWORD = "a-sufficiently-long-password"

CORREO_CAIDO = override_settings(
    EMAIL_BACKEND="apps.common.mail.SMTPBackend",
    EMAIL_HOST="127.0.0.1",
    EMAIL_PORT=1,
    EMAIL_USE_TLS=False,
    EMAIL_USE_SSL=False,
    EMAIL_TIMEOUT=2,
)


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def jefa(empresa):
    return User.objects.create_user(
        email="jefa@acme.example", password=PASSWORD, tenant=empresa, role=Role.ADMIN
    )


@pytest.fixture
def marta(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(email="marta@acme.example", tenant=empresa)


def reenviar(jefa, persona):
    cliente = APIClient()
    cliente.force_authenticate(user=jefa)
    return cliente.post(f"/api/employees/{persona.id}/invite/")


@CORREO_CAIDO
def test_con_el_correo_caido_contesta_502_con_su_codigo(
    empresa, jefa, marta, caplog, django_capture_on_commit_callbacks
):
    with caplog.at_level(logging.WARNING), django_capture_on_commit_callbacks(execute=True):
        respuesta = reenviar(jefa, marta)

    assert respuesta.status_code == 502, respuesta.content
    error = respuesta.json()["error"]
    assert error["code"] == "mail_not_sent"
    assert error["message"]

    # Ni una invitación anotada que no salió.
    assert not AuditLog.objects.filter(
        tenant=empresa, action=AuditAction.INVITATION_SENT, target_id=marta.id
    ).exists()

    lineas = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("m***@acme.example" in linea for linea in lineas), lineas
    assert not any("marta@acme.example" in linea for linea in lineas), "la dirección, tapada"


def test_una_direccion_rechazada_lo_dice_y_no_es_un_500(empresa, jefa, marta, monkeypatch):
    from django.core.mail.backends.locmem import EmailBackend

    def rechaza(self, mensajes):
        raise smtplib.SMTPRecipientsRefused({"marta@acme.example": (550, b"No such user")})

    monkeypatch.setattr(EmailBackend, "send_messages", rechaza)

    respuesta = reenviar(jefa, marta)

    assert respuesta.status_code == 502, respuesta.content
    error = respuesta.json()["error"]
    assert error["code"] == "mail_address_refused"
    assert "marta@acme.example" in error["message"]


def test_con_el_correo_bien_se_sigue_enviando(empresa, jefa, marta):
    respuesta = reenviar(jefa, marta)

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json() == {"sent_to": "marta@acme.example"}
    assert [m.to for m in mail.outbox] == [["marta@acme.example"]]
