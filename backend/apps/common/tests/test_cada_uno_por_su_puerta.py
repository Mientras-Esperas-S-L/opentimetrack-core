"""Una aplicación no entra por la API de personas, y una persona sí.

`ApplicationUser` contesta `is_authenticated` y trae `tenant_id`, así que
`IsAuthenticatedInTenant` la daba por buena. Medido con una credencial **sin
ningún permiso declarado**:

    GET /api/departments/          -> 200   la estructura de la empresa
    GET /api/workplaces/           -> 200
    GET /api/working-time-rules/   -> 200   sus reglas de jornada
    GET /api/audit/                -> AttributeError: sin 'id'      (un 500)
    GET /api/punches/              -> AttributeError: sin 'pk'      (un 500)
    GET /api/reports/working-time/ -> AttributeError: sin 'tzinfo'  (un 500)

`HasApplicationScope` dice de sí mismo que «olvidar declarar un permiso no debe
abrir una puerta». No la abría él: la abría el permiso de al lado, que no sabía
de aplicaciones. Dos sistemas de permisos correctos por separado, y nadie había
mirado el cruce.

La mitad de este fichero es lo que **no** puede romperse: una aplicación con sus
permisos tiene que seguir entrando por `/api/app/…`, y una persona por la suya.
Cerrar de más aquí sería mucho peor que el fallo.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.applications import Application, ApplicationCredential, ApplicationScope
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

#: Endpoints de personas que una credencial de aplicación alcanzaba.
DE_PERSONAS = [
    "/api/employees/",
    "/api/audit/",
    "/api/punches/",
    "/api/absences/",
    "/api/departments/",
    "/api/workplaces/",
    "/api/working-time-rules/",
    "/api/reports/payroll-summary/",
    "/api/reports/working-time/",
    "/api/punches/today/",
    "/api/overview/",
]


@pytest.fixture
def puerta(db):
    empresa = Tenant.objects.create(name="Puerta SL", tax_id="B55550000", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Je",
            last_name="Fa",
            role=Role.ADMIN,
        )
        app = Application.objects.create(
            tenant=empresa, name="Conector", scopes=[s.value for s in ApplicationScope]
        )
        _cred, raw = ApplicationCredential.issue(app, label="prueba")
        yield empresa, jefa, raw


def _como_aplicacion(token):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


@pytest.mark.parametrize("ruta", DE_PERSONAS)
@pytest.mark.django_db
def test_la_aplicacion_no_entra_por_la_puerta_de_las_personas(puerta, ruta):
    empresa, _jefa, token = puerta
    with tenant_context(empresa.id):
        r = _como_aplicacion(token).get(ruta)

    assert r.status_code == 403, (
        f"{ruta} contestó {r.status_code} a una credencial de aplicación. "
        "Con 2xx entrega datos de personas por una puerta que no es la suya; con "
        "5xx revienta al pedirle a la aplicación algo que solo tiene una persona"
    )
    assert "api/app/" in str(r.json()), "y el 403 tiene que decir cuál es su puerta"


@pytest.mark.django_db
def test_pero_sí_entra_por_la_suya(puerta):
    """El contraste que más importa: cerrar de más rompería toda integración."""
    empresa, _jefa, token = puerta
    api = _como_aplicacion(token)
    with tenant_context(empresa.id):
        assert api.get("/api/app/people/").status_code == 200
        assert api.get("/api/app/attendance/").status_code == 200


@pytest.mark.parametrize(
    "ruta", ["/api/departments/", "/api/employees/", "/api/working-time-rules/"]
)
@pytest.mark.django_db
def test_y_una_persona_sigue_entrando_por_la_suya(puerta, ruta):
    """El otro contraste: la comprobación mira si el llamante es una aplicación,
    y una persona no puede caer en esa rama por parecerse."""
    empresa, jefa, _token = puerta
    api = APIClient()
    api.force_authenticate(user=jefa)
    with tenant_context(empresa.id):
        assert api.get(ruta).status_code == 200, ruta
