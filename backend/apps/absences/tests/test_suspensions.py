"""Suspensiones del contrato.

No son permisos: el contrato se para y no hay obligación de trabajar. Entran
porque durante ellas **no debe esperarse jornada**, que es lo que explica el
hueco en el registro. La tramitación --- el parte al INSS, el expediente del
ERTE --- se hace en otro sitio.

Casi todas encajan en la maquinaria que ya había: una ausencia de días
completos, más larga. La que no es el **ERTE de reducción de jornada**, que no
para el contrato sino que lo encoge, y sin el que todo el cuadrante de una
empresa en ERTE parcial se lee como incumplimiento.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import AbsenceStatus, LeaveType
from apps.absences.services import request_absence
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import HoursPeriod, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        seed_leave_types(company)
        yield User.objects.create_user(
            email="ana@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            regime=WorkingTimeRegime.FULL_TIME,
            contracted_hours=40,
            contracted_period=HoursPeriod.WEEK,
        )


def suspend(company, who, code, first, last, *, share=None, status=AbsenceStatus.APPROVED):
    with tenant_context(company.id):
        absence = request_absence(
            employee=who,
            company=company,
            leave_type=LeaveType.objects.get(code=code),
            start_date=first,
            end_date=last,
            reduction_share=share,
        )
        absence.status = status
        absence.save(update_fields=["status"])
        return absence


# ----------------------------------------------------------- las que paran


@pytest.mark.django_db
def test_the_catalogue_carries_the_fifteen_of_article_45(company, worker):
    with tenant_context(company.id):
        codes = set(LeaveType.objects.filter(family="SUSPENSION").values_list("code", flat=True))

    assert {"es.birth", "es.erte", "es.strike", "es.unpaid_leave", "es.custody"} <= codes


@pytest.mark.django_db
def test_none_of_them_is_paid_by_the_company(company, worker):
    """Paga la Seguridad Social, la mutua, o nadie. Quién paga se dice en la
    nota, porque el campo solo distingue si sale de la nómina."""
    with tenant_context(company.id):
        assert not LeaveType.objects.filter(family="SUSPENSION", paid=True).exists()


@pytest.mark.django_db
def test_a_suspension_blocks_clocking(company, worker):
    today = local_today(company)
    suspend(
        company, worker, "es.unpaid_leave", today - timedelta(days=30), today + timedelta(days=300)
    )

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        register_punch(employee=worker, company=company)

    assert caught.value.code == "punch_blocked_by_absence"


@pytest.mark.django_db
def test_and_the_roster_reports_anybody_planned_during_one(company, worker):
    with tenant_context(company.id):
        suspend(company, worker, "es.birth", date(2026, 9, 1), date(2026, 12, 20))
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 15),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        findings = review_roster(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))

    assert any(f.code == "rostered_on_leave" for f in findings)


# ------------------------------------------------------- el ERTE que encoge


@pytest.mark.django_db
def test_a_partial_erte_does_not_block_clocking(company, worker):
    """Quien tiene la jornada reducida un cuarenta por ciento sigue viniendo
    por el otro sesenta."""
    today = local_today(company)
    suspend(
        company, worker, "es.erte", today - timedelta(days=10), today + timedelta(days=80), share=40
    )

    with tenant_context(company.id):
        assert register_punch(employee=worker, company=company) is not None


@pytest.mark.django_db
def test_the_roster_is_measured_against_the_reduced_contract(company, worker):
    """Sin esto, el cuadrante entero de una empresa en ERTE parcial se lee como
    que todo el mundo se pasa de sus horas todas las semanas --- que es lo
    contrario de lo que ha pasado."""
    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        # Cinco días de cinco horas: 25 h, por debajo de 40 y por encima del
        # 60 % de 40, que son 24.
        for offset in range(5):
            Shift.objects.create(
                tenant=company,
                employee=worker,
                day=monday + timedelta(days=offset),
                segments=[{"start": "09:00", "end": "14:00"}],
            )

        sin_erte = review_roster(company=company, first=monday, last=monday + timedelta(days=6))
        assert [f for f in sin_erte if f.code == "over_contracted_hours"] == []

        suspend(company, worker, "es.erte", monday, monday + timedelta(days=90), share=40)
        con_erte = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    over = [f for f in con_erte if f.code == "over_contracted_hours"]
    assert len(over) == 1
    # Y dice la cifra reducida, no la del contrato entero.
    assert "24 h" in str(over[0].message)


@pytest.mark.django_db
def test_a_full_suspension_leaves_the_roster_arithmetic_alone(company, worker):
    """Cien por cien no es una reducción: es la suspensión de siempre, y el
    cuadrante no debería medirse contra cero."""
    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        for offset in range(5):
            Shift.objects.create(
                tenant=company,
                employee=worker,
                day=monday + timedelta(days=offset),
                segments=[{"start": "09:00", "end": "14:00"}],
            )
        suspend(company, worker, "es.erte", monday, monday + timedelta(days=90), share=100)
        findings = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    assert [f for f in findings if f.code == "over_contracted_hours"] == []


@pytest.mark.django_db
def test_only_a_suspension_can_reduce_the_day(company, worker):
    """En cualquier otro sitio parecería un ajuste y no haría nada, que es la
    peor clase de campo."""
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            reduction_share=40,
        )

    assert caught.value.code == "reduction_needs_a_suspension"


@pytest.mark.django_db
def test_a_suspension_spends_no_holiday(company, worker):
    from apps.absences.services import vacation_balance

    with tenant_context(company.id):
        suspend(company, worker, "es.birth", date(2026, 9, 1), date(2026, 12, 20))
        assert vacation_balance(worker, company, date(2026, 10, 1)).taken == 0


@pytest.mark.django_db
def test_a_pending_suspension_does_not_block_anything(company, worker):
    """Sólo lo aprobado para el registro. Una solicitud sin resolver es una
    intención, y el registro no se mide contra intenciones."""
    today = local_today(company)
    suspend(
        company,
        worker,
        "es.unpaid_leave",
        today,
        today + timedelta(days=90),
        status=AbsenceStatus.PENDING,
    )

    with tenant_context(company.id):
        assert register_punch(employee=worker, company=company) is not None


# ---------------------------------------------- la reducción convive (12/08)
#
# El ERTE parcial trataba el día como reclamado entero, y durante meses no se
# podía pedir ni una visita médica. La reducción va ahora por su propio carril:
# solo choca con otra reducción, que sí es una contradicción.


@pytest.mark.django_db
def test_holiday_can_be_booked_during_a_partial_erte(company, worker):
    today = local_today(company)
    suspend(company, worker, "es.erte", today, today + timedelta(days=90), share=40)

    with tenant_context(company.id):
        absence = request_absence(
            employee=worker,
            company=company,
            absence_type="VACATION",
            start_date=today + timedelta(days=14),
            end_date=today + timedelta(days=18),
        )

    assert absence.pk is not None


@pytest.mark.django_db
def test_and_so_can_a_medical_appointment(company, worker):
    from datetime import time

    today = local_today(company)
    suspend(company, worker, "es.erte", today, today + timedelta(days=90), share=40)

    with tenant_context(company.id):
        absence = request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=7),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )

    assert absence.is_partial


@pytest.mark.django_db
def test_two_reductions_at_once_are_a_contradiction(company, worker):
    """El único choque que una reducción sí tiene: la jornada de nadie puede
    estar reducida dos veces a la vez."""
    today = local_today(company)
    suspend(company, worker, "es.erte", today, today + timedelta(days=90), share=40)

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.red"),
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=60),
            reduction_share=20,
        )

    assert caught.value.code == "overlapping_absence"


@pytest.mark.django_db
def test_a_full_suspension_still_claims_its_days(company, worker):
    """La excedencia sí para el contrato: unas vacaciones dentro siguen siendo
    una contradicción."""
    suspend(company, worker, "es.unpaid_leave", date(2026, 9, 1), date(2026, 12, 20))

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            absence_type="VACATION",
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
        )

    assert caught.value.code == "overlapping_absence"


@pytest.mark.django_db
def test_a_reduction_takes_no_hours(company, worker):
    """Reducción y horas son dos formas incompatibles del mismo día."""
    from datetime import time

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.erte"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            start_time=time(9, 0),
            end_time=time(13, 0),
            reduction_share=40,
        )

    assert caught.value.code == "reduction_takes_no_hours"


# ------------------------------------------ el cuadrante deja de acusar (12/08)


@pytest.mark.django_db
def test_the_roster_does_not_flag_somebody_on_a_partial_erte(company, worker):
    """Quien tiene la jornada reducida DEBE estar en el cuadrante, al 60 %.
    Avisar de cada día suyo era el falso positivo que enterraba los avisos
    buenos: 23 de 30 en el mes de la demo."""
    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        suspend(company, worker, "es.erte", monday, monday + timedelta(days=90), share=40)
        for offset in range(5):
            Shift.objects.create(
                tenant=company,
                employee=worker,
                day=monday + timedelta(days=offset),
                segments=[{"start": "09:00", "end": "14:00"}],
            )
        findings = review_roster(company=company, first=monday, last=monday + timedelta(days=13))

    assert [f for f in findings if f.code == "rostered_on_leave"] == []


@pytest.mark.django_db
def test_nor_somebody_with_two_hours_at_the_doctor(company, worker):
    from datetime import time

    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        absence = request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=monday,
            end_date=monday,
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        absence.status = AbsenceStatus.APPROVED
        absence.save(update_fields=["status"])
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=monday,
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        findings = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    assert [f for f in findings if f.code == "rostered_on_leave"] == []


@pytest.mark.django_db
def test_but_a_whole_day_absence_still_is_flagged(company, worker):
    """El aviso existe para esto: planificar a quien no va a venir."""
    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        suspend(company, worker, "es.unpaid_leave", monday, monday + timedelta(days=30))
        Shift.objects.create(
            tenant=company,
            employee=worker,
            day=monday + timedelta(days=2),
            segments=[{"start": "08:00", "end": "16:00"}],
        )
        findings = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    assert any(f.code == "rostered_on_leave" for f in findings)


# ------------------------------------------------ quién registra qué (12/08)


def client_for(user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff(company):
    with tenant_context(company.id):
        from apps.users.models import Role

        yield {
            "boss": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
            "admin": User.objects.create_user(
                email="dire@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Ana",
                role=Role.ADMIN,
            ),
        }


@pytest.mark.django_db
def test_a_worker_cannot_request_an_erte_for_themselves(company, worker, staff):
    """Un ERTE es un acto de la empresa. Que la persona pudiera solicitárselo
    era la extralimitación de modelado que señaló la auditoría."""
    with tenant_context(company.id):
        erte = LeaveType.objects.get(code="es.erte")

    response = client_for(worker).post(
        "/api/absences/",
        {
            "leave_type": str(erte.id),
            "start_date": "2026-09-01",
            "end_date": "2026-11-30",
            "reduction_share": 40,
        },
        format="json",
    )

    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "company_recorded"


@pytest.mark.django_db
def test_the_company_records_it_directly_in_force(company, worker, staff):
    """Sin cola: no hay nada que decidir, solo que registrar."""
    with tenant_context(company.id):
        erte = LeaveType.objects.get(code="es.erte")

    response = client_for(staff["boss"]).post(
        "/api/absences/",
        {
            "employee": str(worker.id),
            "leave_type": str(erte.id),
            "start_date": "2026-09-01",
            "end_date": "2026-11-30",
            "reduction_share": 40,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "APPROVED"


@pytest.mark.django_db
def test_a_manager_recording_their_own_falls_back_to_the_queue(company, worker, staff):
    """Los cuatro ojos mandan también aquí: registrarse una suspensión a uno
    mismo queda pendiente para que la resuelva otra persona."""
    with tenant_context(company.id):
        strike = LeaveType.objects.get(code="es.strike")

    response = client_for(staff["boss"]).post(
        "/api/absences/",
        {
            "leave_type": str(strike.id),
            "start_date": "2026-09-01",
            "end_date": "2026-09-01",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"


@pytest.mark.django_db
def test_an_excedencia_is_still_the_persons_to_request(company, worker, staff):
    """Las excedencias las pide la persona: siguen el flujo de siempre."""
    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.unpaid_leave")

    response = client_for(worker).post(
        "/api/absences/",
        {
            "leave_type": str(kind.id),
            "start_date": "2026-09-01",
            "end_date": "2027-01-31",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"


# --------------------------------------- las dos varas del ERTE, igualadas


@pytest.mark.django_db
def test_hours_worked_are_measured_against_the_reduced_contract_too(company, worker):
    """Lo planificado ya se medía contra el contrato reducido; lo fichado
    seguía midiéndose contra el entero. Las horas entre medias, trabajadas
    durante un ERTE, son justo las que una inspección de un ERTE busca."""
    from datetime import datetime
    from datetime import time as dt_time

    from apps.punches.models import Punch, PunchType

    monday = date(2026, 9, 7)
    with tenant_context(company.id):
        suspend(company, worker, "es.erte", monday, monday + timedelta(days=90), share=40)
        # Cinco días de seis horas: 30 h. Por debajo de 40 (contrato entero) y
        # muy por encima de 24 (el 60 % que queda).
        zone = company.tzinfo
        for offset in range(5):
            day = monday + timedelta(days=offset)
            Punch.objects.create(
                tenant=company,
                employee=worker,
                punch_type=PunchType.IN,
                timestamp=datetime.combine(day, dt_time(8, 0), tzinfo=zone),
            )
            Punch.objects.create(
                tenant=company,
                employee=worker,
                punch_type=PunchType.OUT,
                timestamp=datetime.combine(day, dt_time(14, 0), tzinfo=zone),
            )
        findings = review_roster(company=company, first=monday, last=monday + timedelta(days=6))

    over = [f for f in findings if f.code == "worked_over_the_contract"]
    assert len(over) == 1
    assert "24 h" in str(over[0].message)


# ------------------------------------ los dos agujeros de la segunda auditoría
#
# Los cazaron sondas ejecutadas contra la API, no lectura de código: una
# trabajadora creó una «suspensión» sin tipo con reducción del 70 %, y una
# excedencia al 40 %. El primero rodeaba initiated_by entero; el segundo
# habría puesto el cuadrante a medir contra un contrato que nadie redujo
# lícitamente.


@pytest.mark.django_db
def test_a_suspension_must_say_which_one_it_is(company, worker):
    """Cruda no lleva artículo, no tiene nombre para el informe y ---lo que
    forzó esto--- no tiene initiated_by que respetar."""
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            absence_type="SUSPENSION",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 20),
            reduction_share=70,
        )

    assert caught.value.code == "suspension_needs_its_kind"


@pytest.mark.django_db
def test_an_excedencia_cannot_carry_a_reduction(company, worker):
    """La excedencia «al 40 %» no existe, y sigue sin existir.

    El criterio cambió el 28/08 y esta prueba se queda: antes reducir era cosa
    de lo que registraba la empresa ---ERTE, RED---, y eso dejaba fuera la
    reducción por guarda legal del art. 37.6, que la pide quien trabaja. Ahora
    lo decide el catálogo, tipo a tipo. Una excedencia voluntaria sigue sin
    poder reducir, que es lo que esta prueba defiende.
    """
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.unpaid_leave"),
            start_date=date(2027, 2, 1),
            end_date=date(2027, 6, 30),
            reduction_share=40,
        )

    assert caught.value.code == "this_leave_cannot_reduce_the_day"
