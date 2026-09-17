"""Por dónde se ficha cuando una aplicación integrada es la puerta normal.

Lo que se fija aquí es que la puerta de este sistema **no se cierra**: se pide un
motivo. Si la única vía fuera la aplicación, el día que no esté disponible habría
gente trabajando sin poder registrar su jornada, y quien responde ante una inspección
es este sistema, no la aplicación.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
URL = "/api/punches/"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def rosa(company):
    with tenant_context(company.id):
        return User.objects.create_user(
            email="rosa@acme.example", password=PASSWORD, tenant=company, employee_id="EMP-1"
        )


def _como(person):
    client = APIClient()
    client.force_authenticate(user=person)
    return client


@pytest.mark.django_db
def test_por_defecto_se_ficha_aqui_sin_dar_explicaciones(company, rosa):
    assert company.punch_entry == Tenant.PunchEntry.ANY
    assert _como(rosa).post(URL, {}, format="json").status_code == 201


@pytest.mark.django_db
def test_cuando_la_puerta_normal_es_la_aplicacion_aqui_se_pide_motivo(company, rosa):
    company.punch_entry = Tenant.PunchEntry.APPLICATION
    company.save(update_fields=["punch_entry"])

    answer = _como(rosa).post(URL, {}, format="json")

    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "exception_reason_required"
    with tenant_context(company.id):
        assert not Punch.objects.exists()


@pytest.mark.django_db
def test_con_motivo_se_ficha_igualmente_y_queda_marcado(company, rosa):
    """Lo importante: la puerta no se cierra. La excepción se anota y se ve."""
    company.punch_entry = Tenant.PunchEntry.APPLICATION
    company.save(update_fields=["punch_entry"])

    answer = _como(rosa).post(
        URL, {"exception_reason": "La aplicación de gestión no responde"}, format="json"
    )

    assert answer.status_code == 201
    with tenant_context(company.id):
        punch = Punch.objects.get(employee=rosa)
    assert punch.evidence["exception"]["reason"] == "La aplicación de gestión no responde"


@pytest.mark.django_db
def test_un_motivo_de_dos_letras_no_es_un_motivo(company, rosa):
    company.punch_entry = Tenant.PunchEntry.APPLICATION
    company.save(update_fields=["punch_entry"])

    answer = _como(rosa).post(URL, {"exception_reason": "ya"}, format="json")

    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "exception_reason_required"


@pytest.mark.django_db
def test_la_aplicacion_no_tiene_que_justificarse_porque_es_la_puerta_normal(company, rosa):
    company.punch_entry = Tenant.PunchEntry.APPLICATION
    company.save(update_fields=["punch_entry"])

    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="Geosian", scopes=[str(ApplicationScope.PUNCH_SELF)]
        )
        ApplicationCredential.issue(application)

    # La sesión que la aplicación obtiene lleva su marca dentro del token: es lo que
    # distingue «la aplicación está actuando» de «alguien entró por la interfaz».
    from apps.users.serializers import issue_tokens

    tokens = issue_tokens(rosa, acting_application=application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    answer = client.post(URL, {}, format="json")

    assert answer.status_code == 201, "la puerta esperada no pide explicaciones"
    with tenant_context(company.id):
        assert Punch.objects.get(employee=rosa).source == "APPLICATION"
