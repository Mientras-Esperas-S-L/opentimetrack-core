"""Alguien se va y su cuadrante del mes que viene sigue hecho.

Lo que pasaba: nada. Cinco turnos futuros, se da de baja a la persona, y los
cinco seguían asignados sin que nada dijera una palabra. Comprobado con una
sonda antes de tocar nada.

Las dos piezas no se hablaban. La baja pone `is_active = False` y escribe la
línea del rastro; la revisión del cuadrante razona por fechas de contrato y se
salta a quien no tiene ninguna ---o sea, a toda la plantilla indefinida---.
`is_engaged_on` tampoco mira `is_active`.

Y no es un detalle cosmético: el cuadrante es contra lo que se comparan los
fichajes, así que quien se fue iba a salir como ausencia sin justificar todos
los días hasta que alguien lo mirara a mano.

Lo que faltaba no era una comprobación sino **una fecha**. `is_active` es un sí
o un no sin día, y nada de lo que razona por fechas puede hacer nada con eso.
Al dar de baja se escribe el último día que la relación cubre, y a partir de ahí
la comprobación que ya existía funciona sola.

Los turnos no se borran: la pantalla promete que dar de baja no borra nada, y
esa promesa incluye esto. Se marcan.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.clock import local_today
from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def jefa(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Luisa",
            role=Role.ADMIN,
        )


@pytest.fixture
def se_va(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="sevaa@example.com", password=PASSWORD, tenant=empresa, first_name="Chelo"
        )


def _con_turnos(empresa, quien, desde: date, cuantos: int = 5):
    for i in range(cuantos):
        Shift.objects.create(
            tenant=empresa,
            employee=quien,
            day=desde + timedelta(days=i),
            segments=[{"start": "08:00", "end": "16:00"}],
        )


def _dar_de_baja(jefa, quien) -> int:
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(jefa).access_token}")
    return cliente.delete(f"/api/employees/{quien.id}/").status_code


@pytest.mark.django_db
def test_la_baja_deja_escrito_el_ultimo_dia(empresa, jefa, se_va):
    with tenant_context(empresa.id):
        assert _dar_de_baja(jefa, se_va) in (200, 204)
        se_va.refresh_from_db()

    assert se_va.is_active is False
    assert se_va.contract_end == local_today(empresa), "una baja sin fecha no se puede responder"


@pytest.mark.django_db
def test_el_cuadrante_marca_los_turnos_de_quien_ya_no_esta(empresa, jefa, se_va):
    """El fallo, tal cual. Antes la revisión no sacaba nada."""
    manana = local_today(empresa) + timedelta(days=10)
    with tenant_context(empresa.id):
        _con_turnos(empresa, se_va, manana)
        _dar_de_baja(jefa, se_va)

        hallazgos = review_roster(company=empresa, first=manana, last=manana + timedelta(days=6))

    fuera = [h for h in hallazgos if h.code == "outside_the_contract"]
    assert len(fuera) == 5, "los turnos de quien se fue no se marcan"


@pytest.mark.django_db
def test_pero_los_turnos_no_se_borran(empresa, jefa, se_va):
    """La promesa de la pantalla es que dar de baja no borra nada.

    Y aquí importa más de lo que parece: borrar el cuadrante de quien se va
    dejaría sin explicar los fichajes que esa persona sí hizo antes de irse.
    """
    manana = local_today(empresa) + timedelta(days=10)
    with tenant_context(empresa.id):
        _con_turnos(empresa, se_va, manana)
        _dar_de_baja(jefa, se_va)

        assert Shift.objects.filter(employee=se_va, day__gte=manana).count() == 5


@pytest.mark.django_db
def test_un_contrato_que_ya_habia_terminado_no_se_pisa(empresa, jefa, se_va):
    """La fecha se pone si falta o si es posterior, no siempre.

    Un temporal que venció en marzo y se da de baja en agosto terminó en marzo:
    escribir agosto diría que estuvo contratado cinco meses de más, y eso es
    justo lo que el registro no puede decir.
    """
    marzo = date(2026, 3, 31)
    with tenant_context(empresa.id):
        se_va.contract_end = marzo
        se_va.save(update_fields=["contract_end"])
        _dar_de_baja(jefa, se_va)
        se_va.refresh_from_db()

    assert se_va.contract_end == marzo


@pytest.mark.django_db
def test_y_uno_que_vencia_mas_adelante_si(empresa, jefa, se_va):
    """El contraste del de arriba. Irse antes de que venza el contrato es lo
    corriente ---una baja voluntaria, un despido--- y lo que la fecha tiene que
    decir es el último día que la relación cubre de verdad."""
    with tenant_context(empresa.id):
        se_va.contract_end = local_today(empresa) + timedelta(days=90)
        se_va.save(update_fields=["contract_end"])
        _dar_de_baja(jefa, se_va)
        se_va.refresh_from_db()

    assert se_va.contract_end == local_today(empresa)


@pytest.mark.django_db
def test_quien_sigue_de_alta_no_recibe_ningun_aviso(empresa, jefa, se_va):
    """El contraste que impide que esto marque el cuadrante entero.

    Sin él, la comprobación pasaría igual si `outside_the_contract` se hubiera
    vuelto loca y estuviera señalando a todo el mundo.
    """
    manana = local_today(empresa) + timedelta(days=10)
    with tenant_context(empresa.id):
        _con_turnos(empresa, se_va, manana)
        hallazgos = review_roster(company=empresa, first=manana, last=manana + timedelta(days=6))

    assert not [h for h in hallazgos if h.code == "outside_the_contract"]


@pytest.mark.django_db
def test_la_baja_queda_contada_en_el_rastro(empresa, jefa, se_va, django_capture_on_commit_callbacks):
    """Cuántos turnos quedaban colgando, dicho en el momento de la baja.

    Es el dato que quien administra necesita para saber si tiene que ir a
    rehacer un cuadrante, y el momento de la baja es cuando lo va a leer.
    """
    from apps.audit.models import AuditLog

    manana = local_today(empresa) + timedelta(days=10)
    with tenant_context(empresa.id):
        _con_turnos(empresa, se_va, manana)
        with django_capture_on_commit_callbacks(execute=True):
            _dar_de_baja(jefa, se_va)

        entradas = [e for e in AuditLog.objects.all() if e.changes.get("future_shifts") is not None]

    assert entradas, "la baja no dejó constancia de los turnos pendientes"
    assert entradas[0].changes["future_shifts"] == 5
