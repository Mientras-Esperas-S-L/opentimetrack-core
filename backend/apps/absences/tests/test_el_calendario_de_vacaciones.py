"""El calendario de vacaciones que ve quien las disfruta (art. 38.3).

«El calendario de vacaciones se fijará en cada empresa. El trabajador conocerá
las fechas que le correspondan dos meses antes, al menos, del comienzo del
disfrute.»

**El sujeto del artículo es quien trabaja**, y era el único que no lo veía. El
calendario del equipo existe y está tras el permiso de gestión; el aviso de que
a alguien le fijaron las vacaciones con menos de dos meses llegaba a quien las
metió y a quien las decide. La persona a la que le fijan las fechas ---la que
tiene que reservar un vuelo o apuntar a un crío a un campamento--- no lo veía en
ninguna pantalla.

Aquí se prueban las dos piezas que hacían falta: **el dato de la antelación
siempre** ---no solo cuando el plazo se incumple, porque un plazo que solo se
nota cuando falla no se puede comprobar--- y que la ventana del calendario
**acote por persona**, que es lo que impedía que este panel se pudiera llamar
«mi» sin mentir.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import holiday_notice_days, request_absence
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 3, 2)


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def gente(empresa):
    with tenant_context(empresa.id):
        yield {
            "ana": User.objects.create_user(
                email="ana@example.com", password=PASSWORD, tenant=empresa, first_name="Ana"
            ),
            "berta": User.objects.create_user(
                email="berta@example.com", password=PASSWORD, tenant=empresa, first_name="Berta"
            ),
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
        }


def poner_vacaciones(empresa, quien, desde, *, las_pone):
    return request_absence(
        employee=quien,
        company=empresa,
        absence_type=AbsenceType.VACATION,
        start_date=desde,
        end_date=desde + timedelta(days=6),
        requested_by=las_pone,
    )


def entrando(quien):
    cliente = APIClient()
    cliente.force_authenticate(user=quien)
    return cliente


# --------------------------------------------------------- el dato, siempre


@pytest.mark.django_db
@freeze_time(HOY)
def test_dice_la_antelacion_aunque_el_plazo_se_cumpla(empresa, gente):
    """**Lo que faltaba.** El aviso solo sale cuando el plazo falla.

    Con noventa días de antelación no hay nada que avisar, y hasta ahora eso
    dejaba a quien las disfruta sin forma de ver que sí se cumplió. Un plazo que
    solo se nota cuando falla no se comprueba: se padece.
    """
    with tenant_context(empresa.id):
        absence = poner_vacaciones(
            empresa, gente["ana"], HOY + timedelta(days=90), las_pone=gente["jefa"]
        )

        assert holiday_notice_days(absence) == 90


@pytest.mark.django_db
@freeze_time(HOY)
def test_y_tambien_cuando_no_se_cumple(empresa, gente):
    with tenant_context(empresa.id):
        absence = poner_vacaciones(
            empresa, gente["ana"], HOY + timedelta(days=21), las_pone=gente["jefa"]
        )

        assert holiday_notice_days(absence) == 21


@pytest.mark.django_db
@freeze_time(HOY)
def test_si_las_pide_la_persona_no_hay_antelacion_que_contar(empresa, gente):
    """`None`, no cero.

    Quien pide sus vacaciones conoce las fechas por definición. Un cero ahí se
    leería como «te avisaron el mismo día», que es lo contrario de lo que pasó.
    """
    with tenant_context(empresa.id):
        absence = poner_vacaciones(
            empresa, gente["ana"], HOY + timedelta(days=7), las_pone=gente["ana"]
        )

        assert holiday_notice_days(absence) is None


@pytest.mark.django_db
@freeze_time(HOY)
def test_lo_que_no_son_vacaciones_no_lleva_este_plazo(empresa, gente):
    """El art. 38.3 es de las vacaciones. Un permiso por mudanza no tiene plazo
    de aviso de dos meses, y decir que sí sería inventarse un derecho."""
    with tenant_context(empresa.id):
        absence = request_absence(
            employee=gente["ana"],
            company=empresa,
            absence_type=AbsenceType.PERSONAL,
            start_date=HOY + timedelta(days=3),
            end_date=HOY + timedelta(days=3),
            requested_by=gente["jefa"],
        )

        assert holiday_notice_days(absence) is None


# ------------------------------------------------- la ventana acota por persona


@pytest.mark.django_db
@freeze_time(HOY)
def test_la_ventana_del_calendario_acota_por_persona(empresa, gente):
    """**El defecto que se vio abriendo la pantalla.**

    `?employee=` se publica en el esquema de la lista y la ventana lo ignoraba
    en silencio, así que quien tiene permiso de gestión recibía las vacaciones de
    toda su gente bajo un panel que empieza por «Mi». Ignorar un filtro publicado
    es peor que no ofrecerlo: quien lo usa cree que va acotado.
    """
    with tenant_context(empresa.id):
        poner_vacaciones(empresa, gente["ana"], HOY + timedelta(days=10), las_pone=gente["jefa"])
        poner_vacaciones(empresa, gente["berta"], HOY + timedelta(days=10), las_pone=gente["jefa"])

    respuesta = entrando(gente["jefa"]).get(
        "/api/absences/calendar/",
        {
            "from": HOY.isoformat(),
            "to": (HOY + timedelta(days=60)).isoformat(),
            "employee": str(gente["ana"].id),
        },
    )

    assert respuesta.status_code == 200
    assert {str(fila["employee"]) for fila in respuesta.data} == {str(gente["ana"].id)}


@pytest.mark.django_db
@freeze_time(HOY)
def test_sin_el_filtro_la_ventana_sigue_dando_lo_de_todos(empresa, gente):
    """El contraste del anterior, y a la vez la garantía de que no se ha roto el
    calendario del equipo: sin `employee`, quien lleva gente sigue viéndola."""
    with tenant_context(empresa.id):
        poner_vacaciones(empresa, gente["ana"], HOY + timedelta(days=10), las_pone=gente["jefa"])
        poner_vacaciones(empresa, gente["berta"], HOY + timedelta(days=10), las_pone=gente["jefa"])

    respuesta = entrando(gente["jefa"]).get(
        "/api/absences/calendar/",
        {"from": HOY.isoformat(), "to": (HOY + timedelta(days=60)).isoformat()},
    )

    assert len({fila["employee"] for fila in respuesta.data}) == 2


@pytest.mark.django_db
@freeze_time(HOY)
def test_el_filtro_no_es_una_puerta_para_mirar_a_otro(empresa, gente):
    """Un filtro no puede ampliar lo que se ve.

    Ana no lleva gente: pedir la ventana con el identificador de Berta no le da
    las de Berta, le da nada. Si `filter_queryset` se hubiera puesto **antes** de
    acotar por quien pregunta, este filtro sería un mirador.
    """
    with tenant_context(empresa.id):
        poner_vacaciones(empresa, gente["berta"], HOY + timedelta(days=10), las_pone=gente["jefa"])

    respuesta = entrando(gente["ana"]).get(
        "/api/absences/calendar/",
        {
            "from": HOY.isoformat(),
            "to": (HOY + timedelta(days=60)).isoformat(),
            "employee": str(gente["berta"].id),
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.data == []


# ---------------------------------------------------- lo que llega a la pantalla


@pytest.mark.django_db
@freeze_time(HOY)
def test_la_ventana_trae_quien_las_fijo_y_con_cuanto(empresa, gente):
    """Sin el nombre, la frase que lee quien las disfruta sería «te las fijó
    <UUID>». Y sin la antelación no se puede decir ninguna de las dos cosas."""
    with tenant_context(empresa.id):
        poner_vacaciones(empresa, gente["ana"], HOY + timedelta(days=21), las_pone=gente["jefa"])

    respuesta = entrando(gente["ana"]).get(
        "/api/absences/calendar/",
        {"from": HOY.isoformat(), "to": (HOY + timedelta(days=60)).isoformat()},
    )

    (fila,) = respuesta.data
    assert fila["requested_by_name"] == gente["jefa"].get_full_name()
    assert fila["notice_days"] == 21
    assert fila["short_notice"]["citation"] == "Art. 38.3 ET"


@pytest.mark.django_db
@freeze_time(HOY)
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(empresa, gente):
    """Con `?employee=` de otra empresa: el filtro se aplica sobre lo que ya está
    acotado por contexto, no sobre la tabla."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B22222222", time_zone="Europe/Madrid"
    )
    with tenant_context(vecina.id):
        suyo = User.objects.create_user(
            email="suyo@vecina.example", password=PASSWORD, tenant=vecina, first_name="Ajeno"
        )
        poner_vacaciones(vecina, suyo, HOY + timedelta(days=10), las_pone=suyo)

    respuesta = entrando(gente["jefa"]).get(
        "/api/absences/calendar/",
        {
            "from": HOY.isoformat(),
            "to": (HOY + timedelta(days=60)).isoformat(),
            "employee": str(suyo.id),
        },
    )

    assert respuesta.data == []
