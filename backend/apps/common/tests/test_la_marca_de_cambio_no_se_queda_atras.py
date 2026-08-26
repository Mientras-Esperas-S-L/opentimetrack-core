"""`updated_at` tiene que moverse cada vez que la fila se mueve.

`auto_now` promete exactamente eso, y `update_fields` lo rompe: Django pone la
marca en la instancia y no la escribe, porque no está en la lista. El código
parece correcto ---`save(update_fields=["is_active"])` no tiene nada raro--- y la
fila queda cambiada con la marca vieja.

Aquí eso decide si una integración funciona. `/api/app/people/?since=` avanza por
`updated_at`: si una baja no la mueve, el conector nunca se entera. Sigue
teniendo por activa a una persona que ya no lo está, la mantiene en sus
cuadrantes y le manda fichajes delegados que OTT rechaza con `employee_inactive`
sin que nadie mire esos errores. Y una reconciliación ---comparar su padrón
contra el de OTT por incremental--- no ve ninguna diferencia y no lo corrige.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
RAIZ = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.mark.django_db
def test_guardar_unos_pocos_campos_mueve_la_marca(company):
    with tenant_context(company.id):
        rosa = User.objects.create_user(
            email="rosa@acme.test", password=PASSWORD, tenant=company, employee_id="EMP-0042"
        )
        antes = rosa.updated_at

        rosa.is_active = False
        rosa.save(update_fields=["is_active"])
        rosa.refresh_from_db()

    assert rosa.updated_at > antes


@pytest.mark.django_db
def test_una_baja_desde_el_panel_la_ve_la_lectura_incremental(company):
    """El escenario completo, por la puerta por la que entra el conector."""
    with tenant_context(company.id):
        admin = User.objects.create_user(
            email="jefa@acme.test", password=PASSWORD, tenant=company, role=Role.ADMIN
        )
        rosa = User.objects.create_user(
            email="rosa@acme.test", password=PASSWORD, tenant=company, employee_id="EMP-0042"
        )
        application = Application.objects.create(
            tenant=company,
            name="Geosian",
            scopes=[str(ApplicationScope.READ_PEOPLE), str(ApplicationScope.WRITE_PEOPLE)],
        )
        _credential, secret = ApplicationCredential.issue(application)

    conector = APIClient()
    conector.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")

    def leer():
        respuesta = conector.get("/api/app/people/")
        assert respuesta.status_code == 200
        return {p["employee_id"]: p for p in respuesta.json()["people"]}

    # El conector se pone al día y la ve activa.
    assert leer()["EMP-0042"]["is_active"] is True
    with tenant_context(company.id):
        antes = User.objects.get(pk=rosa.pk).updated_at

    # Y ahora la administración da de baja a Rosa desde el panel.
    panel = APIClient()
    panel.force_authenticate(user=admin)
    baja = panel.delete(f"/api/employees/{rosa.id}/")
    assert baja.status_code in (200, 204)

    assert leer()["EMP-0042"]["is_active"] is False

    # **La marca tiene que haberse movido**, y se comprueba en la fila.
    # Hacerlo con `?since=` no valdría: el cursor filtra con `>=` para no perder
    # dos cambios del mismo instante, así que reenvía la última tanda entera y
    # Rosa aparecería igual sin que su marca cambiara --- escrito así, la prueba
    # pasaba con el fallo delante.
    with tenant_context(company.id):
        despues = User.objects.get(pk=rosa.pk).updated_at
    assert despues > antes, (
        "la baja no movió `updated_at`: una lectura incremental que ya hubiera "
        "pasado de esa marca no la vería nunca."
    )


def test_ningun_save_se_deja_la_marca_por_el_camino():
    """Sonda: la raíz lo arregla, pero alguien puede volver a saltárselo.

    Un `save(update_fields=…)` sobre un modelo del dominio pasa ahora por
    `BaseModel.save`, que añade la marca. Lo que esta sonda vigila es que ese
    método siga estando: si alguien lo quita, los siete sitios que lo omiten
    vuelven a fallar de golpe y en silencio.
    """
    fuente = (RAIZ / "common" / "models.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    base = next(n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef) and n.name == "BaseModel")
    metodos = [n.name for n in base.body if isinstance(n, ast.FunctionDef)]
    assert "save" in metodos, (
        "BaseModel ya no añade `updated_at` a `update_fields`. Sin eso, "
        "`/api/app/people/?since=` deja de ver las bajas hechas desde el panel."
    )
