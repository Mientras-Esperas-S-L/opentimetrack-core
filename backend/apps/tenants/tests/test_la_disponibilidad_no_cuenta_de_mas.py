"""Quién puede trabajar tal día, y qué se dice de quien no puede.

Lo que fija esta prueba es la línea que separa lo que un planificador necesita de lo
que no le corresponde. Necesita saber que el martes esa persona no está: si lo ignora,
asigna trabajo a quien no puede hacerlo. **No** necesita saber que está de baja
médica: eso es dato de salud, categoría especial del art. 9 RGPD, y el cuadrante se
hace igual de bien sin él.

Un permiso ordinario sí se nombra, y esa diferencia tampoco es cosmética: un
planificador puede pedir mover unas vacaciones y no puede pedir mover una baja.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, AbsenceType, LeaveType
from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.tenants.holidays import PublicHoliday
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User, Workplace

PASSWORD = "a-sufficiently-long-password"
URL = "/api/app/availability/"
SEMANA = {"from": "2026-09-14", "to": "2026-09-18"}


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def ronda(company):
    with tenant_context(company.id):
        return Workplace.objects.create(
            tenant=company, name="Ronda", municipality="Ronda", region="ES-AN"
        )


@pytest.fixture
def rosa(company, ronda):
    with tenant_context(company.id):
        return User.objects.create_user(
            email="rosa@acme.example",
            password=PASSWORD,
            tenant=company,
            employee_id="EMP-0042",
            workplace=ronda,
        )


def credential(company, *scopes, name="Geosian"):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name=name, scopes=[str(s) for s in scopes]
        )
        _credential, secret = ApplicationCredential.issue(application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    return client


def dias_de(answer, ref="EMP-0042"):
    persona = next(p for p in answer.json()["people"] if p["employee_id"] == ref)
    return {d["day"]: d for d in persona["days"]}


def ausentar(company, quien, tipo, desde, hasta, *, code="", nombre=""):
    with tenant_context(company.id):
        leave_type = None
        if code:
            leave_type = LeaveType.objects.create(
                tenant=company, code=code, name=nombre, family=tipo
            )
        return Absence.objects.create(
            tenant=company,
            employee=quien,
            absence_type=tipo,
            leave_type=leave_type,
            start_date=desde,
            end_date=hasta,
            status=AbsenceStatus.APPROVED,
        )


# ------------------------------------------------------------- lo que dice


@pytest.mark.django_db
def test_un_dia_libre_es_un_dia_disponible(company, rosa):
    answer = credential(company, ApplicationScope.READ_AVAILABILITY).get(URL, SEMANA)

    assert answer.status_code == 200
    dias = dias_de(answer)
    assert dias["2026-09-16"]["available"] is True
    assert dias["2026-09-16"]["absence"] is None
    assert dias["2026-09-16"]["rostered_minutes"] == 0


@pytest.mark.django_db
def test_dice_los_minutos_que_ya_tiene_planificados(company, rosa):
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=rosa,
            day=date(2026, 9, 16),
            segments=[{"start": "08:00", "end": "16:00"}],
        )

    dias = dias_de(credential(company, ApplicationScope.READ_AVAILABILITY).get(URL, SEMANA))

    assert dias["2026-09-16"]["rostered_minutes"] == 480
    assert dias["2026-09-16"]["available"] is True, "tener turno no es estar ocupado para otra cosa"


@pytest.mark.django_db
def test_el_festivo_de_su_centro_lo_deja_no_disponible(company, rosa, ronda):
    with tenant_context(company.id):
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 9, 17), name="Feria de Ronda", workplace=ronda
        )

    dias = dias_de(credential(company, ApplicationScope.READ_AVAILABILITY).get(URL, SEMANA))

    assert dias["2026-09-17"]["available"] is False
    assert dias["2026-09-17"]["holiday"] == "Feria de Ronda"


@pytest.mark.django_db
def test_el_festivo_de_otro_centro_no_le_toca(company, rosa):
    with tenant_context(company.id):
        otro = Workplace.objects.create(
            tenant=company, name="Cádiz", municipality="Cádiz", region="ES-AN"
        )
        PublicHoliday.objects.create(
            tenant=company, day=date(2026, 9, 17), name="Carnaval de Cádiz", workplace=otro
        )

    dias = dias_de(credential(company, ApplicationScope.READ_AVAILABILITY).get(URL, SEMANA))

    assert dias["2026-09-17"]["available"] is True
    assert dias["2026-09-17"]["holiday"] is None


@pytest.mark.django_db
def test_un_permiso_ordinario_se_nombra(company, rosa):
    """Quien planifica puede pedir mover unas vacaciones; por eso se le dicen."""
    ausentar(
        company,
        rosa,
        AbsenceType.VACATION,
        date(2026, 9, 15),
        date(2026, 9, 16),
        code="es.vacation",
        nombre="Vacaciones",
    )

    dias = dias_de(credential(company, ApplicationScope.READ_AVAILABILITY).get(URL, SEMANA))

    assert dias["2026-09-15"]["available"] is False
    assert dias["2026-09-15"]["absence"] == "Vacaciones"
    assert dias["2026-09-17"]["available"] is True, "el permiso acabó el 16"


# ------------------------------------------------------ lo que NO dice


@pytest.mark.django_db
def test_la_baja_medica_se_dice_sin_nombrarla(company, rosa):
    """El caso que da nombre a la prueba: dato de salud, art. 9 RGPD."""
    ausentar(
        company,
        rosa,
        AbsenceType.SICK_LEAVE,
        date(2026, 9, 15),
        date(2026, 9, 18),
        code="es.sick.common",
        nombre="Baja por enfermedad común",
    )

    answer = credential(company, ApplicationScope.READ_AVAILABILITY).get(URL, SEMANA)
    dias = dias_de(answer)

    assert dias["2026-09-15"]["available"] is False, "quien planifica sabe que no está"
    assert dias["2026-09-15"]["absence"] is None, "y no sabe por qué"
    entero = answer.content.decode()
    assert "enfermedad" not in entero.lower()
    assert "sick" not in entero.lower()


# ---------------------------------------------------------------- los límites


@pytest.mark.django_db
def test_necesita_su_propio_permiso(company, rosa):
    """Leer el cuadrante o las ausencias no da derecho a esto, ni al revés."""
    sin_el = credential(company, ApplicationScope.READ_ROSTER, ApplicationScope.READ_ABSENCES)

    assert sin_el.get(URL, SEMANA).status_code == 403


@pytest.mark.django_db
def test_se_acota_como_las_demas(company, rosa):
    client = credential(company, ApplicationScope.READ_AVAILABILITY)

    assert client.get(URL, {"from": "2026-01-01", "to": "2026-12-31"}).status_code == 400
    assert client.get(URL, {"from": "2026-09-14"}).status_code == 400


@pytest.mark.django_db
def test_otra_empresa_no_ve_a_nadie_de_esta(company, rosa):
    otra = Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")
    intrusa = credential(otra, ApplicationScope.READ_AVAILABILITY, name="Otra")

    assert intrusa.get(URL, SEMANA).json()["people"] == []
