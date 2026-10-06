"""Un correo que no sale no tumba nada, y tampoco desaparece sin rastro.

Había dos fallos opuestos:

- Los avisos ---recordatorios, cambios en el registro, el aviso a la
  representación--- iban con `fail_silently=True`. No tumbaban nada, bien, pero
  con el servidor de correo caído **no quedaba ni una línea en el log**: los
  `try/except` que los rodeaban no veían la excepción, porque se la tragaba
  Django antes.
- El alta de una persona y «He olvidado mi contraseña» iban sin red. Con el
  correo caído, el alta contestaba 500 y la transacción se llevaba a la persona
  por delante; y la recuperación contestaba 500 solo a las direcciones que
  existen, que es justo lo que esa vista se niega a contar.

Se prueba con el servidor SMTP de verdad apuntando a un puerto cerrado: es lo
que pasa cuando el relé se cae, y es lo único que `fail_silently` sabía callar.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.mail import mask_address
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

PASSWORD = "a-sufficiently-long-password"

#: El backend del producto contra un puerto donde no escucha nadie.
CORREO_CAIDO = override_settings(
    EMAIL_BACKEND="apps.common.mail.SMTPBackend",
    EMAIL_HOST="127.0.0.1",
    EMAIL_PORT=1,
    EMAIL_USE_TLS=False,
    EMAIL_USE_SSL=False,
    EMAIL_TIMEOUT=2,
)


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def admin(company):
    return User.objects.create_user(
        email="jefa@acme.example", password=PASSWORD, tenant=company, role=Role.ADMIN
    )


@pytest.fixture
def marta(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="marta@acme.example",
            password=PASSWORD,
            tenant=company,
            first_name="Marta",
            employee_id="EMP-0003",
        )


def _lineas(caplog, nivel=logging.ERROR):
    return [r for r in caplog.records if r.levelno >= nivel]


def test_la_direccion_va_enmascarada():
    assert mask_address("marta.ruiz@acme.example") == "m***@acme.example"
    assert mask_address("") == "***"
    assert mask_address("sin-arroba") == "***"


# ------------------------------------------------- los avisos: no cortan y avisan


@CORREO_CAIDO
def test_el_aviso_de_un_cambio_en_el_registro_que_no_sale_queda_en_el_log(
    company, marta, admin, caplog, django_capture_on_commit_callbacks
):
    from apps.punches.corrections import CorrectionKind, approve_correction, request_correction
    from apps.punches.services import register_punch

    with freeze_time("2026-08-10 06:00:00"):
        original = register_punch(employee=marta, company=company)
    correction = request_correction(
        employee=marta,
        company=company,
        requested_by=marta,
        kind=CorrectionKind.MODIFY,
        target=original,
        reason="El reloj iba adelantado.",
        proposed_timestamp=original.timestamp + timedelta(minutes=20),
    )

    with caplog.at_level(logging.WARNING), django_capture_on_commit_callbacks(execute=True):
        approve_correction(correction, resolved_by=admin)

    correction.refresh_from_db()
    assert correction.status == "APPROVED", "el correo caído no deshace la corrección"
    lineas = [r.getMessage() for r in _lineas(caplog)]
    assert any("m***@acme.example" in linea for linea in lineas), lineas
    assert not any("marta@acme.example" in linea for linea in lineas), "la dirección, tapada"


@CORREO_CAIDO
def test_un_recordatorio_que_no_sale_queda_en_el_log(marta, caplog):
    from apps.punches.models import PunchReminder
    from apps.punches.reminders import DueReminder, _deliver

    with caplog.at_level(logging.WARNING):
        _deliver(DueReminder(marta, date(2026, 10, 7), PunchReminder.Kind.CLOCK_IN))

    assert any("m***@acme.example" in r.getMessage() for r in _lineas(caplog))


# --------------------------------------------- el alta y la recuperación: no se pierden


@CORREO_CAIDO
def test_el_alta_se_queda_aunque_la_invitacion_no_salga(admin, company, caplog):
    client = APIClient()
    client.force_authenticate(admin)

    with caplog.at_level(logging.WARNING):
        respuesta = client.post(
            reverse("employee-list"),
            {
                "email": "nuevo@acme.example",
                "first_name": "Nuevo",
                "last_name": "Operario",
                "role": Role.EMPLOYEE,
            },
            format="json",
        )

    assert respuesta.status_code == 201, respuesta.data
    assert respuesta.data["invitation_sent"] is False
    assert User.objects.filter(tenant=company, email="nuevo@acme.example").exists()
    assert any("n***@acme.example" in r.getMessage() for r in _lineas(caplog))


def test_con_el_correo_bien_la_respuesta_dice_que_salio(admin):
    client = APIClient()
    client.force_authenticate(admin)
    respuesta = client.post(
        reverse("employee-list"),
        {
            "email": "nuevo@acme.example",
            "first_name": "Nuevo",
            "last_name": "Operario",
            "role": Role.EMPLOYEE,
        },
        format="json",
    )
    assert respuesta.data["invitation_sent"] is True


@CORREO_CAIDO
def test_la_recuperacion_contesta_igual_aunque_el_correo_falle(marta, caplog):
    client = APIClient()

    with caplog.at_level(logging.WARNING):
        existe = client.post(
            reverse("auth:password-reset"), {"email": "marta@acme.example"}, format="json"
        )
    no_existe = client.post(
        reverse("auth:password-reset"), {"email": "nadie@acme.example"}, format="json"
    )

    assert existe.status_code == no_existe.status_code == 204
    assert any("m***@acme.example" in r.getMessage() for r in _lineas(caplog))
