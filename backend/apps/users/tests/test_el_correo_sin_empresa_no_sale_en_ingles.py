"""El correo a una cuenta sin empresa salía en inglés.

El idioma salía de la persona o de su empresa, y una cuenta de la instalación no
tiene ninguna de las dos cosas: quedaba vacío, `translation.override(None)` apaga
las traducciones y lo que llega es el texto original del código. Medido en
producción el 23/09/2026: «Reset your password at the platform».
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import translation
from rest_framework.test import APIClient

from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def instalacion():
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
        first_name="Plata",
    )


def test_la_recuperacion_llega_en_el_idioma_del_navegador(instalacion):
    APIClient().post(
        "/api/auth/password-reset/",
        {"email": "plataforma@ejemplo.test"},
        format="json",
        HTTP_ACCEPT_LANGUAGE="ca",
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject.startswith("Restablir la teva contrasenya")


@override_settings(LANGUAGE_CODE="es")
def test_sin_ningun_idioma_activo_llega_en_el_de_la_instalacion(instalacion):
    """Lo que pasa desde un proceso sin petición detrás, como el cron."""
    from apps.users.passwords import send_account_email

    with translation.override(None):
        send_account_email(instalacion, base_url="https://ott.example")
    asunto = mail.outbox[0].subject
    assert asunto.startswith("Restablecer tu contraseña"), asunto
    assert "Reset" not in asunto
