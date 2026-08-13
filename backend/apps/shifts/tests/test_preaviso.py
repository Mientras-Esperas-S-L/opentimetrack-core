"""El preaviso del art. 34.2, que estaba configurado y no lo miraba nadie.

«El trabajador deberá conocer con un preaviso mínimo de cinco días el día y la
hora de la prestación de trabajo resultante» de la distribución irregular de la
jornada.

El plazo estaba en el modelo (`roster_notice_days`), en el marco legal con su
cita, y en la pantalla de ajustes para que la empresa lo subiera si su convenio
lo mejora. **Y no lo leía ni una línea de código.** Un ajuste que no lee nadie
es peor que no tenerlo: quien lo configura se queda convencido de que el
producto lo vigila.

Se avisa, no se impide. Un cambio urgente ---alguien se pone malo y hay que
cubrir el turno--- es legítimo y frecuente, y negarse a registrarlo dejaría el
cuadrante real fuera del cuadrante.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time

from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
MAÑANA = [{"start": "08:00", "end": "16:00"}]


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="ana@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            last_name="García",
        )


def poner_turno(empresa, quien, dia, *, el_dia_que):
    """Crea el turno **en** esa fecha, que es lo que fija el preaviso."""
    with freeze_time(el_dia_que):
        return Shift.objects.create(tenant=empresa, employee=quien, day=dia, segments=MAÑANA)


def avisos(empresa, primero, ultimo):
    return [
        f
        for f in review_roster(company=empresa, first=primero, last=ultimo)
        if f.code == "short_roster_notice"
    ]


@pytest.mark.django_db
def test_un_turno_puesto_con_dos_dias_avisa(empresa, quien):
    with tenant_context(empresa.id):
        poner_turno(empresa, quien, date(2026, 9, 10), el_dia_que="2026-09-08")

        salidas = avisos(empresa, date(2026, 9, 1), date(2026, 9, 30))

    assert len(salidas) == 1
    assert "2 días" in str(salidas[0].message) or "2 day" in str(salidas[0].message)
    assert salidas[0].basis == "Art. 34.2 ET"


@pytest.mark.django_db
def test_con_los_cinco_dias_no_dice_nada(empresa, quien):
    """El contraste. Sin él, un aviso que saltara siempre pasaría por bueno."""
    with tenant_context(empresa.id):
        poner_turno(empresa, quien, date(2026, 9, 10), el_dia_que="2026-09-05")

        assert avisos(empresa, date(2026, 9, 1), date(2026, 9, 30)) == []


@pytest.mark.django_db
def test_el_mismo_dia_lo_dice_sin_número(empresa, quien):
    """«Puesto con 0 días de antelación» se lee peor que «puesto el mismo día»."""
    with tenant_context(empresa.id):
        poner_turno(empresa, quien, date(2026, 9, 10), el_dia_que="2026-09-10")

        salidas = avisos(empresa, date(2026, 9, 1), date(2026, 9, 30))

    assert len(salidas) == 1
    assert "0" not in str(salidas[0].message)


@pytest.mark.django_db
def test_anotar_el_cuadrante_de_la_semana_pasada_no_es_poco_preaviso(empresa, quien):
    """Rellenar lo que ya pasó no es un incumplimiento del preaviso.

    Avisar ahí sería llamar incumplimiento a poner al día el cuadrante, y de
    quién lo tocó y cuándo ya consta en el registro de actividad.
    """
    with tenant_context(empresa.id):
        poner_turno(empresa, quien, date(2026, 9, 10), el_dia_que="2026-09-14")

        assert avisos(empresa, date(2026, 9, 1), date(2026, 9, 30)) == []


@pytest.mark.django_db
def test_el_plazo_es_el_de_la_empresa_no_uno_escrito_aquí(empresa, quien):
    """Si el convenio pide diez días, con siete hay que avisar.

    Es la razón de que el ajuste exista, y lo que hacía tan raro que nadie lo
    leyera.
    """
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.roster_notice_days = 10
        reglas.save(update_fields=["roster_notice_days"])

        poner_turno(empresa, quien, date(2026, 9, 20), el_dia_que="2026-09-13")

        salidas = avisos(empresa, date(2026, 9, 1), date(2026, 9, 30))

    assert len(salidas) == 1


@pytest.mark.django_db
def test_a_cero_se_apaga(empresa, quien):
    """Una empresa puede no querer este aviso, y ponerlo a cero es cómo se dice.

    Sin esto, el único modo de callarlo sería un número enorme, que además
    mentiría sobre lo que la empresa pide.
    """
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.roster_notice_days = 0
        reglas.save(update_fields=["roster_notice_days"])

        poner_turno(empresa, quien, date(2026, 9, 10), el_dia_que="2026-09-10")

        assert avisos(empresa, date(2026, 9, 1), date(2026, 9, 30)) == []


@pytest.mark.django_db
def test_mover_un_turno_reabre_el_plazo(empresa, quien):
    """El artículo pide el día **y la hora**.

    Un turno planificado en enero para septiembre tiene preaviso de sobra; el
    mismo turno movido de las siete a las quince el día antes es un dato nuevo
    que la persona no conocía.
    """
    with tenant_context(empresa.id):
        turno = poner_turno(empresa, quien, date(2026, 9, 10), el_dia_que="2026-06-01")
        assert avisos(empresa, date(2026, 9, 1), date(2026, 9, 30)) == []

        with freeze_time("2026-09-09"):
            turno.segments = [{"start": "15:00", "end": "23:00"}]
            turno.save(update_fields=["segments", "updated_at"])

        assert len(avisos(empresa, date(2026, 9, 1), date(2026, 9, 30))) == 1
