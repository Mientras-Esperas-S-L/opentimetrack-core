"""La reducción de jornada por guarda legal, que el producto rechazaba.

El mecanismo para reducir la jornada ---una fracción, unas fechas, y el cuadrante
midiendo contra lo reducido--- existía entero desde el ERTE. Estaba cerrado con
esta condición:

    if reduction_share is not None and leave_type.initiated_by != "COMPANY":
        raise BusinessRuleError(code="reduction_is_company_recorded", ...)

y el razonamiento escrito al lado era bueno: una excedencia voluntaria «al 40 %»
no existe en la ley, y si se colara, el cuadrante empezaría a medir a esa persona
contra un contrato que nadie redujo.

Lo que no consideró es que **la reducción más corriente de todas la pide quien
trabaja**. El art. 37.6 es un derecho suyo, no un acto de la empresa, así que
caía del lado prohibido. La única forma de apuntarla era escribirla en el horario
contratado ---en la demostración estaba literalmente como «L-V 09:00-15:00
(guarda legal)»---, donde no hay fracción, no hay fechas y **nadie se entera de
que el derecho se acaba** cuando el menor cumple doce años.

Lo que decide ahora no es quién lo registra sino si el artículo lo permite, y eso
lo dice el catálogo tipo a tipo.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.absences.models import Absence, AbsenceStatus, AbsenceType, LeaveType
from apps.absences.services import request_absence
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import HoursPeriod, Role, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Guarda SL", tax_id="B21212121", time_zone="Europe/Madrid", country="ES"
    )
    from apps.absences.catalogue import seed_leave_types

    with tenant_context(empresa.id):
        seed_leave_types(empresa)
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="elena@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Elena",
            last_name="Prats",
            role=Role.EMPLOYEE,
            regime=WorkingTimeRegime.REDUCED,
            contracted_hours=40,
            contracted_period=HoursPeriod.WEEK,
        )


def pide_la_reduccion(company, quien, share, *, desde=date(2026, 8, 1), hasta=date(2030, 7, 31)):
    return request_absence(
        employee=quien,
        company=company,
        leave_type=LeaveType.objects.get(code="es.childcare_reduced_hours"),
        start_date=desde,
        end_date=hasta,
        reduction_share=share,
    )


@pytest.mark.django_db
def test_la_puede_pedir_quien_trabaja(company, quien):
    """Lo que antes daba `reduction_is_company_recorded`.

    `reduction_share` es **cuánto se reduce**, no cuánto se trabaja: el modelo lo
    dice sin lugar a dudas ---«40 means they work 60 %»--- y lo escribí al revés
    la primera vez, hasta en la nota que lee quien registra la solicitud. Un
    cuarto de reducción es 25.
    """
    with tenant_context(company.id):
        ausencia = pide_la_reduccion(company, quien, 25)

        assert ausencia.reduction_share == 25
        assert ausencia.absence_type == AbsenceType.SUSPENSION
        # Y con sus fechas, que es la mitad del asunto: **este derecho se
        # acaba**, y apuntado en el horario contratado no se acababa nunca.
        assert ausencia.start_date == date(2026, 8, 1)
        assert ausencia.end_date == date(2030, 7, 31)


@pytest.mark.django_db
def test_una_excedencia_voluntaria_sigue_sin_poder_reducir(company, quien):
    """El contraste del criterio nuevo.

    Si «puede reducir» se hubiera abierto a todo lo que pide la persona ---que
    es el atajo evidente al quitar la condición vieja--- esto pasaría, y el
    cuadrante mediría a alguien contra una jornada que nadie redujo. Lo que
    cambió es que la lista de quién puede la escribe el catálogo, no la forma de
    registrarse.
    """
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        request_absence(
            employee=quien,
            company=company,
            leave_type=LeaveType.objects.get(code="es.unpaid_leave"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 31),
            reduction_share=40,
        )

    assert caught.value.code == "this_leave_cannot_reduce_the_day"


@pytest.mark.django_db
def test_el_erte_sigue_pudiendo(company, quien):
    """El campo nace en `False`, así que hay que decir quién sí.

    La regresión que acecha: el ERTE y el mecanismo RED reducían por el criterio
    viejo ---los registra la empresa--- y con el campo nuevo dejarían de poder
    hacerlo si nadie los marca, sin que nadie toque nada. El cuadrante volvería a
    medir contra la jornada entera a quien la tiene reducida.

    **Lo que esta prueba fija es el catálogo, no la migración.** El contraste lo
    dejó claro: vaciando la lista de la migración `0015`, esto sigue pasando,
    porque la fixture siembra desde `apps.legal.es` y no desde el historial de
    migraciones. Para las empresas **ya creadas** ---que no vuelven a sembrar---
    quien lleva ese mismo criterio es la migración, y eso se comprueba
    aplicándola, no aquí.
    """
    with tenant_context(company.id):
        assert LeaveType.objects.get(code="es.erte").can_reduce_the_day
        assert LeaveType.objects.get(code="es.red").can_reduce_the_day
        assert not LeaveType.objects.get(code="es.unpaid_leave").can_reduce_the_day


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("share", "avisa"),
    [
        (12.5, False),  # un octavo, el mínimo del derecho
        (25, False),  # un cuarto
        (50, False),  # la mitad, el máximo
        (60, True),  # pasa de la mitad
        (5, True),  # no llega al octavo
    ],
    ids=["un octavo", "un cuarto", "la mitad", "más de la mitad", "menos de un octavo"],
)
def test_la_horquilla_del_articulo_avisa_y_no_impide(company, quien, share, avisa):
    """«Entre, al menos, un octavo y un máximo de la mitad de la jornada.»

    Se sigue trabajando entre el 50 % y el 87,5 %. Fuera de ahí **se avisa y se
    registra igual**: el artículo delimita el derecho, no lo que las partes
    puedan acordar, y un convenio puede mejorar las condiciones. Bloquearlo
    obligaría a apuntar la reducción en el horario contratado otra vez, que es
    justo de donde se la ha sacado.

    Los bordes van dentro a propósito: reducir exactamente un octavo o
    exactamente la mitad es ejercicio del derecho, no un exceso.
    """
    with tenant_context(company.id):
        ausencia = pide_la_reduccion(company, quien, share)
        # Se registra pase lo que pase. Esto es la mitad de la prueba.
        assert Absence.objects.filter(pk=ausencia.pk).exists()

        ausencia.status = AbsenceStatus.APPROVED
        ausencia.save(update_fields=["status"])

        codigos = [
            f.code
            for f in review_roster(company=company, first=date(2026, 8, 3), last=date(2026, 8, 9))
        ]
        assert ("reduction_outside_the_right" in codigos) is avisa


@pytest.mark.django_db
def test_el_cuadrante_mide_contra_la_jornada_reducida(company, quien):
    """Para lo que sirve todo esto: que no se le exijan las horas de antes.

    Con la reducción apuntada en el horario contratado, el cuadrante medía a
    Elena contra su contrato entero o contra una cifra escrita a mano que no
    caducaba nunca. Ahora sale de la fracción, y **se acaba sola** el día que
    termina el derecho.
    """
    from apps.shifts.services import _reduced_share

    with tenant_context(company.id):
        ausencia = pide_la_reduccion(company, quien, 25)
        ausencia.status = AbsenceStatus.APPROVED
        ausencia.save(update_fields=["status"])

        # Dentro: se espera el 75 % de la jornada.
        assert _reduced_share(quien, date(2026, 8, 3), date(2026, 8, 9)) == 0.75

        # Y después de que el derecho termine, la jornada entera otra vez, sin
        # que nadie tenga que acordarse de deshacerlo.
        assert _reduced_share(quien, date(2030, 8, 5), date(2030, 8, 11)) == 1
