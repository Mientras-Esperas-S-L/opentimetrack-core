"""Art. 36.1 ET: «Los trabajadores nocturnos no podrán realizar horas
extraordinarias.»

Es de las pocas prohibiciones del capítulo --- casi todo lo demás son suelos y
techos que el convenio puede mejorar. Y el producto la nombraba sin vigilarla:
el aviso del cuadrante decía que la condición de trabajador nocturno «trae una
media de ocho horas, una prohibición de horas extra y una evaluación de salud»,
y luego la cola de «Por decidir» autorizaba esas horas sin que nada la
mencionara. `holds_night_worker_status` existía y se usaba en un solo sitio.

Se avisa, no se impide, y aquí el motivo es más fuerte que de costumbre: las
horas ya se trabajaron. Negarse a clasificarlas dejaría fuera del registro unas
horas que existen, que es justo lo contrario de lo que el art. 34.9 busca. Lo
que hay que hacer es que quien decide lo sepa, y que quede por escrito.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from apps.common.models import tenant_context
from apps.punches.overtime import pending_overtime
from apps.punches.services import register_punch
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.users.models import NightWorkerStatus, User

PASSWORD = "a-sufficiently-long-password"
DIA = date(2026, 9, 8)


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def _persona(empresa, correo, *, nocturno):
    return User.objects.create_user(
        email=correo,
        password=PASSWORD,
        tenant=empresa,
        first_name="Quien",
        last_name="Sea",
        night_worker=nocturno,
    )


def _un_dia_con_horas_de_mas(empresa, quien, *, turno, entra, sale):
    """Un turno planificado y una jornada que se pasa de él."""
    Shift.objects.create(tenant=empresa, employee=quien, day=DIA, segments=turno)
    with freeze_time(entra):
        register_punch(employee=quien, company=empresa)
    with freeze_time(sale):
        register_punch(employee=quien, company=empresa)


def _cola(empresa):
    return pending_overtime(
        company=empresa, first=DIA - timedelta(days=1), last=DIA + timedelta(days=1)
    )


@pytest.mark.django_db
def test_la_cola_dice_que_esa_persona_es_trabajadora_nocturna(empresa):
    with tenant_context(empresa.id):
        quien = _persona(empresa, "noche@example.com", nocturno=NightWorkerStatus.YES)
        # El día que se pasa es de jornada diurna a propósito: una jornada de
        # noche **no llega siquiera a la cola**, porque la reconciliación no le
        # atribuye horas al cruzar la medianoche. Eso está anotado como hallazgo
        # abierto y es más gordo que esto; aquí se prueba el veto, no aquello.
        _un_dia_con_horas_de_mas(
            empresa,
            quien,
            turno=[{"start": "08:00", "end": "16:00"}],
            entra="2026-09-08 07:55:00",
            sale="2026-09-08 18:00:00",
        )

        filas = _cola(empresa)

    assert len(filas) == 1, filas
    assert filas[0]["minutes"] > 0
    assert filas[0]["night_worker"] is True


@pytest.mark.django_db
def test_quien_no_lo_es_no_arrastra_el_aviso(empresa):
    """El contraste, y el que hace que el aviso valga: si saliera para todos,
    en dos semanas nadie lo miraría."""
    with tenant_context(empresa.id):
        quien = _persona(empresa, "dia@example.com", nocturno=NightWorkerStatus.NO)
        _un_dia_con_horas_de_mas(
            empresa,
            quien,
            turno=[{"start": "08:00", "end": "16:00"}],
            entra="2026-09-08 07:55:00",
            sale="2026-09-08 18:00:00",
        )

        filas = _cola(empresa)

    assert len(filas) == 1, filas
    assert filas[0]["night_worker"] is False


@pytest.mark.django_db
def test_la_respuesta_de_la_empresa_manda_sobre_el_cuadrante(empresa):
    """Alguien de noche a quien la empresa declara **no** nocturno.

    No es un agujero: la condición se define por lo que se hace *normalmente*, y
    un mes de cuadrante es peor testigo de «normalmente» que el contrato. El
    cuadrante sigue avisando por su cuenta de que el patrón está ahí, así que la
    respuesta de la empresa queda a la vista en vez de tapar nada.
    """
    with tenant_context(empresa.id):
        quien = _persona(empresa, "declarado@example.com", nocturno=NightWorkerStatus.NO)
        _un_dia_con_horas_de_mas(
            empresa,
            quien,
            turno=[{"start": "08:00", "end": "16:00"}],
            entra="2026-09-08 07:55:00",
            sale="2026-09-08 18:00:00",
        )

        assert _cola(empresa)[0]["night_worker"] is False


@pytest.mark.django_db
def test_sin_respuesta_lo_lee_del_cuadrante(empresa):
    """En «automático», la prueba es la del artículo: tres horas de la jornada
    dentro de la ventana, y de forma habitual."""
    with tenant_context(empresa.id):
        quien = _persona(empresa, "auto@example.com", nocturno=NightWorkerStatus.AUTO)
        # Cuadrante nocturno: catorce noches y un día suelto, que es el que se
        # pasa de horas. La condición se lee del cuadrante, y ahí la mayoría
        # manda.
        for dia in range(1, 16):
            nocturno = [{"start": "22:00", "end": "06:00"}]
            diurno = [{"start": "08:00", "end": "16:00"}]
            Shift.objects.create(
                tenant=empresa,
                employee=quien,
                day=date(2026, 9, dia),
                segments=diurno if dia == 8 else nocturno,
            )
        with freeze_time("2026-09-08 07:55:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-08 18:00:00"):
            register_punch(employee=quien, company=empresa)

        filas = pending_overtime(company=empresa, first=date(2026, 9, 1), last=date(2026, 9, 15))

    assert filas, "no hubo horas extra que decidir"
    assert filas[0]["night_worker"] is True
