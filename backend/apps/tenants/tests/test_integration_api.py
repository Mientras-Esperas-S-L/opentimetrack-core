"""La API que usa otra herramienta para integrarse: personas y asistencia.

Lo que se prueba aquí es lo que hace fiable a un conector: que reintentar no
duplique, que la baja no borre, que cada permiso abra solo su puerta, y que
nada de esto cruce de una empresa a otra.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def other_company(db):
    return Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")


def credential(company, *scopes):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="Geosian", scopes=[str(scope) for scope in scopes]
        )
        _credential, secret = ApplicationCredential.issue(application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    return client, application


@pytest.fixture
def connector(company):
    client, _ = credential(
        company,
        ApplicationScope.READ_PEOPLE,
        ApplicationScope.WRITE_PEOPLE,
        ApplicationScope.READ_ATTENDANCE,
    )
    return client


# --------------------------------------------------------------- el empuje


@pytest.mark.django_db
def test_pushing_somebody_creates_them(connector, company):
    answer = connector.put(
        "/api/app/people/EMP-0042/",
        {
            "email": "rosa@acme.example",
            "first_name": "Rosa",
            "last_name": "Campos",
            "employee_id": "EMP-0042",
        },
        format="json",
    )
    assert answer.status_code == 201
    assert answer.json()["employee_id"] == "EMP-0042"

    with tenant_context(company.id):
        assert User.objects.filter(tenant=company, employee_id="EMP-0042").count() == 1


@pytest.mark.django_db
def test_pushing_twice_updates_instead_of_duplicating(connector, company):
    """Lo que hace que un conector pueda reintentar. La red se cae y el
    servidor se despliega; reintentar no puede crear una segunda persona."""
    cuerpo = {
        "email": "rosa@acme.example",
        "first_name": "Rosa",
        "last_name": "Campos",
        "employee_id": "EMP-0042",
    }
    primera = connector.put("/api/app/people/EMP-0042/", cuerpo, format="json")
    segunda = connector.put(
        "/api/app/people/EMP-0042/", {**cuerpo, "last_name": "Campos Ruiz"}, format="json"
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200  # actualizada, no creada
    assert segunda.json()["last_name"] == "Campos Ruiz"
    with tenant_context(company.id):
        assert User.objects.filter(tenant=company, employee_id="EMP-0042").count() == 1


@pytest.mark.django_db
def test_the_reference_may_be_the_identity_provider_subject(connector, company):
    connector.put(
        "/api/app/people/EMP-0042/",
        {
            "email": "rosa@acme.example",
            "first_name": "Rosa",
            "employee_id": "EMP-0042",
            "oidc_sub": "azure|abc123",
        },
        format="json",
    )
    # La misma persona, encontrada por el ancla del proveedor de identidad.
    de_nuevo = connector.get("/api/app/people/azure|abc123/")
    assert de_nuevo.status_code == 200
    assert de_nuevo.json()["employee_id"] == "EMP-0042"


@pytest.mark.django_db
def test_the_push_refuses_to_steal_somebody_elses_staff_number(connector, company):
    connector.put(
        "/api/app/people/EMP-0001/",
        {"email": "uno@acme.example", "first_name": "Uno", "employee_id": "EMP-0001"},
        format="json",
    )
    choque = connector.put(
        "/api/app/people/otra@acme.example/",
        {"email": "otra@acme.example", "first_name": "Otra", "employee_id": "EMP-0001"},
        format="json",
    )
    assert choque.status_code == 409
    assert choque.json()["error"]["code"] == "staff_number_taken"


@pytest.mark.django_db
def test_the_baja_deactivates_and_keeps_the_record(connector, company):
    """Los fichajes viven cuatro años y sobreviven a quien los hizo."""
    connector.put(
        "/api/app/people/EMP-0042/",
        {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"},
        format="json",
    )
    baja = connector.delete("/api/app/people/EMP-0042/")

    assert baja.status_code == 200
    assert baja.json()["is_active"] is False
    with tenant_context(company.id):
        assert User.objects.filter(tenant=company, employee_id="EMP-0042").exists()


@pytest.mark.django_db
def test_pushing_again_brings_a_seasonal_worker_back(connector, company):
    """Quien viene por temporadas vuelve con el mismo número."""
    cuerpo = {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"}
    connector.put("/api/app/people/EMP-0042/", cuerpo, format="json")
    connector.delete("/api/app/people/EMP-0042/")
    vuelta = connector.put("/api/app/people/EMP-0042/", cuerpo, format="json")

    assert vuelta.json()["is_active"] is True


# ------------------------------------------------------------- los permisos


@pytest.mark.django_db
def test_reading_does_not_grant_writing(company):
    """Una integración que solo pinta la asistencia no puede dar de alta."""
    client, _ = credential(company, ApplicationScope.READ_PEOPLE)

    assert client.get("/api/app/people/").status_code == 200
    escribir = client.put(
        "/api/app/people/EMP-0001/",
        {"email": "x@acme.example", "first_name": "X"},
        format="json",
    )
    assert escribir.status_code == 403


@pytest.mark.django_db
def test_attendance_needs_its_own_permission(company):
    client, _ = credential(company, ApplicationScope.READ_PEOPLE)
    assert client.get("/api/app/attendance/").status_code == 403


@pytest.mark.django_db
def test_a_person_token_does_not_open_the_application_doors(company):
    """Estas puertas son para aplicaciones. Una sesión de persona, por
    administradora que sea, no entra por aquí."""
    with tenant_context(company.id):
        from apps.users.models import Role

        admin = User.objects.create_user(
            email="jefa@acme.example", password=PASSWORD, tenant=company, role=Role.ADMIN
        )
    client = APIClient()
    client.force_authenticate(user=admin)

    assert client.get("/api/app/people/").status_code == 403


# ------------------------------------------------------------ el aislamiento


@pytest.mark.django_db
def test_a_credential_only_reaches_its_own_company(company, other_company):
    with tenant_context(other_company.id):
        ajena = User.objects.create_user(
            email="rosa@globex.example",
            password=PASSWORD,
            tenant=other_company,
            employee_id="EMP-0042",
        )

    client, _ = credential(company, ApplicationScope.READ_PEOPLE, ApplicationScope.WRITE_PEOPLE)

    # El mismo número existe en la otra empresa y aquí no.
    assert client.get("/api/app/people/EMP-0042/").status_code == 409
    # Y empujarlo crea uno **propio**, no toca al de al lado.
    client.put(
        "/api/app/people/EMP-0042/",
        {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"},
        format="json",
    )
    ajena.refresh_from_db()
    assert ajena.email == "rosa@globex.example"
    assert ajena.tenant_id == other_company.id


# ------------------------------------------------------------- la asistencia


@pytest.mark.django_db
def test_attendance_answers_with_the_day_and_no_capture_metadata(connector, company):
    """La IP y el dispositivo son datos de seguridad de esta empresa y no salen
    hacia otra aplicación por poder leer la asistencia."""
    from apps.punches.services import register_punch

    with tenant_context(company.id):
        persona = User.objects.create_user(
            email="rosa@acme.example", password=PASSWORD, tenant=company, employee_id="EMP-0042"
        )
        register_punch(employee=persona, company=company, ip_address="10.0.0.9")

    answer = connector.get("/api/app/attendance/", {"employee_ref": "EMP-0042"})
    assert answer.status_code == 200
    dia = answer.json()["people"][0]
    assert dia["state"] == "WORKING"
    assert "10.0.0.9" not in str(answer.json())
    assert all("ip" not in tramo for tramo in dia["segments"])
