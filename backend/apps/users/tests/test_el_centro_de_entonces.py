"""En qué centro de trabajo estaba alguien cuando hizo esas horas.

Del centro cuelgan tres cosas que no son organizativas sino del sitio: los dos festivos
locales (art. 34.6 ET, el calendario laboral es del centro), la zona en la que se lee
su jornada, y dónde una inspección pide el registro.

Sin historial, el día que alguien se traslada esas tres cosas se le reescriben **hacia
atrás**: sus festivos de marzo pasan a ser los del centro nuevo, y el informe de un mes
ya cerrado deja de decir lo que decía. Eso es lo que se fija aquí.

No es el desplazamiento de un día ---quien va al municipio de al lado conserva sus
festivos--- sino el traslado de quien cambia de centro para quedarse.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.common.models import tenant_context
from apps.tenants.holidays import PublicHoliday, holidays_by_workplace, holidays_for
from apps.tenants.models import Tenant
from apps.users.models import User, Workplace, WorkplaceAssignment
from apps.users.workplace_history import (
    people_in_workplace,
    workplace_on,
    workplaces_by_person,
)

PASSWORD = "a-sufficiently-long-password"
MARZO = (date(2026, 3, 1), date(2026, 3, 31))


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def sitios(company):
    with tenant_context(company.id):
        ronda = Workplace.objects.create(
            tenant=company, name="Ronda", municipality="Ronda", region="ES-AN"
        )
        cadiz = Workplace.objects.create(
            tenant=company, name="Cádiz", municipality="Cádiz", region="ES-AN"
        )
        return ronda, cadiz


@pytest.fixture
def rosa(company, sitios):
    ronda, _cadiz = sitios
    with tenant_context(company.id):
        return User.objects.create_user(
            email="rosa@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="EMP-0042",
            workplace=ronda,
        )


def trasladar(quien, destino, *, el):
    """Un traslado como lo haría quien lo gestiona: cambiar el centro y anotarlo."""
    quien.workplace = destino
    quien.save(update_fields=["workplace"])
    # La señal ya lo anotó con la fecha de hoy; el traslado tiene su propia fecha.
    WorkplaceAssignment.objects.filter(employee=quien, ends_on__isnull=True).update(starts_on=el)
    WorkplaceAssignment.objects.filter(employee=quien, ends_on__isnull=False).update(
        ends_on=date(el.year, el.month, el.day - 1)
    )


# ------------------------------------------------------------- lo que consta


@pytest.mark.django_db
def test_al_darse_de_alta_queda_una_asignacion_sin_fecha(company, rosa, sitios):
    """«No consta desde cuándo»: del pasado no hay dato y no se inventa."""
    ronda, _ = sitios
    with tenant_context(company.id):
        tramos = list(WorkplaceAssignment.objects.filter(employee=rosa))

    assert len(tramos) == 1
    assert tramos[0].workplace_id == ronda.id
    assert tramos[0].starts_on is None
    assert tramos[0].ends_on is None


@pytest.mark.django_db
def test_guardar_sin_tocar_el_centro_no_crea_tramos(company, rosa):
    with tenant_context(company.id):
        rosa.first_name = "Rosa María"
        rosa.save()
        rosa.save()
        assert WorkplaceAssignment.objects.filter(employee=rosa).count() == 1


@pytest.mark.django_db
def test_el_traslado_cierra_uno_y_abre_otro(company, rosa, sitios):
    ronda, cadiz = sitios
    with tenant_context(company.id):
        trasladar(rosa, cadiz, el=date(2026, 4, 15))
        tramos = sorted(
            WorkplaceAssignment.objects.filter(employee=rosa),
            key=lambda t: t.starts_on or date.min,
        )

    assert [t.workplace_id for t in tramos] == [ronda.id, cadiz.id]
    assert tramos[0].ends_on == date(2026, 4, 14), "se cierra el día anterior"
    assert tramos[1].starts_on == date(2026, 4, 15)
    assert tramos[1].ends_on is None


# ------------------------------------------------------- el centro de un día


@pytest.mark.django_db
def test_el_centro_de_un_dia_anterior_al_traslado_es_el_de_entonces(company, rosa, sitios):
    ronda, cadiz = sitios
    with tenant_context(company.id):
        trasladar(rosa, cadiz, el=date(2026, 4, 15))

        assert workplace_on(rosa, date(2026, 3, 10)).id == ronda.id
        assert workplace_on(rosa, date(2026, 4, 14)).id == ronda.id
        assert workplace_on(rosa, date(2026, 4, 15)).id == cadiz.id
        assert workplace_on(rosa, date(2026, 6, 1)).id == cadiz.id


@pytest.mark.django_db
def test_quien_no_tiene_historial_se_resuelve_con_el_de_hoy(company, sitios):
    """Nadie pierde nada por haberse estrenado el historial ayer."""
    ronda, _ = sitios
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="sin@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="EMP-0099",
            workplace=ronda,
        )
        WorkplaceAssignment.objects.filter(employee=quien).delete()

        assert workplace_on(quien, date(2020, 1, 1)).id == ronda.id


# ------------------------------------------------------------- los festivos


@pytest.mark.django_db
def test_los_festivos_de_marzo_no_cambian_porque_te_trasladen_en_abril(company, rosa, sitios):
    """El caso que da nombre a todo esto."""
    ronda, cadiz = sitios
    with tenant_context(company.id):
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 3, 12), name="Feria de Ronda", workplace=ronda
        )
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 3, 20), name="Carnaval de Cádiz", workplace=cadiz
        )

        antes = holidays_for(rosa, *MARZO)
        assert antes == {date(2026, 3, 12)}, "en marzo estaba en Ronda"

        trasladar(rosa, cadiz, el=date(2026, 4, 15))
        despues = holidays_for(rosa, *MARZO)

    assert despues == antes, "marzo sigue siendo marzo después del traslado"


@pytest.mark.django_db
def test_el_mes_del_traslado_lleva_los_dos_centros(company, rosa, sitios):
    ronda, cadiz = sitios
    with tenant_context(company.id):
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 4, 3), name="Fiesta de Ronda", workplace=ronda
        )
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 4, 28), name="Fiesta de Cádiz", workplace=cadiz
        )
        PublicHoliday.objects.create(tenant=company, day=date(2026, 4, 1), name="De la empresa")
        trasladar(rosa, cadiz, el=date(2026, 4, 15))

        suyos = holidays_for(rosa, date(2026, 4, 1), date(2026, 4, 30))

    assert suyos == {date(2026, 4, 1), date(2026, 4, 3), date(2026, 4, 28)}


@pytest.mark.django_db
def test_lo_mismo_con_los_festivos_traidos_de_una_vez(company, rosa, sitios):
    """La otra vía de `holidays_for`, la que usa el cuadrante para no hacer N+1."""
    ronda, cadiz = sitios
    with tenant_context(company.id):
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 4, 3), name="Fiesta de Ronda", workplace=ronda
        )
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 4, 28), name="Fiesta de Cádiz", workplace=cadiz
        )
        trasladar(rosa, cadiz, el=date(2026, 4, 15))

        por_centro = holidays_by_workplace(date(2026, 4, 1), date(2026, 4, 30))
        suyos = holidays_for(rosa, date(2026, 4, 1), date(2026, 4, 30), por_centro)

    assert suyos == {date(2026, 4, 3), date(2026, 4, 28)}


# --------------------------------------------------- el informe por centro


@pytest.mark.django_db
def test_el_informe_de_marzo_por_centro_trae_a_quien_estaba_entonces(company, rosa, sitios):
    ronda, cadiz = sitios
    with tenant_context(company.id):
        trasladar(rosa, cadiz, el=date(2026, 4, 15))
        gente = [rosa]

        assert people_in_workplace(gente, ronda.id, *MARZO) == [rosa]
        assert people_in_workplace(gente, cadiz.id, *MARZO) == []
        assert people_in_workplace(gente, cadiz.id, date(2026, 5, 1), date(2026, 5, 31)) == [rosa]


# ------------------------------------------------- sin crecer con la gente


@pytest.mark.django_db
def test_el_historial_de_toda_la_plantilla_se_trae_de_una_vez(company, rosa, sitios):
    """Por cabeza sería una consulta por persona dentro de cada bucle que lo use."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    ronda, cadiz = sitios
    with tenant_context(company.id):
        otra = User.objects.create_user(
            email="otra@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="EMP-0043",
            workplace=cadiz,
        )
        trasladar(rosa, cadiz, el=date(2026, 4, 15))

        with CaptureQueriesContext(connection) as consultas:
            reparto = workplaces_by_person([rosa, otra], *MARZO)

    assert len(consultas) == 1, "una consulta, no una por persona"
    assert reparto[rosa.id][date(2026, 3, 10)].id == ronda.id
    assert reparto[otra.id][date(2026, 3, 10)].id == cadiz.id
