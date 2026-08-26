"""Dos peticiones de la misma ausencia a la vez pasaban las dos.

La comprobación de solapamiento lee la cola sin bloquear nada, así que dos
peticiones simultáneas ven la misma cola y las dos escriben. Medido con dos hilos
y una barrera, contra el servidor de desarrollo:

| | Rondas con dos solicitudes | Solape real |
|---|---|---|
| Antes | **12 de 12** | 37 ms |
| Después | 0 de 12 | 34 ms |

Lo que pasa después está escrito en el docstring de `_overlapping`, que ya lo
sabía: «quien apruebe la segunda crea una contradicción que nadie caza». Y si se
aprueban las dos, el saldo de vacaciones se descuenta dos veces y el cuadrante ve
el día doblemente ocupado.

## Sin hilos, por lo mismo que `apps/common/tests/test_dos_a_la_vez.py`

`transaction=True` vacía las tablas con TRUNCATE en el desmontaje y el rastro de
auditoría lo rechaza --- es uno de los tres disparadores que lo hacen inmutable.
Lo que se comprueba aquí es determinista: que pedir una ausencia **bloquea la
fila de la persona antes de mirar la cola**, que es la única forma de que esa
comprobación signifique algo con dos transacciones de verdad.

Se bloquea a la persona y no las filas de sus ausencias porque las que hay que
impedir todavía no existen: no hay nada que bloquear ahí.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.absences.models import Absence, AbsenceType
from apps.absences.services import request_absence
from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con vacaciones", tax_id="B17171717", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="pide@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Pide",
            last_name="Equis",
        )


def pide(company, quien, dia):
    return request_absence(
        employee=quien,
        company=company,
        absence_type=AbsenceType.PAID_LEAVE,
        start_date=dia,
        end_date=dia,
        requested_by=quien,
    )


@pytest.mark.django_db
def test_pedirla_bloquea_a_la_persona_antes_de_mirar_la_cola(company, quien):
    dia = timezone.now().date() + timedelta(days=30)

    with tenant_context(company.id), CaptureQueriesContext(connection) as capturadas:
        pide(company, quien, dia)

    consultas = [c["sql"] for c in capturadas]
    bloqueos = [i for i, sql in enumerate(consultas) if "FOR UPDATE" in sql.upper()]
    assert bloqueos, "pedir una ausencia no bloquea nada: dos a la vez verán la misma cola"
    assert any("users_user" in consultas[i].lower() for i in bloqueos), [
        consultas[i] for i in bloqueos
    ]

    lecturas = [
        i
        for i, sql in enumerate(consultas)
        if "absences_absence" in sql.lower() and sql.strip().upper().startswith("SELECT")
    ]
    assert lecturas, "el control falla: ya no se consulta la cola de ausencias"
    assert min(bloqueos) < min(lecturas), (
        "el bloqueo va después de leer la cola, así que no protege"
    )


@pytest.mark.django_db
def test_y_el_solapamiento_sigue_rechazandose(company, quien):
    """El control. Un bloqueo que rompiera la comprobación pasaría la de arriba."""
    dia = timezone.now().date() + timedelta(days=40)
    with tenant_context(company.id):
        pide(company, quien, dia)

        with pytest.raises(BusinessRuleError) as caso:
            pide(company, quien, dia)

    assert caso.value.code == "overlapping_absence"
    with tenant_context(company.id):
        assert Absence.objects.filter(employee=quien, start_date=dia).count() == 1


@pytest.mark.django_db
def test_una_sola_peticion_sigue_saliendo(company, quien):
    """Y el otro control: pedir vacaciones tiene que seguir funcionando."""
    dia = timezone.now().date() + timedelta(days=50)
    with tenant_context(company.id):
        pedida = pide(company, quien, dia)

    assert pedida.start_date == dia
    with tenant_context(company.id):
        assert Absence.objects.filter(employee=quien).count() == 1
