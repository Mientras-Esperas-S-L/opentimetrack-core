"""Cambiar la ficha de una empresa, y desactivarla de verdad.

Hasta el 23/09/2026 una empresa solo se podía crear. Y el campo `is_active`, que
existía, **solo frenaba al entrar**: con la empresa desactivada, quien ya estaba
dentro seguía quince minutos, y su token de refresco le renovaba la sesión una
semana entera.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditLog, PlatformAction, PlatformAuditEntry
from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

CLAVE = "Una-clave-larga-de-verdad"


@pytest.fixture
def plataforma():
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )


@pytest.fixture
def mundo():
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@acme.test", password=CLAVE, tenant=empresa, role=Role.ADMIN
        )
        app = Application.objects.create(
            tenant=empresa, name="Conector de ejemplo", scopes=[s.value for s in ApplicationScope]
        )
        _cred, testigo = ApplicationCredential.issue(app, label="prueba")
    return {"empresa": empresa, "jefa": jefa, "testigo": testigo}


def cliente(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def con_token(token):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


def desactivar(plataforma, empresa, **extra):
    return cliente(plataforma).patch(
        f"/api/platform/companies/{empresa.id}/",
        {"is_active": False, "confirm": empresa.name, **extra},
        format="json",
    )


def test_cambia_la_ficha_y_lo_anota_en_los_dos_rastros(
    plataforma, mundo, django_capture_on_commit_callbacks
):
    empresa = mundo["empresa"]
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cliente(plataforma).patch(
            f"/api/platform/companies/{empresa.id}/",
            {"name": "ACME Jardines S.L.", "tax_id": " b22222222 ", "language": "ca"},
            format="json",
        )

    assert respuesta.status_code == 200, respuesta.data
    empresa.refresh_from_db()
    assert (empresa.name, empresa.tax_id, empresa.language) == (
        "ACME Jardines S.L.",
        "B22222222",
        "ca",
    )

    de_la_instalacion = PlatformAuditEntry.objects.get()
    assert de_la_instalacion.action == PlatformAction.COMPANY_CHANGED
    assert de_la_instalacion.changes["tax_id"] == ["B11111111", "B22222222"]
    de_la_empresa = AuditLog.objects.get(tenant=empresa)
    assert de_la_empresa.changes["name"] == ["ACME Ltd", "ACME Jardines S.L."]


def test_no_deja_un_cif_que_ya_tiene_otra(plataforma, mundo):
    Tenant.objects.create(name="Otra", tax_id="B33333333")
    respuesta = cliente(plataforma).patch(
        f"/api/platform/companies/{mundo['empresa'].id}/",
        {"tax_id": "b33333333"},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "tax_id" in respuesta.data["error"]["details"]


def test_desactivar_pide_el_nombre_escrito(plataforma, mundo):
    empresa = mundo["empresa"]
    for confirmacion in ("", "acme ltd", "ACME"):
        respuesta = desactivar(plataforma, empresa, confirm=confirmacion)
        assert respuesta.status_code == 400
        assert "confirm" in respuesta.data["error"]["details"]
    empresa.refresh_from_db()
    assert empresa.is_active


def test_la_sesion_abierta_muere_al_desactivar(plataforma, mundo):
    """El caso que no funcionaba: quien ya estaba dentro."""
    sesion = RefreshToken.for_user(mundo["jefa"])
    dentro = con_token(sesion.access_token)
    assert dentro.get("/api/auth/me/").status_code == 200, "el control: antes entra"

    assert desactivar(plataforma, mundo["empresa"]).status_code == 200

    assert dentro.get("/api/auth/me/").status_code == 401
    renovar = APIClient().post("/api/auth/refresh/", {"refresh": str(sesion)}, format="json")
    assert renovar.status_code >= 400
    assert "access" not in renovar.json()


def test_desactivada_no_entra_nadie_ni_su_aplicacion(plataforma, mundo):
    empresa = mundo["empresa"]
    assert desactivar(plataforma, empresa).status_code == 200

    entrar = APIClient().post(
        "/api/auth/token/", {"email": "jefa@acme.test", "password": CLAVE}, format="json"
    )
    assert entrar.status_code == 400
    assert con_token(mundo["testigo"]).get("/api/app/people/").status_code == 401


def test_reactivar_la_deja_exactamente_como_estaba(
    plataforma, mundo, django_capture_on_commit_callbacks
):
    """Desactivar no toca nada más: ni la gente, ni las credenciales."""
    empresa = mundo["empresa"]
    with django_capture_on_commit_callbacks(execute=True):
        desactivar(plataforma, empresa)
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cliente(plataforma).patch(
            f"/api/platform/companies/{empresa.id}/", {"is_active": True}, format="json"
        )
    assert respuesta.status_code == 200 and respuesta.data["is_active"] is True

    entrar = APIClient().post(
        "/api/auth/token/", {"email": "jefa@acme.test", "password": CLAVE}, format="json"
    )
    assert entrar.status_code == 200
    with tenant_context(empresa.id):
        assert con_token(mundo["testigo"]).get("/api/app/people/").status_code == 200

    acciones = list(PlatformAuditEntry.objects.order_by("at").values_list("action", flat=True))
    assert acciones == [PlatformAction.COMPANY_DEACTIVATED, PlatformAction.COMPANY_REACTIVATED]


def test_el_administrador_de_una_empresa_no_toca_la_ficha(mundo):
    respuesta = cliente(mundo["jefa"]).patch(
        f"/api/platform/companies/{mundo['empresa'].id}/", {"name": "Otra"}, format="json"
    )
    assert respuesta.status_code == 403
