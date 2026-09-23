"""Lo que hacen las cuentas de la instalación queda escrito, y no se puede reescribir.

Hasta el 23/09/2026 no quedaba en ningún sitio que una cuenta de instalación
creara una empresa, diera de alta otra cuenta o le pusiera contraseña nueva. Lo
que tocaba a una empresa sí iba a su rastro; lo de la instalación, a ninguno.
"""

from __future__ import annotations

import json

import pytest
from django.db import connection, transaction
from django.db.utils import DatabaseError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog, PlatformAction, PlatformAuditEntry
from apps.tenants.models import Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def plataforma():
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
        first_name="Plata",
        last_name="Forma",
    )


def cliente(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def _todo_el_registro() -> str:
    """El registro entero en texto, para buscar en él lo que no debe estar."""
    return json.dumps(list(PlatformAuditEntry.objects.values()), default=str, ensure_ascii=False)


def test_crear_una_empresa_queda_escrito_sin_su_contrasena(
    plataforma, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cliente(plataforma).post(
            "/api/platform/companies/",
            {
                "company_name": "Jardines de Ejemplo, S.L.",
                "tax_id": "U00000000",
                "country": "ES",
                "time_zone": "Europe/Madrid",
                "email": "quien.administre@empresa.example",
                "first_name": "Quien",
                "last_name": "Administre",
            },
            format="json",
        )
    assert respuesta.status_code == 201

    entrada = PlatformAuditEntry.objects.get()
    assert entrada.action == PlatformAction.COMPANY_CREATED
    assert entrada.actor == plataforma
    assert entrada.company.tax_id == "U00000000"
    assert entrada.company_label == "Jardines de Ejemplo, S.L."
    assert respuesta.data["administrator"]["password"] not in _todo_el_registro()


def test_las_cuentas_de_la_instalacion_dejan_rastro_y_ninguna_contrasena(
    plataforma, django_capture_on_commit_callbacks
):
    api = cliente(plataforma)
    with django_capture_on_commit_callbacks(execute=True):
        creada = api.post(
            "/api/platform/admins/",
            {"email": "otra@ejemplo.test", "first_name": "Otra", "last_name": "Cuenta"},
            format="json",
        )
    with django_capture_on_commit_callbacks(execute=True):
        nueva = api.post(f"/api/platform/admins/{creada.data['id']}/password/", {})
    with django_capture_on_commit_callbacks(execute=True):
        api.delete(f"/api/platform/admins/{creada.data['id']}/")

    acciones = list(PlatformAuditEntry.objects.order_by("at").values_list("action", flat=True))
    assert acciones == [
        PlatformAction.ADMIN_CREATED,
        PlatformAction.ADMIN_PASSWORD_RESET,
        PlatformAction.ADMIN_DEACTIVATED,
    ]
    assert all(e.target_label == "otra@ejemplo.test" for e in PlatformAuditEntry.objects.all())
    assert all(e.company is None for e in PlatformAuditEntry.objects.all())
    registro = _todo_el_registro()
    assert creada.data["password"] not in registro
    assert nueva.data["password"] not in registro


def test_lo_que_toca_a_una_empresa_va_a_los_dos_rastros_y_sin_el_testigo(
    plataforma, company, django_capture_on_commit_callbacks
):
    """El de la instalación, para quien la administra; el de la empresa, para que
    su administrador vea que alguien de fuera tocó su configuración."""
    api = cliente(plataforma)
    with django_capture_on_commit_callbacks(execute=True):
        alta = api.post(
            f"/api/platform/companies/{company.id}/applications/",
            {"name": "Conector de ejemplo"},
            format="json",
        )
    aplicacion = alta.data["id"]
    with django_capture_on_commit_callbacks(execute=True):
        otra = api.post(
            f"/api/platform/companies/{company.id}/applications/{aplicacion}/credentials/",
            {"label": "segunda"},
            format="json",
        )
    with django_capture_on_commit_callbacks(execute=True):
        api.delete(f"/api/platform/companies/{company.id}/applications/{aplicacion}/")

    acciones = list(PlatformAuditEntry.objects.order_by("at").values_list("action", flat=True))
    assert acciones == [
        PlatformAction.APPLICATION_AUTHORISED,
        PlatformAction.CREDENTIAL_ISSUED,
        PlatformAction.APPLICATION_WITHDRAWN,
    ]
    assert all(e.company == company for e in PlatformAuditEntry.objects.all())
    assert AuditLog.objects.filter(tenant=company).count() == 3

    registro = _todo_el_registro()
    assert alta.data["token"] not in registro
    assert otra.data["token"] not in registro


def test_se_lee_lo_mas_reciente_primero_y_solo_desde_la_instalacion(
    plataforma, company, django_capture_on_commit_callbacks
):
    api = cliente(plataforma)
    for nombre in ("una@ejemplo.test", "dos@ejemplo.test"):
        with django_capture_on_commit_callbacks(execute=True):
            api.post(
                "/api/platform/admins/",
                {"email": nombre, "first_name": "A", "last_name": "B"},
                format="json",
            )

    respuesta = api.get("/api/platform/audit/")
    assert respuesta.status_code == 200
    assert respuesta.data["count"] == 2
    assert [e["target_label"] for e in respuesta.data["results"]] == [
        "dos@ejemplo.test",
        "una@ejemplo.test",
    ]
    assert respuesta.data["results"][0]["actor"] == "Plata Forma"

    de_la_empresa = User.objects.create_user(
        email="jefa@acme.test", password="X" * 14, tenant=company, role=Role.ADMIN
    )
    assert cliente(de_la_empresa).get("/api/platform/audit/").status_code == 403


def test_la_base_no_deja_reescribir_ni_borrar_el_registro(plataforma):
    entrada = PlatformAuditEntry.objects.create(
        actor=plataforma, actor_label="Plata Forma", action=PlatformAction.ADMIN_CREATED
    )
    for orden in (
        "UPDATE audit_platformauditentry SET note = 'otra cosa' WHERE id = %s",
        "DELETE FROM audit_platformauditentry WHERE id = %s",
    ):
        with pytest.raises(DatabaseError, match="append-only"):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(orden, [str(entrada.id)])


def test_la_salud_avisa_si_al_registro_de_la_instalacion_le_falta_un_guardian():
    """TRUNCATE no se puede probar aquí ---en la transacción de la prueba hay
    eventos de clave foránea pendientes y la base lo rechaza por eso, no por el
    guardián---, así que se comprueba lo que sí vigila producción: que la sonda de
    salud lo echa en falta, y que el comando lo repone."""
    from io import StringIO

    from django.core.management import call_command

    from apps.common.views import _check_audit_is_append_only

    with connection.cursor() as cursor:
        cursor.execute("DROP TRIGGER platform_audit_no_truncate ON audit_platformauditentry")
    bien, motivo = _check_audit_is_append_only()
    assert not bien and "platform_audit_no_truncate" in motivo, motivo

    call_command("ensure_append_only", stdout=StringIO())
    bien, motivo = _check_audit_is_append_only()
    assert bien, motivo
