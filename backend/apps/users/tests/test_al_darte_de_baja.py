"""Qué pasa con lo tuyo cuando te dan de baja.

Fijado porque no estaba escrito en ninguna parte y el manual decía otra cosa
---«aunque tu sesión siga abierta, el fichaje se rechaza», que sugiere un aviso
sobre la baja--- cuando lo que ocurre es que **la autenticación entera deja de
valer**: 401 en la siguiente petición, sea cual sea.

La diferencia importa por dos motivos. Uno, lo que ve la persona: no un mensaje
que explica su situación, sino la pantalla de entrada. Y dos, `register_punch`
tiene su propio rechazo con código ---`employee_inactive`--- que por esta vía
**no se alcanza nunca**: solo lo ve un fichaje delegado, donde quien autentica es
la aplicación y no la persona.

Lo que aquí se fija es el comportamiento actual, para que cambiarlo sea una
decisión y no un descuido. La pregunta de si debería conservar el acceso a su
propio registro está anotada en el cuaderno; es de producto, no de código.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def gente(company):
    with tenant_context(company.id):
        yield {
            "rosa": User.objects.create_user(
                email="rosa@example.com", password=PASSWORD, tenant=company, first_name="Rosa"
            ),
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.ADMIN,
            ),
        }


@pytest.mark.django_db
def test_la_sesion_deja_de_valer_entera_no_solo_el_fichaje(company, gente):
    rosa, jefa = gente["rosa"], gente["jefa"]
    with tenant_context(company.id):
        register_punch(employee=rosa, company=company)

    # Con testigo de verdad y no con `force_authenticate`: ese salta la capa de
    # autenticación, que es **justo la que rechaza** a quien está de baja. Con él
    # la petición llega a `register_punch` y sale un 409 `employee_inactive` que
    # por la vía real nadie ve nunca.
    def como(persona):
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(persona).access_token}"
        )
        return cliente

    suya = como(rosa)
    assert suya.get("/api/punches/").status_code == 200

    panel = APIClient()
    panel.force_authenticate(user=jefa)
    assert panel.delete(f"/api/employees/{rosa.id}/").status_code in (200, 204)

    rosa.refresh_from_db()
    assert rosa.is_active is False

    # Y a partir de aquí, todo. No solo fichar.
    # El mismo testigo de antes, que no ha caducado.
    assert suya.post("/api/punches/", {}, format="json").status_code == 401
    despues = suya
    assert despues.get("/api/punches/").status_code == 401
    assert despues.get("/api/absences/").status_code == 401


@pytest.mark.django_db
def test_sus_fichajes_se_conservan(company, gente):
    """La baja no borra: es la promesa del art. 34.9 y del propio producto."""
    from apps.punches.models import Punch

    rosa, jefa = gente["rosa"], gente["jefa"]
    with tenant_context(company.id):
        register_punch(employee=rosa, company=company)
        antes = Punch.objects.filter(employee=rosa).count()

    panel = APIClient()
    panel.force_authenticate(user=jefa)
    panel.delete(f"/api/employees/{rosa.id}/")

    with tenant_context(company.id):
        assert Punch.objects.filter(employee=rosa).count() == antes

    # Y siguen saliendo en el informe que la empresa entrega.
    informe = panel.get(
        f"/api/reports/working-time/?employee={rosa.id}"
        "&date_from=2026-01-01&date_to=2026-12-31&format=csv"
    )
    assert informe.status_code == 200
