"""El historial de ausencias se corta por el **periodo**, no por el año natural.

El propio docstring del filtro ya lo decía ---«se devengan y se disfrutan por
periodo»--- y luego filtraba de enero a diciembre. Con el mes de inicio por
defecto son lo mismo y no se notaba; con cualquier otro, que es lo que el
producto ofrece configurar, la pantalla se contradecía a la vista:

    Vacaciones · Periodo del 01 sept 2025 al 31 ago 2026
    24 días laborables de 24 · 0 disfrutados
    ...
    Historial · Año 2026
    Vacaciones 08 oct → 15 oct · 8 días · Aprobada
    Vacaciones 27 nov → 29 nov · 3 días · Aprobada

Las dos cosas eran ciertas y hablaban de ventanas distintas sin decirlo. Quien lo
lee ve «cero disfrutados» encima de dos vacaciones aprobadas.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def septiembre(db):
    """Una empresa cuyo periodo va de septiembre a agosto."""
    return Tenant.objects.create(
        name="Curso SL",
        tax_id="B33333333",
        time_zone="Europe/Madrid",
        country="ES",
        leave_year_start_month=9,
    )


@pytest.fixture
def enero(db):
    return Tenant.objects.create(
        name="Natural SL", tax_id="B33333334", time_zone="Europe/Madrid", country="ES"
    )


def alguien(empresa, correo="quien@example.com"):
    with tenant_context(empresa.id):
        return User.objects.create_user(
            email=correo, password=PASSWORD, tenant=empresa, first_name="Quien"
        )


def vacaciones(empresa, quien, desde, dias=3):
    with tenant_context(empresa.id):
        return request_absence(
            employee=quien,
            company=empresa,
            absence_type=AbsenceType.VACATION,
            start_date=desde,
            end_date=desde + timedelta(days=dias - 1),
            requested_by=quien,
        )


def pidiendo(quien, año):
    cliente = APIClient()
    cliente.force_authenticate(user=quien)
    respuesta = cliente.get("/api/absences/", {"year": año, "absence_type": "VACATION"})
    filas = respuesta.data["results"] if isinstance(respuesta.data, dict) else respuesta.data
    return {f["start_date"] for f in filas}


@pytest.mark.django_db
def test_el_ano_pedido_es_el_periodo_que_empieza_en_el(septiembre):
    """**El caso que destapó la contradicción.**

    Octubre de 2026 pertenece al periodo que arranca en septiembre de 2026, no
    al que arranca en septiembre de 2025 --- que es el que el saldo enseñaba
    mientras el historial las sacaba.
    """
    quien = alguien(septiembre)
    vacaciones(septiembre, quien, date(2025, 10, 6))
    vacaciones(septiembre, quien, date(2026, 10, 6))

    assert pidiendo(quien, 2025) == {"2025-10-06"}
    assert pidiendo(quien, 2026) == {"2026-10-06"}


@pytest.mark.django_db
def test_agosto_y_septiembre_caen_en_periodos_distintos(septiembre):
    """El borde exacto: el 31 de agosto cierra uno y el 1 de septiembre abre el
    siguiente. Un fallo de un día aquí manda las vacaciones de todo un verano al
    saldo que no es."""
    quien = alguien(septiembre)
    vacaciones(septiembre, quien, date(2026, 8, 29), dias=1)
    vacaciones(septiembre, quien, date(2026, 9, 1), dias=1)

    assert pidiendo(quien, 2025) == {"2026-08-29"}
    assert pidiendo(quien, 2026) == {"2026-09-01"}


@pytest.mark.django_db
def test_con_el_periodo_natural_no_cambia_nada(enero):
    """El contraste que protege a la inmensa mayoría: con el mes por defecto,
    periodo y año natural son lo mismo y esta pantalla se queda igual."""
    quien = alguien(enero)
    vacaciones(enero, quien, date(2025, 10, 6))
    vacaciones(enero, quien, date(2026, 10, 6))

    assert pidiendo(quien, 2025) == {"2025-10-06"}
    assert pidiendo(quien, 2026) == {"2026-10-06"}


@pytest.mark.django_db
def test_lo_que_cruza_el_corte_sale_en_los_dos_periodos(septiembre):
    """Por solape, como ya hacía con el año natural.

    Unas vacaciones del 29 de agosto al 4 de septiembre son siete días de los que
    cuatro caen en el periodo siguiente. Filtrando por la fecha de inicio no
    saldrían al pedir el que viene, y quien las está disfrutando no las
    encontraría en su propia lista.
    """
    quien = alguien(septiembre)
    vacaciones(septiembre, quien, date(2026, 8, 29), dias=7)

    assert pidiendo(quien, 2025) == {"2026-08-29"}
    assert pidiendo(quien, 2026) == {"2026-08-29"}


@pytest.mark.django_db
def test_el_corte_es_el_de_la_empresa_de_quien_pregunta(septiembre, enero):
    """Y no el de la primera que haya. Dos empresas con periodos distintos y la
    misma fecha: cada una la ve en el año que le toca."""
    suyo = alguien(septiembre, "curso@example.com")
    otro = alguien(enero, "natural@example.com")
    vacaciones(septiembre, suyo, date(2026, 10, 6))
    vacaciones(enero, otro, date(2026, 10, 6))

    # En la de septiembre, octubre de 2026 abre el periodo 2026; en la natural,
    # cierra el año 2026. Misma fecha, dos respuestas, las dos correctas.
    assert pidiendo(suyo, 2026) == {"2026-10-06"}
    assert pidiendo(suyo, 2025) == set()
    assert pidiendo(otro, 2026) == {"2026-10-06"}


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(septiembre, enero):
    suyo = alguien(septiembre, "curso2@example.com")
    otro = alguien(enero, "natural2@example.com")
    vacaciones(enero, otro, date(2026, 10, 6))

    assert pidiendo(suyo, 2026) == set(), "ve las de otra empresa"
