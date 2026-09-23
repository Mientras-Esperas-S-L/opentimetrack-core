"""Quién administra cada empresa, y mandarle el enlace para poner contraseña.

«El responsable no puede entrar» es la llamada de soporte más habitual, y hasta el
23/09/2026 la instalación no tenía forma de atenderla sin abrir un shell.

Lo que se fija aquí, sobre todo, es lo que **no** hace: no enseña a nadie más que
a quien administra, y el enlace va al correo de esa persona y no a la pantalla.
"""

from __future__ import annotations

from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog, PlatformAction, PlatformAuditEntry
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def plataforma():
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )


@pytest.fixture
def mundo():
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@acme.test",
            password="X" * 14,
            tenant=empresa,
            role=Role.ADMIN,
            first_name="Jefa",
            last_name="Acme",
        )
        curro = User.objects.create_user(
            email="curro@acme.test", password="X" * 14, tenant=empresa, role=Role.EMPLOYEE
        )
    return {"empresa": empresa, "jefa": jefa, "curro": curro}


def cliente(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def url(empresa, persona=None):
    base = f"/api/platform/companies/{empresa.id}/admins/"
    return f"{base}{persona.id}/link/" if persona else base


def test_enseña_solo_a_quien_administra(plataforma, mundo):
    respuesta = cliente(plataforma).get(url(mundo["empresa"]))
    assert respuesta.status_code == 200
    correos = [a["email"] for a in respuesta.data["admins"]]
    assert correos == ["jefa@acme.test"]
    assert "curro@acme.test" not in str(respuesta.data)


def test_el_enlace_va_al_correo_y_no_a_la_pantalla(
    plataforma, mundo, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cliente(plataforma).post(url(mundo["empresa"], mundo["jefa"]))

    assert respuesta.status_code == 200
    assert respuesta.data == {"sent_to": "jefa@acme.test"}
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["jefa@acme.test"]
    assert "/set-password/" in mail.outbox[0].body
    assert "set-password" not in str(respuesta.data)

    assert PlatformAuditEntry.objects.get().action == PlatformAction.COMPANY_ADMIN_LINK_SENT
    en_la_empresa = AuditLog.objects.get(tenant=mundo["empresa"])
    assert en_la_empresa.action == AuditAction.INVITATION_SENT
    assert en_la_empresa.actor == plataforma


def test_a_quien_no_administra_no_se_le_manda(plataforma, mundo):
    respuesta = cliente(plataforma).post(url(mundo["empresa"], mundo["curro"]))
    assert respuesta.status_code == 404
    assert mail.outbox == []


@pytest.mark.parametrize("caso", ["federada", "desactivada", "empresa desactivada"])
def test_cuando_el_enlace_no_serviria_lo_dice_y_no_lo_manda(plataforma, mundo, caso):
    jefa, empresa = mundo["jefa"], mundo["empresa"]
    if caso == "federada":
        jefa.oidc_sub = "sub-de-la-jefa"
        jefa.save(update_fields=["oidc_sub"])
    elif caso == "desactivada":
        jefa.is_active = False
        jefa.save(update_fields=["is_active"])
    else:
        empresa.is_active = False
        empresa.save(update_fields=["is_active"])

    respuesta = cliente(plataforma).post(url(empresa, jefa))
    assert respuesta.status_code == 400
    assert respuesta.data["detail"]
    assert mail.outbox == []


def test_si_el_correo_no_sale_no_dice_enviado(plataforma, mundo):
    with mock.patch(
        "apps.tenants.platform_views.send_account_email", side_effect=OSError("sin relé")
    ):
        respuesta = cliente(plataforma).post(url(mundo["empresa"], mundo["jefa"]))
    assert respuesta.status_code == 502
    assert "sent_to" not in respuesta.data
    assert PlatformAuditEntry.objects.count() == 0


def test_el_administrador_de_una_empresa_no_lo_usa(mundo):
    api = cliente(mundo["jefa"])
    assert api.get(url(mundo["empresa"])).status_code == 403
    assert api.post(url(mundo["empresa"], mundo["jefa"])).status_code == 403
