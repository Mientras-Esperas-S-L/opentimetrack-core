"""Corregir, reactivar y mandar el enlace a una cuenta de la instalación.

Se podía añadir una, darle contraseña nueva y desactivarla. No se podía corregir
su nombre ni su correo; reactivarla solo pasaba a escondidas, al darle contraseña
nueva; y el enlace por correo no existía para estas cuentas.
"""

from __future__ import annotations

import smtplib
from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import PlatformAction, PlatformAuditEntry
from apps.tenants.models import Tenant
from apps.users.models import User

pytestmark = pytest.mark.django_db


def _instalacion(correo, **extra):
    return User.objects.create_user(
        email=correo, password="X" * 14, tenant=None, is_superuser=True, is_staff=True, **extra
    )


@pytest.fixture
def yo():
    return _instalacion("yo@ejemplo.test", first_name="Yo")


@pytest.fixture
def otra():
    return _instalacion("otra@ejemplo.test", first_name="Otra", last_name="Cuenta")


def cliente(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def cambiar(api, cuenta, **datos):
    return api.patch(f"/api/platform/admins/{cuenta.id}/", datos, format="json")


def test_corrige_el_nombre_y_el_correo_y_lo_anota(yo, otra, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cambiar(cliente(yo), otra, first_name="Otra bien", email="Nueva@Ejemplo.test")
    assert respuesta.status_code == 200, respuesta.data
    otra.refresh_from_db()
    assert (otra.first_name, otra.email) == ("Otra bien", "nueva@ejemplo.test")
    entrada = PlatformAuditEntry.objects.get()
    assert entrada.action == PlatformAction.ADMIN_CHANGED
    assert entrada.changes["email"] == ["otra@ejemplo.test", "nueva@ejemplo.test"]


def test_no_deja_poner_un_correo_que_la_dejaria_sin_entrar(yo, otra):
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    User.objects.create_user(email="jefa@acme.test", password="X" * 14, tenant=empresa)
    for ocupado in ("yo@ejemplo.test", "jefa@acme.test"):
        respuesta = cambiar(cliente(yo), otra, email=ocupado)
        assert respuesta.status_code == 400, ocupado
    otra.refresh_from_db()
    assert otra.email == "otra@ejemplo.test"


def test_dejar_el_mismo_correo_no_choca_consigo_misma(yo, otra):
    assert cambiar(cliente(yo), otra, email="OTRA@ejemplo.test").status_code == 200


def test_reactivar_es_una_accion_y_queda_anotada(yo, otra, django_capture_on_commit_callbacks):
    otra.is_active = False
    otra.save(update_fields=["is_active"])
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cambiar(cliente(yo), otra, is_active=True)
    assert respuesta.status_code == 200 and respuesta.data["is_active"] is True
    assert PlatformAuditEntry.objects.get().action == PlatformAction.ADMIN_REACTIVATED


def test_desactivar_no_va_por_aqui(yo, otra):
    """Desactivar tiene sus reglas ---nunca la propia ni la última--- y va por DELETE."""
    assert cambiar(cliente(yo), otra, is_active=False).status_code == 400
    otra.refresh_from_db()
    assert otra.is_active


def test_el_enlace_va_a_su_correo(yo, otra, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cliente(yo).post(f"/api/platform/admins/{otra.id}/link/")
    assert respuesta.status_code == 200
    assert respuesta.data == {"sent_to": "otra@ejemplo.test"}
    assert mail.outbox[0].to == ["otra@ejemplo.test"]
    assert "set-password" not in str(respuesta.data)
    assert PlatformAuditEntry.objects.get().action == PlatformAction.ADMIN_LINK_SENT


def test_a_una_desactivada_no_se_le_manda(yo, otra):
    otra.is_active = False
    otra.save(update_fields=["is_active"])
    assert cliente(yo).post(f"/api/platform/admins/{otra.id}/link/").status_code == 400
    assert mail.outbox == []


def test_si_el_rele_rechaza_la_direccion_lo_dice(yo, otra):
    rechazo = smtplib.SMTPRecipientsRefused({"otra@ejemplo.test": (554, b"Access denied")})
    with mock.patch("apps.tenants.platform_views.send_account_email", side_effect=rechazo):
        respuesta = cliente(yo).post(f"/api/platform/admins/{otra.id}/link/")
    assert respuesta.status_code == 502
    assert "otra@ejemplo.test" in respuesta.data["detail"]
    assert PlatformAuditEntry.objects.count() == 0


def test_una_de_empresa_no_toca_las_de_la_instalacion(otra):
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    jefa = User.objects.create_user(
        email="jefa@acme.test", password="X" * 14, tenant=empresa, is_superuser=True
    )
    api = cliente(jefa)
    assert cambiar(api, otra, first_name="Hackeada").status_code == 403
    assert api.post(f"/api/platform/admins/{otra.id}/link/").status_code == 403
