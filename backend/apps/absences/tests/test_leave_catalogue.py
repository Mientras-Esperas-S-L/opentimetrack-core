"""El catálogo de permisos y las ausencias de parte del día.

Dos huecos que iban juntos. Había cuatro tipos de ausencia —vacaciones, baja,
permiso personal y otros— así que los ocho permisos del art. 37.3 caían todos en
«permiso personal»; y una ausencia iba de una fecha a otra, sin horas, así que
irse a las once con fiebre no se podía registrar.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from rest_framework.test import APIClient

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import Absence, AbsenceStatus, AbsenceType, LeaveType
from apps.absences.services import request_absence, vacation_balance
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ------------------------------------------------------------- el catálogo


@pytest.mark.django_db
def test_the_country_catalogue_seeds_the_company(company):
    with tenant_context(company.id):
        result = seed_leave_types(company)
        codes = set(LeaveType.objects.values_list("code", flat=True))

    assert result["added"] > 10
    # Los ocho del art. 37.3, que eran los que no cabían.
    assert {"es.marriage", "es.bereavement", "es.force_majeure", "es.public_duty"} <= codes


@pytest.mark.django_db
def test_seeding_twice_adds_nothing_and_changes_nothing(company):
    """Se copia, no se referencia: el convenio mejora cualquiera de estas cifras
    y una corrección nuestra no puede reescribir lo que alguien negoció."""
    with tenant_context(company.id):
        seed_leave_types(company)
        mudanza = LeaveType.objects.get(code="es.moving_house")
        mudanza.amount = 2  # el convenio da dos días
        mudanza.save(update_fields=["amount"])

        again = seed_leave_types(company)
        mudanza.refresh_from_db()

    assert again["added"] == 0
    assert mudanza.amount == 2


@pytest.mark.django_db
def test_the_entitlement_keeps_its_unit(company):
    """Quince días naturales por boda y cuatro laborables al año no son «cuatro
    días» en un campo que no dice cuál."""
    with tenant_context(company.id):
        seed_leave_types(company)
        boda = LeaveType.objects.get(code="es.marriage")
        fuerza = LeaveType.objects.get(code="es.force_majeure")

    assert (boda.amount, boda.unit, boda.period) == (15, "DAYS_CALENDAR", "EVENT")
    assert (fuerza.amount, fuerza.unit, fuerza.period) == (4, "DAYS_WORKING", "YEAR")


@pytest.mark.django_db
def test_the_two_extra_days_for_travelling_are_a_condition_not_the_amount(company):
    """El art. 37.3.b bis da dos días y cuatro es una condición. Un catálogo que
    dijera cuatro estaría regalando días que nadie concedió."""
    with tenant_context(company.id):
        seed_leave_types(company)
        luto = LeaveType.objects.get(code="es.bereavement")

    assert luto.amount == 2
    assert luto.extra_when_travelling == 2


@pytest.mark.django_db
def test_the_parental_leave_is_unpaid(company):
    """Lo que más se confunde de él."""
    with tenant_context(company.id):
        seed_leave_types(company)
        assert LeaveType.objects.get(code="es.parental").paid is False


# --------------------------------------------------- las ausencias por horas


@pytest.mark.django_db
def test_leaving_at_eleven_can_be_recorded(company, worker):
    with tenant_context(company.id):
        seed_leave_types(company)
        absence = request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            start_time=time(11, 0),
            end_time=time(14, 30),
            reason="Consulta",
        )

    assert absence.is_partial
    assert absence.hours == 3.5
    # La familia sale del tipo, para que no puedan discrepar.
    assert absence.absence_type == "PAID_LEAVE"


@pytest.mark.django_db
def test_a_partial_absence_does_not_block_clocking(company, worker):
    """Quien se fue a las once con fiebre trabajó la mañana. Impedirle fichar la
    salida dejaría el día abierto, que es lo único que un registro no puede
    hacer nunca."""
    with tenant_context(company.id):
        seed_leave_types(company)
        absence = request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=date.today(),
            end_date=date.today(),
            start_time=time(11, 0),
            end_time=time(14, 0),
        )
        absence.status = AbsenceStatus.APPROVED
        absence.save(update_fields=["status"])

        assert register_punch(employee=worker, company=company) is not None


@pytest.mark.django_db
def test_a_whole_day_one_still_does(company, worker):
    """El día de la empresa, no el del contenedor.

    Estaba escrito con `date.today()`, que es la fecha **UTC** del contenedor, y
    `register_punch` mira el día de la empresa. Entre medianoche y las dos de la
    madrugada en Madrid las dos no coinciden: la ausencia quedaba en el día
    anterior, el fichaje no chocaba con nada y la prueba fallaba sola.

    Es exactamente la trampa por la que existe `apps/common/clock.py`, esta vez
    dentro de una prueba --- donde no la miraba nadie porque el aviso está en el
    módulo del producto.
    """
    with tenant_context(company.id):
        hoy = local_today(company)
        Absence.objects.create(
            tenant=company,
            employee=worker,
            absence_type=AbsenceType.VACATION,
            start_date=hoy,
            end_date=hoy,
            status=AbsenceStatus.APPROVED,
        )
        with pytest.raises(BusinessRuleError) as caught:
            register_punch(employee=worker, company=company)

    assert caught.value.code == "punch_blocked_by_absence"


@pytest.mark.django_db
def test_holiday_cannot_be_half_a_day(company, worker):
    """El saldo está en días. Medio día redondearía --- regalando o comiéndose
    un día que nadie decidió --- o convertiría el saldo en un decimal que la ley
    no usa."""
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=worker,
            company=company,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            start_time=time(9, 0),
            end_time=time(13, 0),
        )

    assert caught.value.code == "holiday_is_whole_days"


@pytest.mark.django_db
def test_part_of_a_day_is_one_day(company, worker):
    """«Del lunes a las dos al miércoles a las once» es una forma que la
    aritmética sabe expresar y que nadie pide."""
    from django.core.exceptions import ValidationError

    with tenant_context(company.id), pytest.raises(ValidationError):
        Absence(
            tenant=company,
            employee=worker,
            absence_type="PAID_LEAVE",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            start_time=time(14, 0),
            end_time=time(18, 0),
        ).clean()


@pytest.mark.django_db
def test_half_a_range_is_not_a_range(company, worker):
    from django.core.exceptions import ValidationError

    with tenant_context(company.id), pytest.raises(ValidationError):
        Absence(
            tenant=company,
            employee=worker,
            absence_type="PAID_LEAVE",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            start_time=time(14, 0),
        ).clean()


@pytest.mark.django_db
def test_a_partial_absence_does_not_touch_the_holiday_balance(company, worker):
    with tenant_context(company.id):
        seed_leave_types(company)
        request_absence(
            employee=worker,
            company=company,
            leave_type=LeaveType.objects.get(code="es.medical"),
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        balance = vacation_balance(worker, company, date(2026, 8, 1))

    assert balance.taken == 0
    assert balance.pending == 0


# ------------------------------------------------------------------- la API


@pytest.mark.django_db
def test_the_catalogue_says_what_each_one_grants(company, worker):
    with tenant_context(company.id):
        seed_leave_types(company)

    rows = client_for(worker).get("/api/leave-types/").json()["results"]
    boda = next(r for r in rows if r["code"] == "es.marriage")

    assert boda["basis"] == "Art. 37.3.a ET"
    assert "15" in boda["allowance"]
    # El que no tiene tope se dice con palabras, no con un hueco.
    médica = next(r for r in rows if r["code"] == "es.medical")
    assert médica["amount"] is None
    assert médica["measured_in_hours"] is True


@pytest.mark.django_db
def test_a_type_in_use_is_not_deleted(company, worker):
    """Borrarlo le quitaría el motivo a registros que tienen que sobrevivir
    cuatro años."""
    with tenant_context(company.id):
        admin = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            role=Role.ADMIN,
        )
        seed_leave_types(company)
        kind = LeaveType.objects.get(code="es.moving_house")
        request_absence(
            employee=worker,
            company=company,
            leave_type=kind,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
        )

    response = client_for(admin).delete(f"/api/leave-types/{kind.id}/")

    assert response.status_code >= 400
    with tenant_context(company.id):
        assert LeaveType.objects.filter(pk=kind.pk).exists()
