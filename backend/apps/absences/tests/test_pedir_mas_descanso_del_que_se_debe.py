"""Pedir más descanso compensatorio del que consta que se debe.

El catálogo no le pone cifra a este permiso, y hace bien: el art. 35.1 no da
ninguna ---lo que se devuelve lo fija lo que se debe, y cuatro horas extra son
cuatro horas de descanso---. **Pero el producto sí sabe la cifra**: es el saldo.

Sin esta comprobación la calculaba, la enseñaba en la pantalla de quien la
disfruta, y no la usaba en el único sitio donde decide algo. Medido en la
demostración: con veinticuatro horas debidas se podían pedir diez días seguidos
y ni quien los pedía ni quien los aprobaba veía nada.

**Avisa, no impide**, y aquí eso importa más que de costumbre: el saldo que
sirve de referencia es incompleto **por diseño** ---los descansos por ampliación
sectorial están fuera a propósito y el convenio puede dar más---, así que negarse
a registrar un descanso por esa cifra sería usar una parcial como si fuera la ley.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from freezegun import freeze_time

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence, rest_debt_over_the_balance
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)


@pytest.fixture
def empresa(db):
    compania = Tenant.objects.create(
        name="Deudas SL", tax_id="B44444444", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(compania.id):
        reglas = WorkingTimeRules.for_company(compania)
        reglas.night_worked_compensation = WorkingTimeRules.NIGHT_REST
        reglas.save(update_fields=["night_worked_compensation"])
    return compania


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="deudora@example.com", password=PASSWORD, tenant=empresa, first_name="Quien"
        )
        # Ocho horas de noche: ocho horas de deuda, y ni una más.
        entra = datetime.combine(date(2026, 8, 17), datetime.min.time(), tzinfo=UTC).replace(
            hour=20
        )
        for momento, kind in ((entra, PunchType.IN), (entra + timedelta(hours=8), PunchType.OUT)):
            Punch.objects.create(
                tenant=empresa,
                employee=persona,
                timestamp=momento,
                punch_type=kind,
                interval=PunchInterval.WORK,
            )
        yield persona


@pytest.fixture
def catalogo(empresa):
    from apps.absences.catalogue import seed_leave_types

    with tenant_context(empresa.id):
        seed_leave_types(empresa)


def con_turnos(empresa, quien, desde, dias, horas=8):
    """Turnos previstos, que es de donde sale cuánto vale un día de descanso."""
    for i in range(dias):
        Shift.objects.update_or_create(
            tenant=empresa,
            employee=quien,
            day=desde + timedelta(days=i),
            defaults={"segments": [{"start": "09:00", "end": f"{9 + horas:02d}:00"}]},
        )


def pide(empresa, quien, desde, dias, catalogo_tipo):
    return request_absence(
        employee=quien,
        company=empresa,
        absence_type=AbsenceType.PAID_LEAVE,
        leave_type=catalogo_tipo,
        start_date=desde,
        end_date=desde + timedelta(days=dias - 1),
        requested_by=quien,
    )


@pytest.fixture
def descanso(empresa, catalogo):
    from apps.absences.models import LeaveType

    with tenant_context(empresa.id):
        return LeaveType.objects.get(code="es.compensatory_rest")


@pytest.mark.django_db
@freeze_time(HOY)
def test_pedir_mas_de_lo_debido_avisa(empresa, quien, descanso):
    """**El agujero.** Ocho horas debidas, tres días pedidos con turno de ocho:
    veinticuatro horas contra ocho."""
    with tenant_context(empresa.id):
        desde = HOY + timedelta(days=3)
        con_turnos(empresa, quien, desde, 3)
        aviso = rest_debt_over_the_balance(pide(empresa, quien, desde, 3, descanso))

    assert aviso["kind"] == "rest_debt"
    assert aviso["asked_hours"] == 24
    assert aviso["owed_hours"] == 8


@pytest.mark.django_db
@freeze_time(HOY)
def test_pedir_lo_que_cabe_no_avisa(empresa, quien, descanso):
    """El contraste. Un día de ocho horas contra ocho horas debidas es
    exactamente lo que se debe, y avisar ahí enseñaría a ignorar el aviso."""
    with tenant_context(empresa.id):
        desde = HOY + timedelta(days=3)
        con_turnos(empresa, quien, desde, 1)

        assert rest_debt_over_the_balance(pide(empresa, quien, desde, 1, descanso)) is None


@pytest.mark.django_db
@freeze_time(HOY)
def test_sin_turno_previsto_no_se_calla(empresa, quien, descanso):
    """**El segundo hallazgo, y salió al verificar el arreglo.**

    Un día entero de descanso vale lo que ese día tocaba trabajar, y eso sale del
    cuadrante. Quien pide con un mes de antelación ---lo normal, y lo que la ley
    fomenta--- pide días que todavía no tienen turno, así que la primera versión
    devolvía `None` justo ahí: el aviso solo aparecía en las peticiones de última
    hora.

    No se estima lo que no se sabe: `asked_hours` va nulo y se dicen los días.
    """
    with tenant_context(empresa.id):
        # Sin turnos: nada que convertir.
        aviso = rest_debt_over_the_balance(
            pide(empresa, quien, HOY + timedelta(days=30), 10, descanso)
        )

    assert aviso is not None, "se calla cuando no puede contar las horas"
    assert aviso["asked_hours"] is None, "no debe estimar horas que no sabe"
    assert aviso["unconverted_days"] == 10
    assert aviso["owed_hours"] == 8


@pytest.mark.django_db
@freeze_time(HOY)
def test_lo_convertido_y_lo_que_no_van_por_separado(empresa, quien, descanso):
    """Con parte del rango en el cuadrante y parte no, se dicen las dos cosas: las
    horas que se han podido contar y los días que no. Sumarlos con una jornada
    tipo daría una cifra con aire de dato."""
    with tenant_context(empresa.id):
        desde = HOY + timedelta(days=3)
        con_turnos(empresa, quien, desde, 2)
        aviso = rest_debt_over_the_balance(pide(empresa, quien, desde, 5, descanso))

    assert aviso["asked_hours"] == 16
    assert aviso["unconverted_days"] == 3


@pytest.mark.django_db
@freeze_time(HOY)
def test_sin_ninguna_deuda_cualquier_peticion_avisa(empresa, catalogo, descanso):
    """Quien no tiene ninguna deuda pidiendo descanso compensatorio: no hay saldo
    del que descontarlo, y el aviso dice cero en vez de callarse."""
    with tenant_context(empresa.id):
        nadie = User.objects.create_user(
            email="sindeuda@example.com", password=PASSWORD, tenant=empresa, first_name="Sin"
        )
        desde = HOY + timedelta(days=3)
        con_turnos(empresa, nadie, desde, 1)
        aviso = rest_debt_over_the_balance(pide(empresa, nadie, desde, 1, descanso))

    assert aviso["owed_hours"] == 0
    assert aviso["asked_hours"] == 8


@pytest.mark.django_db
@freeze_time(HOY)
def test_otros_permisos_no_lo_llevan(empresa, quien, catalogo):
    """El contraste que acota. Este saldo es del descanso compensatorio y de nada
    más: aplicárselo a unas vacaciones o a una mudanza sería inventarles un tope
    que no tienen."""
    from apps.absences.models import LeaveType

    with tenant_context(empresa.id):
        desde = HOY + timedelta(days=3)
        con_turnos(empresa, quien, desde, 5)
        otro = LeaveType.objects.exclude(code="es.compensatory_rest").filter(amount=None).first()
        assert otro is not None, "el catálogo ya no tiene otro permiso sin tope"

        assert rest_debt_over_the_balance(pide(empresa, quien, desde, 5, otro)) is None


@pytest.mark.django_db
@freeze_time(HOY)
def test_el_aviso_llega_por_el_mismo_canal_que_el_tope_del_catalogo(empresa, quien, descanso):
    """En `over_the_limit`, que es lo que ven quien pide y quien decide.

    Un canal nuevo habría dejado la pantalla de decidir sin enterarse, que es
    exactamente como estaba.
    """
    from rest_framework.test import APIClient

    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            role=Role.MANAGER,
        )
        desde = HOY + timedelta(days=3)
        con_turnos(empresa, quien, desde, 3)
        absence = pide(empresa, quien, desde, 3, descanso)

    cliente = APIClient()
    cliente.force_authenticate(user=jefa)
    respuesta = cliente.get(f"/api/absences/{absence.id}/")

    assert respuesta.status_code == 200
    assert respuesta.data["over_the_limit"]["kind"] == "rest_debt"
    assert respuesta.data["over_the_limit"]["owed_hours"] == 8
