"""Desactivar una cuenta o darle contraseña nueva echa a quien estuviera dentro.

Las personas de empresa ya lo hacían al darse de baja por su botón y al
recuperar la cuenta. No lo hacían:

- las cuentas de la instalación, ni al desactivarlas ni al darles contraseña
  nueva;
- la contraseña que pone la administración en la ficha de una persona;
- la baja desde la ficha (`is_active: false`) ni la de una aplicación.

Y una sesión **renovada** una sola vez no la alcanzaba nadie: la renovación
emitía un refresco nuevo sin apuntarlo entre los vivos, y `revoke_sessions` solo
mira esos.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User
from apps.users.passwords import revoke_sessions

pytestmark = pytest.mark.django_db

CLAVE = "a-sufficiently-long-password"


@pytest.fixture
def acme():
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def jefa(acme):
    with tenant_context(acme.id):
        return User.objects.create_user(
            email="jefa@acme.example", password=CLAVE, tenant=acme, role=Role.ADMIN
        )


@pytest.fixture
def ana(acme):
    with tenant_context(acme.id):
        return User.objects.create_user(
            email="ana@acme.example", password=CLAVE, tenant=acme, employee_id="EMP-1"
        )


def de_la_instalacion(correo):
    return User.objects.create_user(
        email=correo, password=CLAVE, tenant=None, is_superuser=True, is_staff=True
    )


def como(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def sesion(user) -> str:
    """Entra de verdad y devuelve el refresco."""
    respuesta = APIClient().post(
        "/api/auth/token/", {"email": user.email, "password": CLAVE}, format="json"
    )
    assert respuesta.status_code == 200, respuesta.content
    return respuesta.json()["refresh"]


def renovar(refresco):
    return APIClient().post("/api/auth/refresh/", {"refresh": refresco}, format="json")


# --------------------------------------------------- cuentas de la instalación


def test_desactivar_una_cuenta_de_la_instalacion_cierra_su_sesion():
    yo = de_la_instalacion("yo@ejemplo.test")
    otra = de_la_instalacion("otra@ejemplo.test")
    refresco = sesion(otra)

    assert como(yo).delete(f"/api/platform/admins/{otra.id}/").status_code == 204
    # Reactivada, la sesión de antes sigue sin valer.
    otra.is_active = True
    otra.save()
    assert renovar(refresco).status_code != 200


def test_la_contrasena_nueva_de_una_cuenta_de_la_instalacion_cierra_su_sesion():
    yo = de_la_instalacion("yo@ejemplo.test")
    otra = de_la_instalacion("otra@ejemplo.test")
    refresco = sesion(otra)

    assert como(yo).post(f"/api/platform/admins/{otra.id}/password/").status_code == 200
    assert renovar(refresco).status_code != 200


# ------------------------------------------------------- personas de empresa


def test_la_contrasena_que_pone_la_administracion_cierra_sus_sesiones(jefa, ana):
    refresco = sesion(ana)

    respuesta = como(jefa).patch(
        f"/api/employees/{ana.id}/", {"password": "una-nueva-bien-larga"}, format="json"
    )
    assert respuesta.status_code == 200, respuesta.content
    assert renovar(refresco).status_code != 200


def test_un_cambio_sin_contrasena_no_echa_a_nadie(jefa, ana):
    refresco = sesion(ana)
    respuesta = como(jefa).patch(f"/api/employees/{ana.id}/", {"first_name": "Ana"}, format="json")
    assert respuesta.status_code == 200, respuesta.content
    assert renovar(refresco).status_code == 200


def test_la_baja_desde_la_ficha_cierra_sus_sesiones(jefa, ana):
    refresco = sesion(ana)
    respuesta = como(jefa).patch(f"/api/employees/{ana.id}/", {"is_active": False}, format="json")
    assert respuesta.status_code == 200, respuesta.content

    ana.is_active = True
    ana.save()
    assert renovar(refresco).status_code != 200


def test_la_baja_que_manda_una_aplicacion_cierra_sus_sesiones(acme, ana):
    refresco = sesion(ana)
    with tenant_context(acme.id):
        aplicacion = Application.objects.create(
            tenant=acme, name="Gestión", scopes=[str(ApplicationScope.WRITE_PEOPLE)]
        )
        _credencial, secreto = ApplicationCredential.issue(aplicacion)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {secreto}")
    assert api.delete("/api/app/people/EMP-1/").status_code == 200

    ana.is_active = True
    ana.save()
    assert renovar(refresco).status_code != 200


# ------------------------------------------------------- la sesión renovada


def test_una_sesion_ya_renovada_tambien_se_cierra(ana):
    renovada = renovar(sesion(ana))
    assert renovada.status_code == 200
    refresco = renovada.json()["refresh"]

    revoke_sessions(ana)

    assert renovar(refresco).status_code != 200
