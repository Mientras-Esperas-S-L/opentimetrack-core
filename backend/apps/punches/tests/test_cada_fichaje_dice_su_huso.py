"""Un listado mezcla delegaciones, y una hora sin su huso no dice nada.

La vuelta anterior puso la zona de cada cual en su sesión, que arregla las
pantallas donde uno mira lo suyo. Quedaban las de gestión: el cuadro de fichajes
y la cola de decisiones enseñan a **varias** personas a la vez, y el frontend
solo tenía la zona de la empresa, así que pintaba todas las filas en el huso de
la central.

Con una empresa en Madrid y una delegación en Las Palmas son sesenta minutos:
quien responde una corrección leía la hora que se le propone poner con una hora
de más, y en el cuadro un fichaje de las 23:30 aparecía bajo el día siguiente.

Por eso el huso va **en el fichaje**, y no solo en la ficha de la persona: quien
lee esto por la API ---una pantalla o un conector--- no tiene otra forma de
saberlo.

Y va con su `select_related`, porque un campo derivado por fila es un N+1
esperando: sin los saltos hasta el centro y hasta la empresa, cuarenta fichajes
de veinte personas costaban cuarenta y seis consultas en vez de seis.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.punches.models import CorrectionKind, Punch, PunchCorrection, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Role, User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con delegación", tax_id="B77777777", time_zone="Europe/Madrid"
    )


@pytest.fixture
def jefa(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Jefa",
            last_name="Central",
            role=Role.ADMIN,
        )


@pytest.fixture
def nayra(company):
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


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


@pytest.mark.django_db
def test_el_fichaje_dice_en_que_huso_se_vivio(company, jefa, nayra):
    with tenant_context(company.id):
        Punch.objects.create(
            tenant=company, employee=nayra, punch_type=PunchType.IN, timestamp=timezone.now()
        )
        Punch.objects.create(
            tenant=company, employee=jefa, punch_type=PunchType.IN, timestamp=timezone.now()
        )

    filas = como(jefa).get("/api/punches/").data["results"]
    por_persona = {f["employee_name"]: f["time_zone"] for f in filas}

    assert por_persona["Nayra Pérez"] == "Atlantic/Canary"
    # El control: quien no tiene centro se queda con el de la empresa. Sin esta
    # línea, un arreglo que devolviera siempre lo mismo pasaría la de arriba.
    assert por_persona["Jefa Central"] == "Europe/Madrid"


@pytest.mark.django_db
def test_la_correccion_lleva_el_huso_de_quien_la_sufre(company, jefa, nayra):
    """`proposed_timestamp` va suelto: es la hora que se propone poner."""
    with tenant_context(company.id):
        suyo = Punch.objects.create(
            tenant=company, employee=nayra, punch_type=PunchType.IN, timestamp=timezone.now()
        )
        PunchCorrection.objects.create(
            tenant=company,
            employee=nayra,
            kind=CorrectionKind.MODIFY,
            target=suyo,
            proposed_timestamp=timezone.now() - timedelta(hours=1),
            reason="Entré antes",
            requested_by=nayra,
        )

    fila = como(jefa).get("/api/corrections/").data["results"][0]
    assert fila["time_zone"] == "Atlantic/Canary"
    # Y el fichaje que cuelga lo trae por su cuenta, que es de donde sale la
    # hora que se sustituye.
    assert fila["target_detail"]["time_zone"] == "Atlantic/Canary"


@pytest.mark.django_db
def test_decirlo_no_cuesta_una_consulta_por_fila(company, jefa, nayra):
    """El campo es derivado, así que se mide. Cuarenta filas, no cuarenta y seis."""
    with tenant_context(company.id):
        ahora = timezone.now()
        gente = [nayra, jefa]
        for numero in range(18):
            gente.append(
                User.objects.create_user(
                    email=f"p{numero}@example.com",
                    password=PASSWORD,
                    tenant=company,
                    first_name=f"P{numero}",
                    last_name="X",
                )
            )
        for indice, quien in enumerate(gente):
            for paso in range(2):
                Punch.objects.create(
                    tenant=company,
                    employee=quien,
                    punch_type=PunchType.IN,
                    timestamp=ahora - timedelta(hours=indice * 10 + paso),
                )

    cliente = como(jefa)
    with CaptureQueriesContext(connection) as consultas:
        respuesta = cliente.get("/api/punches/")

    assert respuesta.status_code == 200
    assert len(respuesta.data["results"]) == 40, "el caso no llega a llenar una página"
    assert len(consultas) <= 8, (
        f"{len(consultas)} consultas para 40 filas: falta un `select_related` "
        f"hasta el centro o hasta la empresa"
    )
