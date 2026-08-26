"""The leave endpoints, and who is allowed to see what.

The isolation tests are the point. Leave reveals things --- who was off sick and
for how long --- that a colleague has no business reading.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def people(company):
    with tenant_context(company.id):
        yield {
            "ana": User.objects.create_user(
                email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
            ),
            "beto": User.objects.create_user(
                email="beto@example.com", password=PASSWORD, tenant=company, first_name="Beto"
            ),
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
        }


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_an_employee_only_sees_their_own_leave(company, people):
    with tenant_context(company.id):
        request_absence(
            employee=people["beto"],
            company=company,
            absence_type=AbsenceType.SICK_LEAVE,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

    response = client_for(people["ana"]).get("/api/absences/")

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_a_manager_sees_the_company(company, people):
    with tenant_context(company.id):
        request_absence(
            employee=people["beto"],
            company=company,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

    response = client_for(people["jefa"]).get("/api/absences/")

    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_an_employee_cannot_file_leave_for_somebody_else(company, people):
    response = client_for(people["ana"]).post(
        "/api/absences/",
        {
            "absence_type": "VACATION",
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
            "employee": str(people["beto"].id),
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_your_request"


@pytest.mark.django_db
def test_an_employee_cannot_approve_their_own_leave(company, people):
    response = client_for(people["ana"]).post(
        "/api/absences/",
        {"absence_type": "VACATION", "start_date": "2026-07-01", "end_date": "2026-07-05"},
        format="json",
    )
    absence_id = response.json()["id"]

    denied = client_for(people["ana"]).post(f"/api/absences/{absence_id}/approve/")

    assert denied.status_code == 403


@pytest.mark.django_db
def test_the_sick_note_is_refused_by_the_api_too(company, people):
    from django.core.files.uploadedfile import SimpleUploadedFile

    response = client_for(people["ana"]).post(
        "/api/absences/",
        {
            "absence_type": "SICK_LEAVE",
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
            "justification": SimpleUploadedFile("parte.pdf", b"%PDF-1.4", "application/pdf"),
        },
        format="multipart",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_medical_certificate"


@pytest.mark.django_db
def test_the_balance_is_your_own_unless_you_manage(company, people):
    denied = client_for(people["ana"]).get(
        "/api/absences/balance/", {"employee": str(people["beto"].id)}
    )
    assert denied.status_code == 409

    allowed = client_for(people["jefa"]).get(
        "/api/absences/balance/", {"employee": str(people["beto"].id)}
    )
    assert allowed.status_code == 200
    assert allowed.json()["remaining"] == 22


@pytest.mark.django_db
def test_the_overview_tells_an_employee_nothing_about_the_company(company, people):
    response = client_for(people["ana"]).get("/api/overview/")

    body = response.json()
    assert body["scope"] == "self"
    assert "working_now" not in body
    assert "headcount" not in body


@pytest.mark.django_db
def test_the_overview_shows_a_manager_who_is_working(company, people):
    from apps.punches.services import register_punch

    with tenant_context(company.id):
        register_punch(employee=people["beto"], company=company)

    body = client_for(people["jefa"]).get("/api/overview/").json()

    assert body["scope"] == "company"
    assert [w["name"] for w in body["working_now"]] == [people["beto"].get_full_name()]
    assert len(body["week"]["days"]) == 7


@pytest.mark.django_db
def test_somebody_who_clocked_out_is_not_working_now(company, people):
    from apps.punches.services import register_punch

    with tenant_context(company.id):
        # Con horas entre entrada y salida, que es lo que pasa de verdad:
        # pegadas las rechaza la protección del doble toque.
        with freeze_time("2026-08-13 08:00:00"):
            register_punch(employee=people["beto"], company=company)
        with freeze_time("2026-08-13 17:00:00"):
            register_punch(employee=people["beto"], company=company)  # out

    body = client_for(people["jefa"]).get("/api/overview/").json()

    assert body["working_now"] == []


@pytest.mark.django_db
def test_la_busqueda_de_ausencias_busca(company, people):
    """`?search=` estaba publicado y no filtraba nada.

    El backend de búsqueda viene en los de por defecto, así que el parámetro
    aparecía en el esquema; sin `search_fields`, DRF lo ignora y devuelve la
    lista entera. Un cliente que lo use se queda con la primera página creyendo
    que es el resultado de su búsqueda --- y en una lista paginada la diferencia
    entre «no hay» y «no cabe en la página» no se ve.

    Salió al caza de por qué fallaba una prueba de navegador que buscaba por su
    propia marca: había cincuenta y cinco ausencias con fecha posterior y la
    suya, recién creada, se caía de la página.
    """
    with tenant_context(company.id):
        request_absence(
            employee=people["ana"],
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
            reason="Cita en el juzgado",
        )
        request_absence(
            employee=people["ana"],
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 5),
            reason="Mudanza",
        )

    client = APIClient()
    client.force_authenticate(user=people["jefa"])

    todas = client.get("/api/absences/")
    juzgado = client.get("/api/absences/?search=juzgado")

    assert todas.status_code == 200
    assert juzgado.status_code == 200
    assert juzgado.data["count"] < todas.data["count"], "la búsqueda no acotó nada"
    assert [a["reason"] for a in juzgado.data["results"]] == ["Cita en el juzgado"]


@pytest.mark.django_db
def test_y_busca_tambien_por_la_persona_sin_acentos(company, people):
    """Que es como se busca una ausencia de verdad: «las de García»."""
    with tenant_context(company.id):
        garcia = User.objects.create_user(
            email="garcia@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Lucía",
            last_name="García",
        )
        request_absence(
            employee=garcia,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 11, 3),
            end_date=date(2026, 11, 3),
            reason="Suya",
        )

    client = APIClient()
    client.force_authenticate(user=people["jefa"])

    sin_tilde = client.get("/api/absences/?search=garcia")

    assert sin_tilde.status_code == 200
    assert [a["employee_name"] for a in sin_tilde.data["results"]] == ["Lucía García"]
