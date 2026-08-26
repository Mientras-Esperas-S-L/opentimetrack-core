"""Cuánto queda de cada permiso.

El catálogo dice lo que concede cada uno; esto dice lo que ya se ha gastado, que
es la pregunta que hace una gestoría. Tres cosas deciden la aritmética y las
tres salen del tipo: qué lo reinicia, qué periodo y en qué unidad.
"""

from __future__ import annotations

from datetime import date, time

import pytest

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import AbsenceStatus, LeaveType
from apps.absences.services import approve_absence, leave_over_the_limit, request_absence
from apps.absences.usage import leave_usage, period_for, usage_summary
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def world(company):
    with tenant_context(company.id):
        seed_leave_types(company)
        yield {
            "worker": User.objects.create_user(
                email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
            ),
            "boss": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
        }


def ask(company, who, code, first, last, **extra):
    with tenant_context(company.id):
        return request_absence(
            employee=who,
            company=company,
            leave_type=LeaveType.objects.get(code=code),
            start_date=first,
            end_date=last,
            **extra,
        )


# ------------------------------------------------------------- los periodos


def test_the_year_is_the_calendar_year():
    """A propósito, y no el periodo de vacaciones de la empresa: ese es del art.
    38 y usarlo aquí aplicaría un año de abril a marzo a la fuerza mayor
    familiar, cuyo artículo dice «al año» y nada más."""

    class Kind:
        period = "YEAR"

    assert period_for(Kind(), date(2026, 7, 15)) == (date(2026, 1, 1), date(2026, 12, 31))


def test_the_week_starts_on_monday():
    class Kind:
        period = "WEEK"

    # 2026-08-12 es miércoles.
    assert period_for(Kind(), date(2026, 8, 12)) == (date(2026, 8, 10), date(2026, 8, 16))


def test_an_event_permit_has_no_period():
    """Quince días por boda no se acumulan: cada solicitud va por su cuenta."""

    class Kind:
        period = "EVENT"

    assert period_for(Kind(), date(2026, 8, 12)) == (None, None)


# --------------------------------------------------------------- el consumo


@pytest.mark.django_db
def test_the_four_days_of_family_emergency_add_up_across_the_year(company, world):
    # Art. 37.9: cuatro días laborables al año.
    ask(company, world["worker"], "es.force_majeure", date(2026, 3, 2), date(2026, 3, 3))
    ask(company, world["worker"], "es.force_majeure", date(2026, 9, 1), date(2026, 9, 1))

    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.force_majeure")
        usage = leave_usage(world["worker"], kind, company, date(2026, 10, 1))

    assert usage.used == 3
    assert usage.allowance == 4
    assert usage.remaining == 1
    assert usage.over is False


@pytest.mark.django_db
def test_last_year_does_not_count_against_this_one(company, world):
    ask(company, world["worker"], "es.force_majeure", date(2025, 3, 2), date(2025, 3, 5))

    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.force_majeure")
        assert leave_usage(world["worker"], kind, company, date(2026, 10, 1)).used == 0


@pytest.mark.django_db
def test_a_pending_request_counts_too(company, world):
    """Enseñarlo como disponible es como acaban dos personas reservando el
    mismo último día: lo mismo que ya hacía el saldo de vacaciones."""
    ask(company, world["worker"], "es.force_majeure", date(2026, 3, 2), date(2026, 3, 5))

    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.force_majeure")
        assert leave_usage(world["worker"], kind, company, date(2026, 4, 1)).used == 4


@pytest.mark.django_db
def test_a_weekend_does_not_count_on_a_working_day_permit(company, world):
    """La fuerza mayor va en días laborables. Del 5 al 8 de marzo de 2026 son
    jueves, viernes, sábado y domingo: dos laborables."""
    ask(company, world["worker"], "es.force_majeure", date(2026, 3, 5), date(2026, 3, 8))

    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.force_majeure")
        assert leave_usage(world["worker"], kind, company, date(2026, 4, 1)).used == 2


@pytest.mark.django_db
def test_hours_add_up_on_an_hourly_permit(company, world):
    """Seis horas a la semana de búsqueda de empleo, art. 53.2."""
    monday = date(2026, 8, 10)
    ask(
        company,
        world["worker"],
        "es.job_search",
        monday,
        monday,
        start_time=time(9, 0),
        end_time=time(11, 30),
    )
    ask(
        company,
        world["worker"],
        "es.job_search",
        monday,
        monday,
        start_time=time(15, 0),
        end_time=time(16, 0),
    )

    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.job_search")
        usage = leave_usage(world["worker"], kind, company, monday)

    assert usage.used == 3.5
    assert usage.remaining == 2.5


@pytest.mark.django_db
def test_part_of_a_day_is_a_fraction_of_a_day(company, world):
    """Contarla como un día entero cobraría un día por dos horas; contarla como
    cero dejaría el tope sin efecto por la puerta de atrás."""
    ask(
        company,
        world["worker"],
        "es.force_majeure",
        date(2026, 3, 2),
        date(2026, 3, 2),
        start_time=time(9, 0),
        end_time=time(13, 0),
    )

    with tenant_context(company.id):
        kind = LeaveType.objects.get(code="es.force_majeure")
        usage = leave_usage(world["worker"], kind, company, date(2026, 4, 1))

    # Cuatro horas de una jornada de ocho: medio día.
    assert usage.used == 0.5
    # Y se dice que la duración de la jornada se ha supuesto, porque no hay
    # cuadrante del que leerla.
    assert usage.estimated is True


# ----------------------------------------------------------- pasarse del tope


@pytest.mark.django_db
def test_going_over_is_reported_at_the_moment_of_deciding(company, world):
    """Nunca se impide: todos los topes del catálogo son el suelo legal y el
    convenio mejora cualquiera. Una empresa que no haya actualizado su copia se
    encontraría el producto negando días a los que su gente tiene derecho."""
    absence = ask(company, world["worker"], "es.force_majeure", date(2026, 3, 2), date(2026, 3, 6))

    with tenant_context(company.id):
        over = leave_over_the_limit(absence)

    assert over is not None
    assert over["used"] == 5
    assert over["allowance"] == 4
    assert over["remaining"] == -1


@pytest.mark.django_db
def test_and_approving_still_works(company, world):
    absence = ask(company, world["worker"], "es.force_majeure", date(2026, 3, 2), date(2026, 3, 6))

    with tenant_context(company.id):
        approved = approve_absence(absence, resolved_by=world["boss"])

    assert approved.status == AbsenceStatus.APPROVED


@pytest.mark.django_db
def test_a_permit_with_no_limit_is_never_over(company, world):
    """«El tiempo indispensable» no tiene de qué pasarse."""
    absence = ask(company, world["worker"], "es.public_duty", date(2026, 3, 2), date(2026, 3, 20))

    with tenant_context(company.id):
        assert leave_over_the_limit(absence) is None


@pytest.mark.django_db
def test_the_summary_only_lists_what_has_a_limit(company, world):
    """Un permiso que da «el tiempo indispensable» no tiene de qué quedar, y una
    fila diciéndolo en cada pantalla sería ruido alrededor de las que importan."""
    with tenant_context(company.id):
        rows = usage_summary(world["worker"], company, date(2026, 4, 1))

    names = {row["name"] for row in rows}
    assert "Fuerza mayor familiar" in names
    assert "Deber inexcusable de carácter público y personal" not in names
    # Y tampoco las de por evento: quince días por boda no se acumulan.
    assert "Matrimonio o registro de pareja de hecho" not in names


# --------------------------------------------------------------- los solapes


@pytest.mark.django_db
def test_two_part_days_on_the_same_date_do_not_clash(company, world):
    """Dos horas en el médico por la mañana y una buscando empleo por la tarde
    son dos ausencias un martes y ninguna contradicción. Las seis horas a la
    semana del art. 53.2 son un permiso que se espera partir."""
    monday = date(2026, 8, 10)
    ask(
        company,
        world["worker"],
        "es.medical",
        monday,
        monday,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    ask(
        company,
        world["worker"],
        "es.job_search",
        monday,
        monday,
        start_time=time(15, 0),
        end_time=time(17, 0),
    )

    with tenant_context(company.id):
        from apps.absences.models import Absence

        assert Absence.objects.filter(employee=world["worker"], start_date=monday).count() == 2


@pytest.mark.django_db
def test_but_overlapping_hours_do(company, world):
    from apps.common.exceptions import BusinessRuleError

    monday = date(2026, 8, 10)
    ask(
        company,
        world["worker"],
        "es.medical",
        monday,
        monday,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )

    with pytest.raises(BusinessRuleError) as caught:
        ask(
            company,
            world["worker"],
            "es.job_search",
            monday,
            monday,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )

    assert caught.value.code == "overlapping_absence"


@pytest.mark.django_db
def test_touching_at_the_edge_is_not_overlapping(company, world):
    """Irse a las once y volver a las once es una cosa detrás de otra, no dos a
    la vez."""
    monday = date(2026, 8, 10)
    ask(
        company,
        world["worker"],
        "es.medical",
        monday,
        monday,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    ask(
        company,
        world["worker"],
        "es.job_search",
        monday,
        monday,
        start_time=time(11, 0),
        end_time=time(13, 0),
    )

    with tenant_context(company.id):
        from apps.absences.models import Absence

        assert Absence.objects.filter(employee=world["worker"], start_date=monday).count() == 2


@pytest.mark.django_db
def test_a_whole_day_still_claims_the_whole_day(company, world):
    from apps.common.exceptions import BusinessRuleError

    monday = date(2026, 8, 10)
    ask(company, world["worker"], "es.moving_house", monday, monday)

    with pytest.raises(BusinessRuleError):
        ask(
            company,
            world["worker"],
            "es.medical",
            monday,
            monday,
            start_time=time(9, 0),
            end_time=time(11, 0),
        )


# ----------------------------------------- el tope por evento avisa (12/08)
#
# Los permisos «por evento» no acumulan nada, así que «lo que queda» no existe
# --- y quien aprobaba no veía ningún aviso mientras quien pedía sí. La
# comparación que sí existe es esta solicitud contra lo que concede, en SU
# unidad.


@pytest.mark.django_db
def test_a_thirty_day_wedding_warns_the_approver(company, world):
    absence = ask(company, world["worker"], "es.marriage", date(2026, 10, 1), date(2026, 10, 30))

    with tenant_context(company.id):
        over = leave_over_the_limit(absence)

    assert over is not None
    assert over["used"] == 30
    assert over["allowance"] == 15


@pytest.mark.django_db
def test_weeks_are_compared_in_weeks(company, world):
    """Ocho semanas de permiso parental son 56 días: pedir 42 (seis semanas) no
    puede avisar, y pedir 70 (diez) sí."""
    fine = ask(company, world["worker"], "es.parental", date(2026, 3, 2), date(2026, 4, 12))
    with tenant_context(company.id):
        assert leave_over_the_limit(fine) is None

    over = ask(company, world["worker"], "es.parental", date(2027, 3, 1), date(2027, 5, 9))
    with tenant_context(company.id):
        result = leave_over_the_limit(over)

    assert result is not None
    assert result["used"] == 10.0
    assert result["allowance"] == 8


@pytest.mark.django_db
def test_the_travelling_extra_is_not_an_excess(company, world):
    """Cuatro días de luto con desplazamiento son lícitos (2+2): avisar de eso
    enseñaría a ignorar el aviso. Cinco ya no."""
    fine = ask(company, world["worker"], "es.bereavement", date(2026, 3, 2), date(2026, 3, 5))
    with tenant_context(company.id):
        assert leave_over_the_limit(fine) is None

    over = ask(company, world["worker"], "es.bereavement", date(2026, 6, 1), date(2026, 6, 5))
    with tenant_context(company.id):
        result = leave_over_the_limit(over)

    assert result is not None
    assert result["used"] == 5
    assert result["travel_extra"] == 2


# ------------------------------------- la jornada de quien no trabaja la entera


@pytest.fixture
def a_tiempo_parcial(company):
    """Veinte horas a la semana: su día son cuatro, no ocho."""
    from apps.users.models import HoursPeriod, WorkingTimeRegime

    with tenant_context(company.id):
        seed_leave_types(company)
        yield User.objects.create_user(
            email="parcial@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            regime=WorkingTimeRegime.PART_TIME,
            contracted_hours=20,
            contracted_period=HoursPeriod.WEEK,
        )


@pytest.mark.django_db
def test_un_dia_entero_suyo_son_sus_horas_no_las_de_la_empresa(company, a_tiempo_parcial):
    """El caso (b) del hallazgo: seis horas de búsqueda de empleo (art. 53.2).

    Ana se ausenta **un día suyo**, que son cuatro horas. Contarlo con la semana
    de la empresa lo convierte en ocho, y el producto le dice que ha agotado y
    superado un permiso legal habiéndose ausentado 4 de las 6 horas a las que
    tiene derecho. `over=True` es lo que ve quien aprueba, justo durante un
    preaviso, que es cuando más falta le hacen.
    """
    with tenant_context(company.id):
        tipo = LeaveType.objects.get(tenant=company, code="es.job_search")
        request_absence(
            employee=a_tiempo_parcial,
            company=company,
            leave_type=tipo,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 7),
        )
        consumo = leave_usage(
            employee=a_tiempo_parcial, company=company, leave_type=tipo, on=date(2026, 9, 7)
        )

    assert consumo.used == 4.0, "su día son cuatro horas, no la semana de la empresa entre cinco"
    assert consumo.over is False


@pytest.mark.django_db
def test_lo_que_concede_el_permiso_se_mide_en_su_jornada(company, a_tiempo_parcial):
    """El caso (a): cuatro días al año de fuerza mayor (art. 37.9), pedidos por horas.

    Cuatro jornadas suyas son dieciséis horas. Medirlas contra días de ocho le
    concedía ocho jornadas: el doble de lo que el artículo obliga, sin que la
    empresa se entere.
    """
    with tenant_context(company.id):
        tipo = LeaveType.objects.get(tenant=company, code="es.force_majeure")
        for dia in (1, 2, 3, 4, 7):
            request_absence(
                employee=a_tiempo_parcial,
                company=company,
                leave_type=tipo,
                start_date=date(2026, 9, dia),
                end_date=date(2026, 9, dia),
                start_time=time(9, 0),
                end_time=time(13, 0),
            )
        consumo = leave_usage(
            employee=a_tiempo_parcial, company=company, leave_type=tipo, on=date(2026, 9, 7)
        )

    # Cinco ausencias de cuatro horas son cinco jornadas suyas: se ha pasado.
    assert consumo.used == 5.0
    assert consumo.over is True


@pytest.mark.django_db
def test_a_jornada_completa_sigue_saliendo_la_semana_de_la_empresa(company, world):
    """El contraste. Sin horas pactadas propias, la referencia sigue siendo la
    empresa, y eso no debe cambiar."""
    with tenant_context(company.id):
        tipo = LeaveType.objects.get(tenant=company, code="es.job_search")
        request_absence(
            employee=world["worker"],
            company=company,
            leave_type=tipo,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 7),
        )
        consumo = leave_usage(
            employee=world["worker"], company=company, leave_type=tipo, on=date(2026, 9, 7)
        )

    assert consumo.used == 8.0
