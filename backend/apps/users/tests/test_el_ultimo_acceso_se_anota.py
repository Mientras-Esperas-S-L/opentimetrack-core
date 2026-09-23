"""Entrar deja constancia de cuándo, y eso invalida el enlace de contraseña anterior.

`last_login` no se guardaba nunca: `UPDATE_LAST_LOGIN` de simplejwt solo actúa en
sus propias vistas, y la entrada de este producto no usa ninguna. Medido en devel
el 23/09/2026: una cuenta recién entrada seguía con el campo vacío, y la consola
de Instalación diría «No ha entrado nunca» de todo el mundo.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationScope, Tenant
from apps.users.models import Role, User
from apps.users.passwords import token_generator
from apps.users.serializers import issue_tokens

pytestmark = pytest.mark.django_db

CLAVE = "Una-clave-larga-de-verdad"


@pytest.fixture
def jefa():
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    with tenant_context(empresa.id):
        return User.objects.create_user(
            email="jefa@acme.test", password=CLAVE, tenant=empresa, role=Role.ADMIN
        )


def entrar():
    return APIClient().post(
        "/api/auth/token/", {"email": "jefa@acme.test", "password": CLAVE}, format="json"
    )


def test_entrar_anota_cuando(jefa):
    assert jefa.last_login is None
    assert entrar().status_code == 200
    jefa.refresh_from_db()
    assert jefa.last_login is not None


def test_entrar_mata_el_enlace_de_contrasena_de_antes(jefa):
    """Lo que el generador de enlaces ya daba por hecho: firma con `last_login`
    para que el enlace deje de valer cuando la persona entra."""
    enlace = token_generator.make_token(jefa)
    assert token_generator.check_token(jefa, enlace), "el control: antes vale"

    entrar()
    jefa.refresh_from_db()
    assert not token_generator.check_token(jefa, enlace)


def test_una_sesion_pedida_por_una_aplicacion_no_cuenta_como_entrar(jefa):
    with tenant_context(jefa.tenant_id):
        app = Application.objects.create(
            tenant=jefa.tenant, name="GreenCity", scopes=[s.value for s in ApplicationScope]
        )
    issue_tokens(jefa, acting_application=app)
    jefa.refresh_from_db()
    assert jefa.last_login is None
