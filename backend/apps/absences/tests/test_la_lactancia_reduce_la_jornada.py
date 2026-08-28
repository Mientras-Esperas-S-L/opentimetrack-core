"""La lactancia se puede pedir como reducción, no solo como hora de ausencia.

El art. 37.4 da **dos formas y las elige quien trabaja**: «una hora de ausencia
del trabajo, que podrán dividir en dos fracciones», o «reducir su jornada en
media hora». El catálogo del país solo traía la primera, así que la copia de cada
empresa nació sin poder reducir y **la mitad del derecho se rechazaba al
pedirla**.

Dos cosas que la distinguen de la reducción por guarda legal, y que explican por
qué no vale con copiar aquélla:

- **Es retribuida.** La del art. 37.6 lleva reducción proporcional de salario; la
  lactancia no, es un permiso pagado. Por eso `paid` sigue en `True` aunque
  reduzca la jornada.
- **No le aplica el rango de un octavo a la mitad.** Media hora de una jornada de
  ocho es un dieciseisavo, por debajo del mínimo del art. 37.6. Ese aviso está
  atado al código de la guarda legal, y tiene que seguir estándolo: sacarlo a
  todas las reducciones convertiría el ejercicio normal de este derecho en un
  incumplimiento aparente.
"""

from __future__ import annotations

import pytest

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import LeaveType
from apps.common.models import tenant_context
from apps.tenants.models import Tenant

LACTANCIA = "es.breastfeeding"
GUARDA_LEGAL = "es.childcare_reduced_hours"


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        seed_leave_types(empresa)
    return empresa


def permiso(company, code):
    with tenant_context(company.id):
        return LeaveType.objects.get(code=code)


@pytest.mark.django_db
def test_la_lactancia_puede_reducir_la_jornada(company):
    """La mitad del derecho que no se podía ejercer."""
    assert permiso(company, LACTANCIA).can_reduce_the_day is True


@pytest.mark.django_db
def test_y_sigue_siendo_retribuida(company):
    """El contraste de copiar la guarda legal sin mirar.

    La del art. 37.6 va con reducción proporcional de salario y está marcada
    `paid=False`. Traer ese `False` de arrastre convertiría un permiso pagado en
    uno que no lo es, y eso llega a la nómina de alguien.
    """
    assert permiso(company, LACTANCIA).paid is True
    assert permiso(company, GUARDA_LEGAL).paid is False


@pytest.mark.django_db
def test_la_de_guarda_legal_sigue_siendo_la_que_es(company):
    """Nada de lo de arriba puede haber tocado a la otra."""
    otra = permiso(company, GUARDA_LEGAL)
    assert otra.can_reduce_the_day is True
    assert otra.initiated_by == "PERSON"


@pytest.mark.django_db
def test_la_pide_quien_trabaja(company):
    """Las dos formas las elige quien trabaja, no la empresa (art. 37.4).

    Un permiso con `initiated_by="COMPANY"` se registra en firme sin pasar por
    nadie, y aquí eso sería la empresa decidiendo cómo ejerce alguien su derecho.
    """
    assert permiso(company, LACTANCIA).initiated_by == "PERSON"


@pytest.mark.django_db
def test_una_empresa_recien_creada_ya_lo_trae(company):
    """El contraste del backfill: si el marco no lo llevara, no habría qué migrar.

    Esta prueba y el backfill cubren las dos mitades del mismo problema ---las
    empresas nuevas y las que ya existían--- y ninguna de las dos sirve sola.
    """
    otra = Tenant.objects.create(
        name="Nueva SL", tax_id="B45454545", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(otra.id):
        seed_leave_types(otra)
    assert permiso(otra, LACTANCIA).can_reduce_the_day is True
