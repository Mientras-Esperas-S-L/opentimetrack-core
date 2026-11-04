"""La entrada que se quedó sin salida, dicha antes de pulsar.

El caso real, del 31/10/2026: alguien entró el viernes a las 08:03 y no fichó la
salida. El sábado por la tarde abrió la pantalla para cerrar el viernes y pedir
la corrección. El botón decía «Fichar entrada» ---pasado el tope, el viernes ya
no cuenta como abierto, y eso está bien--- y pulsó. Se le abrió una jornada el
sábado, un día que no trabajó, y la tuvo que cerrar al minuto.

Lo que faltaba no era otra regla de entrada o salida, sino decirlo: que la
pantalla sepa que hay una entrada sin cerrar y lo avise antes del toque.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, CorrectionStatus, PunchCorrection
from apps.punches.models import PunchType
from apps.punches.services import register_punch, unclosed_clock_in
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="olvido@example.com", password=PASSWORD, tenant=empresa, first_name="Ana"
        )


def _entra_el_viernes_y_no_sale(empresa, quien):
    # 08:03 de Madrid del viernes 30/10/2026, que en UTC son las 07:03.
    with freeze_time("2026-10-30 07:03:00"):
        return register_punch(employee=quien, company=empresa)


@pytest.mark.django_db
def test_el_sabado_se_ve_la_entrada_del_viernes(empresa, quien):
    with tenant_context(empresa.id):
        entrada = _entra_el_viernes_y_no_sale(empresa, quien)
        with freeze_time("2026-10-31 16:46:00"):
            assert unclosed_clock_in(quien) == entrada


@pytest.mark.django_db
def test_la_pantalla_de_fichar_lo_recibe(empresa, quien):
    with tenant_context(empresa.id):
        _entra_el_viernes_y_no_sale(empresa, quien)
    cliente = APIClient()
    cliente.force_authenticate(quien)
    with freeze_time("2026-10-31 16:46:00"):
        respuesta = cliente.get("/api/punches/today/")

    assert respuesta.status_code == 200
    assert respuesta.data["state"] == "NOT_STARTED"
    assert respuesta.data["unclosed"]["workday"] == "2026-10-30"
    assert respuesta.data["unclosed"]["timestamp"].startswith("2026-10-30T07:03")


@pytest.mark.django_db
def test_y_sigue_avisando_despues_de_abrir_otra_jornada(empresa, quien):
    """Si pulsa igual, el olvido del viernes sigue ahí: abrir el sábado no lo
    cierra, así que el aviso tampoco se va."""
    with tenant_context(empresa.id):
        entrada = _entra_el_viernes_y_no_sale(empresa, quien)
        with freeze_time("2026-10-31 16:46:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-10-31 16:47:00"):
            assert unclosed_clock_in(quien) == entrada


@pytest.mark.django_db
def test_la_jornada_en_curso_no_es_un_olvido(empresa, quien):
    """Dentro del tope la entrada es la de ahora: avisar sería decir «se te
    olvidó salir» a quien está trabajando."""
    with tenant_context(empresa.id):
        _entra_el_viernes_y_no_sale(empresa, quien)
        with freeze_time("2026-10-30 15:00:00"):
            assert unclosed_clock_in(quien) is None


@pytest.mark.django_db
def test_una_jornada_cerrada_no_avisa(empresa, quien):
    with tenant_context(empresa.id):
        _entra_el_viernes_y_no_sale(empresa, quien)
        with freeze_time("2026-10-30 15:30:00"):
            salida = register_punch(employee=quien, company=empresa)
        with freeze_time("2026-10-31 16:46:00"):
            assert salida.punch_type == PunchType.OUT
            assert unclosed_clock_in(quien) is None


@pytest.mark.django_db
def test_pedida_la_salida_deja_de_avisar(empresa, quien):
    """Pedida y sin resolver, el aviso empujaría a pedirla otra vez."""
    with tenant_context(empresa.id):
        entrada = _entra_el_viernes_y_no_sale(empresa, quien)
        PunchCorrection.objects.create(
            tenant=empresa,
            employee=quien,
            requested_by=quien,
            kind=CorrectionKind.ADD,
            proposed_type=PunchType.OUT,
            proposed_timestamp=entrada.timestamp + timedelta(hours=8),
            reason="Olvidé fichar la salida",
        )
        with freeze_time("2026-10-31 16:46:00"):
            assert unclosed_clock_in(quien) is None


@pytest.mark.django_db
def test_rechazada_la_peticion_vuelve_a_avisar(empresa, quien):
    """El contraste: una petición rechazada no cierra nada."""
    with tenant_context(empresa.id):
        entrada = _entra_el_viernes_y_no_sale(empresa, quien)
        PunchCorrection.objects.create(
            tenant=empresa,
            employee=quien,
            requested_by=quien,
            kind=CorrectionKind.ADD,
            proposed_type=PunchType.OUT,
            proposed_timestamp=entrada.timestamp + timedelta(hours=8),
            reason="Olvidé fichar la salida",
            status=CorrectionStatus.REJECTED,
        )
        with freeze_time("2026-10-31 16:46:00"):
            assert unclosed_clock_in(quien) == entrada


@pytest.mark.django_db
def test_pasada_la_semana_ya_no_se_avisa(empresa, quien):
    with tenant_context(empresa.id):
        _entra_el_viernes_y_no_sale(empresa, quien)
        with freeze_time("2026-11-07 08:00:00"):
            assert unclosed_clock_in(quien) is None
