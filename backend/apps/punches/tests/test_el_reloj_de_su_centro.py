"""Una delegación en otro huso: qué hora ve, y en qué día cae su jornada.

Una empresa de Madrid con una delegación en Las Palmas son sesenta minutos, y
sesenta minutos son la diferencia entre que un fichaje caiga el lunes o el
domingo. El producto ya lo tenía resuelto donde se cuenta ---`local_day_bounds`
resuelve por persona, y el informe que se entrega pone cada fichaje en el día
que esa persona vivió--- y no donde se enseña: la sesión y la pantalla de fichar
daban la zona de la **empresa**.

Lo que se veía: quien fichaba a las 23:30 en Las Palmas leía «00:30» en su
pantalla, y su jornada aparecía empezada al día siguiente. El informe decía el
día correcto. El registro que uno consulta y el que se entrega tienen que ser el
mismo, que es de lo que va el art. 34.9.

La zona de la empresa sigue siendo la respuesta para quien no tiene centro
asignado, y eso también se prueba: un arreglo que exigiera centro dejaría sin
hora a la mayoría de las plantillas, que solo tienen uno.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.reports.services import build_report
from apps.tenants.models import Tenant
from apps.users.models import User, Workplace

PASSWORD = "a-sufficiently-long-password"
CANARIAS = ZoneInfo("Atlantic/Canary")


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="Dos husos SL", tax_id="B66666666", time_zone="Europe/Madrid")


@pytest.fixture
def nayra(company):
    """Trabaja en la delegación, que va una hora por detrás de la central."""
    with tenant_context(company.id):
        centro = Workplace.objects.create(
            tenant=company, name="Las Palmas", time_zone="Atlantic/Canary"
        )
        yield User.objects.create_user(
            email="nayra@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Nayra",
            last_name="Pérez",
            workplace=centro,
        )


@pytest.fixture
def sin_centro(company):
    """La mayoría de las plantillas: un solo sitio y ningún centro asignado."""
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="madrid@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Marta",
            last_name="Central",
        )


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


@pytest.mark.django_db
def test_la_sesion_dice_en_que_huso_vive_quien_la_abre(company, nayra):
    cuerpo = como(nayra).get("/api/auth/me/").data

    assert cuerpo["tenant"]["time_zone"] == "Europe/Madrid"
    assert cuerpo["user"]["effective_time_zone"] == "Atlantic/Canary"


@pytest.mark.django_db
def test_quien_no_tiene_centro_se_queda_con_la_de_la_empresa(company, sin_centro):
    """El control. Sin esto, el arreglo podría estar dando siempre lo mismo."""
    cuerpo = como(sin_centro).get("/api/auth/me/").data

    assert cuerpo["user"]["effective_time_zone"] == "Europe/Madrid"


@pytest.mark.django_db
def test_el_reloj_de_la_pantalla_de_fichar_es_el_suyo(company, nayra):
    """Es la hora que la persona lee al fichar, y la que decide qué día es hoy."""
    assert como(nayra).get("/api/punches/today/").data["time_zone"] == "Atlantic/Canary"
    assert (
        como(User.objects.get(email="nayra@example.com")).get("/api/punches/today/").status_code
        == 200
    )


@pytest.mark.django_db
def test_la_pantalla_y_el_informe_ponen_el_fichaje_en_el_mismo_dia(company, nayra):
    """El caso entero, de punta a punta.

    Las 23:30 en Las Palmas son las 00:30 **del día siguiente** en Madrid. El
    informe siempre puso este fichaje en el día de Las Palmas; lo que fallaba
    era la zona con la que la pantalla lo colocaba.
    """
    with tenant_context(company.id):
        dia = timezone.now().astimezone(CANARIAS).date() - timedelta(days=2)
        Punch.objects.create(
            tenant=company,
            employee=nayra,
            punch_type=PunchType.IN,
            timestamp=datetime.combine(dia, time(23, 30), tzinfo=CANARIAS),
        )
        informe = build_report(
            employee=nayra, company=company, date_from=dia, date_to=dia + timedelta(days=1)
        )

    del_informe = [fila.day for fila in informe.rows if fila.entries]
    assert del_informe == [dia], f"el informe lo pone en {del_informe}, no en {dia}"

    # Y el día que sale con la zona que la pantalla recibe ahora.
    zona = ZoneInfo(como(nayra).get("/api/auth/me/").data["user"]["effective_time_zone"])
    with tenant_context(company.id):
        guardado = Punch.objects.filter(employee=nayra).first()
    assert guardado.timestamp.astimezone(zona).date() == dia

    # Con la de la empresa saldría el día siguiente, que es el defecto que había.
    de_la_empresa = guardado.timestamp.astimezone(company.tzinfo).date()
    assert de_la_empresa == dia + timedelta(days=1), (
        "si esto falla, el caso ya no separa los dos husos y la prueba no demuestra nada"
    )
