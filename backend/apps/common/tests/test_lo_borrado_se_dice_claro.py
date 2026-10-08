"""Elegir algo que otra persona acaba de borrar se dice en llano.

Con la ficha de una persona abierta, otra borra el departamento que tenía
elegido. Al guardar, DRF contestaba «Clave primaria "…" inválida - objeto no
existe.», con el identificador interno dentro. Lo que hace falta saber es que eso
ya no está y que hay que volver a elegir.
"""

from __future__ import annotations

import pytest
from django.utils import translation
from rest_framework import exceptions
from rest_framework.test import APIClient, APIRequestFactory

from apps.common.exceptions import api_exception_handler
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


def _manejar(exc):
    contexto = {"view": None, "request": APIRequestFactory().get("/")}
    # En inglés fijo: otra prueba puede dejar activo otro idioma.
    with translation.override("en"):
        return api_exception_handler(exc, contexto).data["error"]


def _no_existe(pk):
    return exceptions.ErrorDetail(
        f'Invalid pk "{pk}" - object does not exist.', code="does_not_exist"
    )


def test_el_identificador_no_sale_en_el_mensaje():
    pk = "0b7e6a0c-1111-2222-3333-444455556666"
    error = _manejar(exceptions.ValidationError({"department": [_no_existe(pk)]}))

    dicho = " ".join(error["details"]["department"])
    assert pk not in dicho, dicho
    assert "no longer exists" in dicho, dicho


def test_tambien_dentro_de_una_lista_o_de_algo_anidado():
    error = _manejar(exceptions.ValidationError({"tramos": [{"workplace": [_no_existe(7)]}]}))

    assert "7" not in str(error["details"]), error["details"]


def test_los_demas_errores_de_campo_no_se_tocan():
    """El contraste: solo se cambia el «no existe»."""
    error = _manejar(exceptions.ValidationError({"name": ["Ya hay uno con ese nombre."]}))

    assert error["details"]["name"] == ["Ya hay uno con ese nombre."]


@pytest.mark.django_db
def test_y_por_la_api_de_verdad():
    empresa = Tenant.objects.create(
        name="Borrado SL", tax_id="B41414141", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        admin = User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            role=Role.ADMIN,
        )
        pepe = User.objects.create_user(
            email="pepe@example.com", password=PASSWORD, tenant=empresa, first_name="Pepe"
        )
        brigada = Department.objects.create(tenant=empresa, name="Brigada")
        pk = brigada.pk
        brigada.delete()

        api = APIClient()
        api.force_authenticate(user=admin)
        r = api.patch(f"/api/employees/{pepe.pk}/", {"department": str(pk)}, format="json")

    assert r.status_code == 400, r.content
    dicho = " ".join(r.json()["error"]["details"]["department"])
    assert str(pk) not in dicho, dicho
