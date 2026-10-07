"""Lo que una aplicación con `write:people` no puede hacer, aunque lo pida.

Cuatro huecos de la API de personas, todos del mismo tipo: el conector podía más
que la pantalla.

- **Deshacer una baja sin decirlo.** El `PUT` reactivaba siempre, así que un
  conector que sincroniza a diario devolvía cada mañana a quien se había dado de
  baja aquí la tarde anterior.
- **Crear administradores.** Quien tuviera el secreto del conector se daba las
  llaves de toda la empresa.
- **Ver y tocar la cuenta de soporte**, que es de la instalación.
- **Dar una baja a medias**: sin fecha de fin de contrato y sin proteger al último
  administrador, al contrario que la pantalla.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.tenants.platform_views import support_account
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def connector(company):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company,
            name="Conector de ejemplo",
            scopes=[str(ApplicationScope.READ_PEOPLE), str(ApplicationScope.WRITE_PEOPLE)],
        )
        _credential, secret = ApplicationCredential.issue(application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    return client


@pytest.fixture
def admin(company):
    return User.objects.create_user(
        email="jefa@acme.example", password=PASSWORD, tenant=company, role=Role.ADMIN
    )


def pantalla(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


ROSA = {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"}


# ------------------------------------------------- la baja que se da aquí se queda


def test_la_sincronizacion_diaria_no_deshace_una_baja_dada_aqui(connector, admin):
    connector.put("/api/app/people/EMP-0042/", ROSA, format="json")
    rosa = User.objects.get(employee_id="EMP-0042")
    assert pantalla(admin).delete(f"/api/employees/{rosa.id}/").status_code == 200

    # A la mañana siguiente el conector empuja lo mismo de siempre.
    respuesta = connector.put("/api/app/people/EMP-0042/", ROSA, format="json")

    assert respuesta.status_code == 200
    assert respuesta.json()["is_active"] is False
    rosa.refresh_from_db()
    assert rosa.is_active is False


def test_reactivar_hay_que_pedirlo(connector, admin):
    """Quien viene por temporadas vuelve, pero porque el conector lo dice."""
    connector.put("/api/app/people/EMP-0042/", ROSA, format="json")
    connector.delete("/api/app/people/EMP-0042/")

    vuelta = connector.put("/api/app/people/EMP-0042/", {**ROSA, "is_active": True}, format="json")

    assert vuelta.json()["is_active"] is True


def test_quien_llega_nueva_entra_activa(connector, admin):
    respuesta = connector.put("/api/app/people/EMP-0042/", ROSA, format="json")
    assert respuesta.status_code == 201
    assert respuesta.json()["is_active"] is True


@freeze_time("2026-10-07 10:00:00+02:00")
def test_dar_de_baja_por_el_put_es_la_misma_baja_que_el_delete(connector, admin):
    connector.put("/api/app/people/EMP-0042/", ROSA, format="json")

    respuesta = connector.put(
        "/api/app/people/EMP-0042/", {**ROSA, "is_active": False}, format="json"
    )

    assert respuesta.status_code == 200
    rosa = User.objects.get(employee_id="EMP-0042")
    assert rosa.is_active is False
    assert rosa.contract_end == date(2026, 10, 7)


# ------------------------------------------------------- no nombra administradores


@pytest.mark.parametrize("papel", [Role.ADMIN, Role.ADVISOR])
def test_no_crea_administracion_ni_asesoria(connector, admin, papel):
    respuesta = connector.put("/api/app/people/EMP-0042/", {**ROSA, "role": papel}, format="json")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "role_not_allowed"
    assert not User.objects.filter(employee_id="EMP-0042").exists()


def test_si_crea_responsables(connector, admin):
    respuesta = connector.put(
        "/api/app/people/EMP-0042/", {**ROSA, "role": Role.MANAGER}, format="json"
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["role"] == Role.MANAGER


def test_mandar_el_papel_de_quien_ya_administra_no_rompe_el_conector(connector, admin):
    """El papel solo cuenta al crear. Un conector que manda el que ya tiene cada uno
    ---administración incluida--- tiene que poder seguir actualizando."""
    respuesta = connector.put(
        f"/api/app/people/{admin.email}/",
        {"email": admin.email, "first_name": "Jefa", "role": Role.ADMIN},
        format="json",
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["role"] == Role.ADMIN


# ------------------------------------------------------- la cuenta de soporte


def test_la_cuenta_de_soporte_ni_se_lista_ni_se_alcanza(connector, admin, company):
    soporte = support_account(company)

    lista = connector.get("/api/app/people/").json()
    assert soporte.email not in {p["email"] for p in lista["people"]}
    assert lista["count"] == 1

    assert connector.get(f"/api/app/people/{soporte.email}/").status_code == 409
    assert connector.delete(f"/api/app/people/{soporte.email}/").status_code == 409
    soporte.refresh_from_db()
    assert soporte.is_active is True


# ---------------------------------------------- la baja es la misma que la pantalla


def test_el_conector_no_deja_a_la_empresa_sin_administrador(connector, admin, company):
    # La cuenta de soporte es administración sobre el papel, y no cuenta.
    support_account(company)

    respuesta = connector.delete(f"/api/app/people/{admin.email}/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "last_administrator"
    admin.refresh_from_db()
    assert admin.is_active is True


@freeze_time("2026-10-07 10:00:00+02:00")
def test_la_baja_del_conector_pone_la_fecha_de_fin(connector, admin):
    connector.put("/api/app/people/EMP-0042/", ROSA, format="json")

    connector.delete("/api/app/people/EMP-0042/")

    rosa = User.objects.get(employee_id="EMP-0042")
    assert rosa.is_active is False
    assert rosa.contract_end == date(2026, 10, 7)
