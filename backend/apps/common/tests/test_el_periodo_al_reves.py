"""Un periodo que acaba antes de empezar se rechaza, no se contesta con cero.

No existe consulta legítima que vaya del 27 al 26: es siempre un dedo
equivocado o un guion que arma las fechas al revés. Devolver cero filas sin
decir nada es la peor respuesta, porque se lee como «no hubo actividad en ese
periodo» --- en el rastro de auditoría, justo la conclusión contraria a la
verdadera.

El producto ya lo rechazaba en el informe del art. 34.9 y en el cuadrante, cada
uno por su cuenta y con este mismo mensaje. Faltaba en el filtro que comparten
los listados de fichajes y del rastro, que es donde más barato sale creerse el
cero: ahí no hay un documento con el periodo escrito dentro, solo una tabla
vacía.

La mitad de este fichero es el contraste. Un filtro que rechazara de más sería
peor que el fallo: el mismo día en los dos extremos es la consulta más corriente
que existe.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
LISTADOS = ["/api/audit/", "/api/punches/"]


@pytest.fixture
def cliente(db):
    empresa = Tenant.objects.create(name="Rango SL", tax_id="B12121212", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="rango@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ra",
            last_name="Ngo",
            is_staff=True,
        )
        register_punch(employee=quien, company=empresa)
        api = APIClient()
        api.force_authenticate(user=quien)
        yield api, empresa


@pytest.mark.parametrize("ruta", LISTADOS)
@pytest.mark.django_db
def test_al_reves_se_rechaza(cliente, ruta):
    api, empresa = cliente
    with tenant_context(empresa.id):
        r = api.get(ruta, {"date_from": "2026-08-27", "date_to": "2026-08-26"})

    assert r.status_code == 400, (
        f"{ruta} contestó {r.status_code} a un periodo que acaba antes de empezar; "
        "cero filas sin avisar se lee como «no hubo actividad»"
    )
    assert "date_to" in str(r.json()), r.json()


@pytest.mark.parametrize("ruta", LISTADOS)
@pytest.mark.django_db
def test_el_mismo_dia_en_los_dos_extremos_sigue_valiendo(cliente, ruta):
    """El contraste que más importa: es la consulta más corriente que hay."""
    api, empresa = cliente
    with tenant_context(empresa.id):
        r = api.get(ruta, {"date_from": "2026-08-27", "date_to": "2026-08-27"})

    assert r.status_code == 200, r.content[:200]


@pytest.mark.parametrize("ruta", LISTADOS)
@pytest.mark.django_db
def test_un_extremo_suelto_no_molesta(cliente, ruta):
    """Pedir solo el principio, o solo el final, es legítimo y frecuente."""
    api, empresa = cliente
    with tenant_context(empresa.id):
        assert api.get(ruta, {"date_from": "2026-08-01"}).status_code == 200
        assert api.get(ruta, {"date_to": "2026-08-31"}).status_code == 200


@pytest.mark.django_db
def test_una_fecha_mal_escrita_sigue_dando_su_propio_error(cliente):
    """Adelantarse a `DateFilter` solo cambiaría un mensaje bueno por otro: el
    suyo nombra el campo y dice que la fecha no vale, que es más útil que
    hablar del orden de dos fechas cuando una de ellas no es una fecha."""
    api, empresa = cliente
    with tenant_context(empresa.id):
        r = api.get("/api/audit/", {"date_from": "ayer", "date_to": "2026-08-26"})

    assert r.status_code == 400
    assert "date_from" in str(r.json()), r.json()


@pytest.mark.django_db
def test_el_fichero_del_rastro_lo_rechaza_igual(cliente):
    """Es la misma consulta con otra salida: si la lista se planta, el fichero
    que se entrega no puede salir vacío y tan tranquilo."""
    api, empresa = cliente
    with tenant_context(empresa.id):
        r = api.get("/api/audit/export/", {"date_from": "2026-08-27", "date_to": "2026-08-26"})

    assert r.status_code == 400, r.content[:200]
