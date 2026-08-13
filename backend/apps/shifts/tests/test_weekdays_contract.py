"""Omitir los días de la semana y mandarlos vacíos no son lo mismo.

Parecen el mismo caso y son opuestos. Omitir el campo es el atajo para «todo el
rango», que es de lo que va «Vaciar el mes». Mandarlo vacío es haber quitado
hasta el último día, y significa ninguno.

El serializador los igualaba con `default=list`, así que el segundo se leía como
el primero: quien desmarcaba todos los días del cuadrante y pulsaba «Asignar»
recibía turnos **los siete días**, sábados y domingos incluidos. Ni un aviso, y
lo contrario de lo que había pedido.

Salió en las pruebas de pantalla del 13/08/2026 --- apareció un turno el sábado
5 de diciembre --- y no lo cubría nada de aquí, que es por lo que este fichero
existe. Es un contrato de la API, no un detalle de la pantalla: un conector que
mande `weekdays: []` tiene el mismo derecho a que se le diga.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
MORNING = [{"start": "08:00", "end": "16:00"}]

#: Diciembre de 2026 entero: 31 días, de los que 23 son de lunes a viernes.
DESDE, HASTA = "2026-12-01", "2026-12-31"
DIAS_DEL_MES, DIAS_LABORABLES = 31, 23


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def jefa(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Luisa",
            role=Role.MANAGER,
        )


@pytest.fixture
def morning(company):
    with tenant_context(company.id):
        yield ShiftPattern.objects.create(tenant=company, name="Mañana", segments=MORNING)


def asignar(jefa, morning, **extra):
    client = APIClient()
    client.force_authenticate(user=jefa)
    return client.post(
        "/api/shifts/assign/",
        {
            "employees": [str(jefa.pk)],
            "pattern": str(morning.pk),
            "date_from": DESDE,
            "date_to": HASTA,
            **extra,
        },
        format="json",
    )


@pytest.mark.django_db
def test_omitir_los_dias_significa_todo_el_rango(company, jefa, morning):
    respuesta = asignar(jefa, morning)

    assert respuesta.status_code == 201
    with tenant_context(company.id):
        assert Shift.objects.filter(employee=jefa).count() == DIAS_DEL_MES


@pytest.mark.django_db
def test_mandar_los_dias_vacios_se_rechaza(company, jefa, morning):
    """El caso que se comía el sábado."""
    respuesta = asignar(jefa, morning, weekdays=[])

    # 409 y no 400: es la convención de `BusinessRuleError` en esta base, la
    # misma que usa `ends_before_it_starts` en esta misma vista.
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "no_weekdays"
    with tenant_context(company.id):
        assert Shift.objects.filter(employee=jefa).count() == 0


@pytest.mark.django_db
def test_de_lunes_a_viernes_deja_fuera_el_fin_de_semana(company, jefa, morning):
    respuesta = asignar(jefa, morning, weekdays=[0, 1, 2, 3, 4])

    assert respuesta.status_code == 201
    with tenant_context(company.id):
        puestos = Shift.objects.filter(employee=jefa)
        assert puestos.count() == DIAS_LABORABLES
        # Lunes es 0 y domingo 6: nada por encima de 4.
        assert all(turno.day.weekday() <= 4 for turno in puestos)


@pytest.mark.django_db
def test_vaciar_sin_dias_borra_el_mes_entero(company, jefa, morning):
    """«Vaciar el mes» omite el campo, y por eso alcanza a los siete días.

    Si algún día volviera a mandar `[]` esta prueba seguiría en verde y la de
    arriba no --- por eso están las dos: una fija el atajo y la otra el rechazo.
    """
    asignar(jefa, morning)
    client = APIClient()
    client.force_authenticate(user=jefa)

    respuesta = client.post(
        "/api/shifts/clear/",
        {"employees": [str(jefa.pk)], "date_from": DESDE, "date_to": HASTA},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["removed"] == DIAS_DEL_MES
    with tenant_context(company.id):
        assert Shift.objects.filter(employee=jefa).count() == 0


@pytest.mark.django_db
def test_vaciar_con_los_dias_vacios_tambien_se_rechaza(company, jefa, morning):
    """Mismo criterio en las dos puntas.

    Un borrado que entiende «ninguno» como «todos» es peor que una asignación
    que lo hace: lo que se lleva por delante no se recupera desde la pantalla.
    """
    asignar(jefa, morning)
    client = APIClient()
    client.force_authenticate(user=jefa)

    respuesta = client.post(
        "/api/shifts/clear/",
        {"employees": [str(jefa.pk)], "date_from": DESDE, "date_to": HASTA, "weekdays": []},
        format="json",
    )

    # 409 y no 400: es la convención de `BusinessRuleError` en esta base, la
    # misma que usa `ends_before_it_starts` en esta misma vista.
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "no_weekdays"
    with tenant_context(company.id):
        assert Shift.objects.filter(employee=jefa).count() == DIAS_DEL_MES
