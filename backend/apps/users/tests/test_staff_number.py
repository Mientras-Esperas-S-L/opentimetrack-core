"""El número de empleado: único dentro de la empresa, repetible entre empresas.

Es el puente con las aplicaciones que fichan en nombre de alguien --- el
conector manda «EMP-0042» y el servidor tiene que saber a quién se refiere ---
así que un duplicado no es un detalle de aseo: la resolución devuelve a quien
salga primero y los fichajes acaban en la ficha de otra persona. Un fallo que no
avisa, y que solo se descubre cuando alguien mira su registro y ve jornadas que
no hizo.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def other_company(db):
    return Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Jefa",
            role=Role.ADMIN,
        )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_the_database_refuses_a_repeated_staff_number(company):
    with tenant_context(company.id):
        User.objects.create_user(
            email="uno@example.com", password=PASSWORD, tenant=company, employee_id="EMP-0042"
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email="dos@example.com", password=PASSWORD, tenant=company, employee_id="EMP-0042"
            )


@pytest.mark.django_db
def test_two_companies_may_each_have_their_own(company, other_company):
    """No es un identificador global: cada empresa numera a su gente."""
    with tenant_context(company.id):
        User.objects.create_user(
            email="uno@acme.example", password=PASSWORD, tenant=company, employee_id="EMP-0001"
        )
    with tenant_context(other_company.id):
        User.objects.create_user(
            email="uno@globex.example",
            password=PASSWORD,
            tenant=other_company,
            employee_id="EMP-0001",
        )

    # Dicho en voz alta y no dado por hecho. Antes la prueba no afirmaba nada:
    # se apoyaba en que crear el segundo no lanzara `IntegrityError`, y eso
    # también pasa si un día alguien quita la restricción entera. Que existe lo
    # prueba la de arriba; que es **por empresa**, esto.
    #
    # Filtrando por `tenant` a mano, y no con `tenant_context`: `User.objects`
    # es el único gestor del dominio que **no** filtra por la empresa en
    # contexto, y está documentado por qué ---al entrar todavía no hay empresa,
    # así que buscar el correo tiene que cruzar todas---. El aislamiento de las
    # personas lo sostienen las vistas y los permisos, no el gestor.
    assert User.objects.filter(tenant=company, employee_id="EMP-0001").count() == 1
    assert User.objects.filter(tenant=other_company, employee_id="EMP-0001").count() == 1


@pytest.mark.django_db
def test_blank_is_not_a_collision(company):
    """Una empresa que no numera a su gente los tiene todos en blanco."""
    with tenant_context(company.id):
        for n in range(3):
            User.objects.create_user(email=f"sin{n}@example.com", password=PASSWORD, tenant=company)
        assert User.objects.filter(tenant=company, employee_id="").count() == 3


@pytest.mark.django_db
def test_the_api_says_who_already_uses_it(company, admin):
    """Y no un 500 de la base, que no dice qué corregir."""
    with tenant_context(company.id):
        User.objects.create_user(
            email="veterana@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Rosa",
            last_name="Veterana",
            employee_id="EMP-0007",
        )

    answer = client_for(admin).post(
        "/api/employees/",
        {
            "email": "nueva@example.com",
            "first_name": "Nueva",
            "last_name": "Persona",
            "employee_id": "EMP-0007",
        },
        format="json",
    )

    assert answer.status_code == 400
    assert "Rosa Veterana" in str(answer.json()["error"]["details"])


@pytest.mark.django_db
def test_editing_somebody_keeping_their_own_number_is_fine(company, admin):
    """El choque consigo mismo no es un choque."""
    with tenant_context(company.id):
        person = User.objects.create_user(
            email="misma@example.com", password=PASSWORD, tenant=company, employee_id="EMP-0009"
        )

    answer = client_for(admin).patch(
        f"/api/employees/{person.id}/",
        {"employee_id": "EMP-0009", "first_name": "Cambiada"},
        format="json",
    )
    assert answer.status_code == 200
