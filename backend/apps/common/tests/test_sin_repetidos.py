"""Un repetido es un 400 con su motivo, no un 500.

Pulsando «Guardar» dos veces con el mismo nombre en departamentos, centros,
turnos, festivos y aplicaciones, la base saltaba con su `IntegrityError` y la
persona veía un error 500 (08/10/2026). Y lo mismo al renombrar uno con el
nombre de otro.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

ALTAS = [
    ("/api/departments/", {"name": "Riego"}, "name"),
    ("/api/workplaces/", {"name": "Vivero"}, "name"),
    (
        "/api/shift-patterns/",
        {"name": "Mañana", "segments": [{"start": "08:00", "end": "15:00"}]},
        "name",
    ),
    ("/api/holidays/", {"day": "2031-03-19", "name": "San José"}, "day"),
    ("/api/applications/", {"name": "Nóminas", "scopes": ["read:people"]}, "name"),
]


@pytest.fixture
def admin(db):
    empresa = Tenant.objects.create(name="ACME", tax_id="B11111111", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        return User.objects.create_user(
            email="jefa@ejemplo.test",
            password="x" * 14,
            tenant=empresa,
            first_name="Ana",
            role=Role.ADMIN,
        )


def cliente(usuario):
    api = APIClient()
    api.force_authenticate(user=usuario)
    return api


@pytest.mark.parametrize(("ruta", "datos", "campo"), ALTAS)
def test_dar_de_alta_un_repetido_dice_por_que(admin, ruta, datos, campo):
    api = cliente(admin)
    assert api.post(ruta, datos, format="json").status_code == 201

    otra = api.post(ruta, datos, format="json")

    assert otra.status_code == 400
    assert campo in otra.json()["error"]["details"]


@pytest.mark.parametrize(("ruta", "datos", "campo"), [a for a in ALTAS if a[2] == "name"])
def test_renombrar_con_el_nombre_de_otro_dice_por_que(admin, ruta, datos, campo):
    api = cliente(admin)
    api.post(ruta, datos, format="json")
    segundo = api.post(ruta, {**datos, "name": "Otro nombre"}, format="json").json()

    respuesta = api.patch(f"{ruta}{segundo['id']}/", {"name": datos["name"]}, format="json")

    assert respuesta.status_code == 400
    assert campo in respuesta.json()["error"]["details"]


def test_cambiar_otra_cosa_sin_tocar_el_nombre_no_choca_consigo_mismo(admin):
    api = cliente(admin)
    creado = api.post("/api/departments/", {"name": "Riego"}, format="json").json()

    respuesta = api.patch(
        f"/api/departments/{creado['id']}/", {"description": "Lo de las bocas"}, format="json"
    )

    assert respuesta.status_code == 200
