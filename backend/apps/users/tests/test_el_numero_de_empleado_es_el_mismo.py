"""«EMP-9» y «emp-9» son la misma persona, y ahora también al darla de alta.

El resto del producto ya los trataba como el mismo: así los busca `_resolve` en
la puerta de integración ---`employee_id__iexact`--- y así los busca el fichaje
delegado, que además **rechaza la referencia por ambigua** si encuentra dos.

La puerta de personas comparaba exacto, así que dejaba crear las dos. Medido con
las dos creadas:

    _resolve(«EMP-9»)          -> una de ellas, la primera, sin decir que hay otra
    _resolve(«emp-9»)          -> la misma
    resolve_employee(«EMP-9»)  -> «la referencia coincide con más de una persona»

O sea: el fichaje delegado se plantaba para las dos, y la puerta de integración
contestaba con una elegida al azar. El espacio ya se normalizaba ---« EMP-9 » sí
chocaba--- y la caja no: la misma asimetría que los ceros de la vuelta anterior.

La mitad de este fichero es lo que **no** puede romperse: numerar es opcional,
varias personas sin número no chocan entre sí, y quien conserva el suyo al
editarse tiene que poder guardar.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
VARIANTES = ["EMP-9", "emp-9", "Emp-9", " emp-9 "]


@pytest.fixture
def api(db):
    t = Tenant.objects.create(name="Numero SL", tax_id="B78787878", time_zone="Europe/Madrid")
    with tenant_context(t.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=t,
            first_name="Je",
            last_name="Fa",
            role=Role.ADMIN,
        )
        cliente = APIClient()
        cliente.force_authenticate(user=jefa)
        cliente.post(
            "/api/employees/",
            {
                "email": "primera@example.com",
                "first_name": "Pri",
                "last_name": "Mera",
                "employee_id": "EMP-9",
            },
            format="json",
        )
        yield cliente, t


@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.django_db
def test_no_se_puede_dar_de_alta_el_mismo_numero_con_otra_caja(api, variante):
    cliente, t = api
    with tenant_context(t.id):
        r = cliente.post(
            "/api/employees/",
            {
                "email": f"otra{abs(hash(variante)) % 999}@example.com",
                "first_name": "Otra",
                "last_name": "Vez",
                "employee_id": variante,
            },
            format="json",
        )

    assert r.status_code == 400, (
        f"«{variante}» es el mismo número que «EMP-9» para todo lo que busca "
        "personas, y aquí se dejó crear otra"
    )
    assert "Pri Mera" in str(r.json()), f"y el error tiene que decir quién lo usa: {r.json()}"


@pytest.mark.django_db
def test_un_numero_distinto_sigue_valiendo(api):
    """El contraste: no vaya a ser que ahora choque con todo."""
    cliente, t = api
    with tenant_context(t.id):
        r = cliente.post(
            "/api/employees/",
            {
                "email": "otra@example.com",
                "first_name": "Otra",
                "last_name": "Vez",
                "employee_id": "EMP-10",
            },
            format="json",
        )

    assert r.status_code == 201, r.json()


@pytest.mark.django_db
def test_no_numerar_sigue_siendo_normal(api):
    """Una empresa puede no numerar a nadie, y dos sin número no chocan."""
    cliente, t = api
    with tenant_context(t.id):
        for correo in ["sin1@example.com", "sin2@example.com"]:
            r = cliente.post(
                "/api/employees/",
                {"email": correo, "first_name": "Sin", "last_name": "Numero"},
                format="json",
            )
            assert r.status_code == 201, r.json()


@pytest.mark.django_db
def test_quien_conserva_su_numero_puede_editarse(api):
    """El contraste que se rompe solo: al editar, el número choca consigo mismo
    si la comprobación no se excluye a sí misma."""
    cliente, t = api
    with tenant_context(t.id):
        quien = User.objects.get(email="primera@example.com")
        r = cliente.patch(
            f"/api/employees/{quien.id}/",
            {"first_name": "Cambiada", "employee_id": "EMP-9"},
            format="json",
        )

    assert r.status_code == 200, r.json()


@pytest.mark.django_db
def test_y_lo_que_busca_personas_encuentra_una_sola(api):
    """Lo que estaba en juego: que las dos formas de resolver una referencia
    lleguen a la misma persona, y a una sola."""
    from apps.punches.delegated import resolve_employee
    from apps.tenants.people_api import _resolve

    cliente, t = api
    with tenant_context(t.id):
        # Se intenta crear la variante; el alta la rechaza, así que queda una.
        cliente.post(
            "/api/employees/",
            {
                "email": "otra@example.com",
                "first_name": "Otra",
                "last_name": "Vez",
                "employee_id": "emp-9",
            },
            format="json",
        )
        for referencia in VARIANTES:
            quien = _resolve(referencia, t)
            assert quien is not None and quien.email == "primera@example.com", referencia
        assert resolve_employee("emp-9", t).email == "primera@example.com"
