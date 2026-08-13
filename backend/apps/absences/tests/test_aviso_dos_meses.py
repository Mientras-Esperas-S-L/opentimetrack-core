"""Los dos meses del art. 38.3, cuando las vacaciones las pone la empresa.

«El trabajador conocerá las fechas que le correspondan dos meses antes, al
menos, del comienzo del disfrute.» El plazo existe para que a nadie le fijen las
vacaciones encima: es lo que permite reservar un vuelo, cuadrar con la pareja o
apuntar a un crío a un campamento.

Se avisa, no se impide, como con el resto de los mínimos. Acortarlo de mutuo
acuerdo es corriente y legítimo, y negarse a registrarlo dejaría fuera del
sistema unas vacaciones que la gente va a disfrutar igual.

Y la mitad que hace que el aviso sirva: **solo cuando las pone otro**. Si las
pide la persona, conoce las fechas por definición. Un aviso que saltara también
ahí saldría en la mitad de las solicitudes normales, y en dos semanas nadie lo
miraría.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence, short_holiday_notice
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


@pytest.mark.django_db
@freeze_time(HOY)
def test_la_empresa_se_las_pone_para_dentro_de_tres_semanas(empresa, gente):
    with tenant_context(empresa.id):
        absence = poner_vacaciones(
            empresa, gente["ana"], HOY + timedelta(days=21), las_pone=gente["jefa"]
        )

        aviso = short_holiday_notice(absence)

    assert aviso == {"days": 21, "required": 60, "citation": "Art. 38.3 ET"}


@pytest.mark.django_db
@freeze_time(HOY)
def test_con_los_dos_meses_no_hay_nada_que_avisar(empresa, gente):
    with tenant_context(empresa.id):
        absence = poner_vacaciones(
            empresa, gente["ana"], HOY + timedelta(days=60), las_pone=gente["jefa"]
        )

        assert short_holiday_notice(absence) is None


@pytest.mark.django_db
@freeze_time(HOY)
def test_si_las_pide_la_propia_persona_no_hay_aviso(empresa, gente):
    """La que hace que el aviso valga para algo.

    Quien pide sus vacaciones para la semana que viene conoce las fechas: no hay
    plazo que incumplir. Avisar aquí sería enseñar a ignorar el aviso.
    """
    with tenant_context(empresa.id):
        absence = poner_vacaciones(
            empresa, gente["ana"], HOY + timedelta(days=7), las_pone=gente["ana"]
        )

        assert short_holiday_notice(absence) is None


@pytest.mark.django_db
@freeze_time(HOY)
def test_una_baja_no_lleva_este_aviso(empresa, gente):
    """El plazo es de las vacaciones. Una baja no se avisa con dos meses."""
    with tenant_context(empresa.id):
        absence = request_absence(
            employee=gente["ana"],
            company=empresa,
            absence_type=AbsenceType.SICK_LEAVE,
            start_date=HOY,
            end_date=HOY + timedelta(days=3),
            requested_by=gente["jefa"],
        )

        assert short_holiday_notice(absence) is None


@pytest.mark.django_db
def test_el_plazo_se_mide_desde_que_se_metieron_no_desde_hoy(empresa, gente):
    """Unas vacaciones avisadas con tiempo no se vuelven «con poco aviso» solas.

    Si se mirara contra hoy, las de julio avisadas en enero pasarían a estar mal
    avisadas en junio, sin que nadie hubiera hecho nada. El plazo se cuenta
    contra el momento en que la persona pudo conocer las fechas.
    """
    with freeze_time(date(2026, 1, 10)), tenant_context(empresa.id):
        absence = poner_vacaciones(empresa, gente["ana"], date(2026, 7, 1), las_pone=gente["jefa"])

    with freeze_time(date(2026, 6, 25)), tenant_context(empresa.id):
        assert short_holiday_notice(absence) is None


@pytest.mark.django_db
@freeze_time(HOY)
def test_el_aviso_viaja_con_la_solicitud_a_quien_decide(empresa, gente):
    """No basta con decírselo a quien las puso: bastaría con no leerlo.

    Quien aprueba tiene que verlo en su cola, que es donde se decide.
    """
    with tenant_context(empresa.id):
        client = APIClient()
        client.force_authenticate(user=gente["jefa"])
        creada = client.post(
            "/api/absences/",
            {
                "employee": str(gente["ana"].id),
                "absence_type": AbsenceType.VACATION,
                "start_date": (HOY + timedelta(days=10)).isoformat(),
                "end_date": (HOY + timedelta(days=17)).isoformat(),
            },
            format="json",
        )
        assert creada.status_code == 201, creada.json()
        assert creada.json()["short_notice"]["days"] == 10

        listado = client.get("/api/absences/", {"status": "PENDING"})
        fila = next(f for f in listado.json()["results"] if f["id"] == creada.json()["id"])

    assert fila["short_notice"]["citation"] == "Art. 38.3 ET"


@pytest.mark.django_db
@freeze_time(HOY)
def test_quien_las_pide_para_si_no_arrastra_el_aviso_por_la_api(empresa, gente):
    """El contraste por la API, no solo sobre el servicio."""
    with tenant_context(empresa.id):
        client = APIClient()
        client.force_authenticate(user=gente["ana"])
        creada = client.post(
            "/api/absences/",
            {
                "absence_type": AbsenceType.VACATION,
                "start_date": (HOY + timedelta(days=10)).isoformat(),
                "end_date": (HOY + timedelta(days=17)).isoformat(),
            },
            format="json",
        )

    assert creada.status_code == 201, creada.json()
    assert creada.json()["short_notice"] is None
    assert creada.json()["requested_by"] == str(gente["ana"].id)
