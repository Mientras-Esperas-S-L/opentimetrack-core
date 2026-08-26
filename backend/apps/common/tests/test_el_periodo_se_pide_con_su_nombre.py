"""Pedir un periodo con el nombre del endpoint vecino ya no devuelve otro.

El mismo concepto se llamaba de dos maneras en esta API: `date_from`/`date_to` en
los listados y en los informes ---lo pone `LocalDayRangeFilter`--- y `from`/`to`
en las horas extra, leídos a mano. Quien automatiza una descarga acierta en uno y
falla en el otro.

Y fallaba **en silencio**: lo desconocido se ignora, así que pedir un año con
`from`/`to` contestaba 200 con el periodo por defecto. En un listado es una
molestia; en el informe del art. 34.9 significa entregar el registro de un
periodo que nadie pidió, y el documento lleva el suyo escrito dentro pero quien
lo genera desde un guion no lo lee.

Lo encontré tropezando con él: medí «un año de la empresa» y estaba midiendo
treinta días.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def jefa(db):
    empresa = Tenant.objects.create(
        name="Periodos", tax_id="B90300001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )


def como(quien):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente


@pytest.mark.django_db
def test_el_informe_no_devuelve_otro_periodo_en_silencio(jefa):
    respuesta = como(jefa).get(
        "/api/reports/working-time/?from=2025-09-01&to=2026-08-31&format=csv"
    )

    assert respuesta.status_code == 400, "contestaba 200 con los últimos treinta días"
    # El nombre bueno tiene que ir en la respuesta: es lo único que hace falta
    # para arreglarlo.
    assert b"date_from" in respuesta.content


@pytest.mark.django_db
def test_y_con_el_nombre_bueno_sigue_funcionando(jefa):
    respuesta = como(jefa).get(
        "/api/reports/working-time/?date_from=2026-08-01&date_to=2026-08-31&format=csv"
    )
    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_los_listados_que_heredan_el_filtro_tambien(jefa):
    """Un solo sitio cubre todos los que usan `LocalDayRangeFilter`."""
    assert como(jefa).get("/api/punches/?from=2026-08-01").status_code == 400
    assert como(jefa).get("/api/punches/?date_from=2026-08-01").status_code == 200
    assert como(jefa).get("/api/audit/?to=2026-08-31").status_code == 400
    assert como(jefa).get("/api/audit/?date_to=2026-08-31").status_code == 200


@pytest.mark.django_db
def test_sin_periodo_no_se_rechaza_nada(jefa):
    """El guard solo salta con el nombre equivocado, no con su ausencia."""
    assert como(jefa).get("/api/punches/").status_code == 200
    assert como(jefa).get("/api/reports/working-time/?format=csv").status_code == 200


@pytest.mark.django_db
def test_y_si_van_los_dos_manda_el_bueno(jefa):
    """Un cliente que mande los dos no se queda fuera: se usa el canónico."""
    assert como(jefa).get("/api/punches/?from=2020-01-01&date_from=2026-08-01").status_code == 200
