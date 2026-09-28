"""Un asiento demasiado largo no puede tumbar lo que describe.

`record()` prometía en su docstring «silent on success, loud on failure, **never
fatal**» y no lo era: el `save` va en un `on_commit`, o sea **fuera** del `try`
que lo envolvía, así que cualquier fallo suyo escapaba y devolvía un 500.

Y fallaba de verdad, con datos válidos. `Tenant.name` admite doscientos cincuenta
y cinco caracteres; `AuditLog.target_label`, doscientos. Una razón social larga
---la que tiene cualquier sociedad con «y Asociados, Sociedad Limitada
Profesional» detrás--- guardaba bien y reventaba al escribir el rastro: la
petición contestaba 500 y el cambio se revertía entero.

El truncado ya existía, pero **solo en la rama que deriva la etiqueta de
`target`**; cuando se la pasan hecha, que es lo que hacen casi todas las
llamadas, iba entera.
"""

from __future__ import annotations

import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.audit.services import record
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B12121212", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            role=Role.ADMIN,
        )


@pytest.mark.django_db
def test_una_etiqueta_mas_larga_que_su_columna_se_corta(
    empresa, quien, django_capture_on_commit_callbacks
):
    with tenant_context(empresa.id), django_capture_on_commit_callbacks(execute=True):
        record(
            action=AuditAction.SETTINGS_CHANGED,
            actor=quien,
            target=empresa,
            target_type="tenant",
            target_label="L" * 400,
        )
    with tenant_context(empresa.id):
        asiento = AuditLog.objects.order_by("-at").first()

    assert asiento is not None, "no se escribió el asiento"
    assert len(asiento.target_label) == 200


@pytest.mark.django_db
def test_tambien_la_de_quien_actua_y_la_nota(empresa, quien, django_capture_on_commit_callbacks):
    """Las tres columnas de texto libre, no solo una. `note` ya se cortaba y
    `actor_label` no, que es la clase de asimetría que deja el fallo esperando en
    la columna de al lado."""
    with tenant_context(empresa.id), django_capture_on_commit_callbacks(execute=True):
        record(
            action=AuditAction.SETTINGS_CHANGED,
            actor=quien,
            actor_label="A" * 400,
            target=empresa,
            note="N" * 900,
        )
    with tenant_context(empresa.id):
        asiento = AuditLog.objects.order_by("-at").first()

    assert len(asiento.actor_label) == 160
    assert len(asiento.note) == 300


@pytest.mark.django_db
def test_una_razon_social_larga_no_devuelve_500(empresa, quien):
    """**El caso real, por la puerta que lo destapó.**

    Doscientos veintinueve caracteres: válidos para el nombre de una empresa y
    demasiados para la etiqueta del asiento.
    """
    from rest_framework.test import APIClient

    largo = "Sociedad " + "Muy Larga " * 22
    assert 200 < len(largo) <= 255, "el caso ya no está entre los dos límites"

    cliente = APIClient()
    cliente.force_authenticate(user=quien)
    respuesta = cliente.patch("/api/company/", {"name": largo}, format="json")

    assert respuesta.status_code == 200, f"contestó {respuesta.status_code}"
    with tenant_context(empresa.id):
        assert Tenant.objects.get(pk=empresa.pk).name.startswith("Sociedad Muy Larga")


@pytest.mark.django_db
def test_si_el_asiento_falla_la_operacion_sigue_en_pie(
    empresa, quien, monkeypatch, django_capture_on_commit_callbacks
):
    """Lo que el docstring prometía y no cumplía.

    Aquí la transacción ya se ha cerrado: lanzar no deshace nada ---solo convierte
    una operación buena en un error para quien la pidió--- y encima deja el hueco
    igual. Se traga el fallo y **se registra en el log**, que es la mitad que
    hace que un hueco no sea invisible.
    """
    from apps.audit import services

    def revienta(self, *args, **kwargs):
        raise RuntimeError("la base dice que no")

    monkeypatch.setattr(AuditLog, "save", revienta)

    with tenant_context(empresa.id), django_capture_on_commit_callbacks(execute=True):
        # No lanza: si lanzara, esta línea rompería la prueba.
        services.record(
            action=AuditAction.SETTINGS_CHANGED,
            actor=quien,
            target=empresa,
            target_label="lo que sea",
        )


@pytest.mark.django_db
def test_lo_que_identifica_la_fila_no_se_toca(empresa, quien, django_capture_on_commit_callbacks):
    """Cortar la etiqueta es aceptable porque es «lo que se vio»; `target_id` es
    lo que permite volver a la fila, y ese no se corta ni se deriva."""
    with tenant_context(empresa.id), django_capture_on_commit_callbacks(execute=True):
        record(
            action=AuditAction.SETTINGS_CHANGED,
            actor=quien,
            target=empresa,
            target_label="X" * 500,
        )
    with tenant_context(empresa.id):
        asiento = AuditLog.objects.order_by("-at").first()

    assert str(asiento.target_id) == str(empresa.pk)


@pytest.mark.django_db
def test_el_rastro_de_la_instalacion_corta_igual(empresa, django_capture_on_commit_callbacks):
    """El registro de la instalación tenía el mismo hueco, copiado de `record`."""
    from apps.audit.models import PlatformAction, PlatformAuditEntry
    from apps.audit.services import record_platform

    with django_capture_on_commit_callbacks(execute=True):
        record_platform(
            action=PlatformAction.COMPANY_CHANGED,
            actor=None,
            company=empresa,
            target=empresa,
            target_label="L" * 400,
            note="N" * 900,
        )
    asiento = PlatformAuditEntry.objects.first()

    assert asiento is not None, "no se escribió el asiento"
    assert len(asiento.target_label) == 200
    assert len(asiento.note) == 300
