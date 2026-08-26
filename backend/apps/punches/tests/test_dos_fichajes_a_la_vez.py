"""Dos peticiones a la vez no son dos pulsaciones seguidas.

`test_double_tap` cubre el doble toque **secuencial**. Su propio docstring nombra
lo que quedaba fuera ---«ni dos pestañas, ni un terminal, ni un conector»--- y
todos ésos son **simultáneos**.

La protección compara con el último fichaje leído de la base, sin bloquear nada.
Dos peticiones a la vez leen el mismo «último» y las dos pasan. Medido a mano con
dos hilos y una barrera, contra el servidor de desarrollo:

| | Rondas con dos fichajes | Solape real |
|---|---|---|
| Antes | **14 de 15** | 35 ms |
| Después | 0 de 15 | 32 ms |

Y la primera medición fue de **una sola ronda**, salió limpia y parecía
suficiente: era la ronda afortunada, la única de quince que no se cuela.

Lo que dejaba en el registro es lo del doble toque secuencial y peor, porque no
se detectaba: una entrada y una salida en el mismo instante, un día de cero
segundos trabajados y la persona en estado «fuera». Deshacerlo exige el
procedimiento del art. 4.b, de uno en uno.

## Sin hilos, por lo mismo que `apps/common/tests/test_dos_a_la_vez.py`

Ese fichero lo explica: `transaction=True` vacía las tablas con TRUNCATE en el
desmontaje y el rastro de auditoría lo rechaza --- es uno de los tres disparadores
que lo hacen inmutable. Así que la carrera no se reproduce con hilos aquí.

Lo que sí se comprueba, y es determinista: que fichar **bloquea la fila de la
persona** antes de mirar su último fichaje. Es la única forma de que la
comprobación signifique algo con dos transacciones de verdad, y si alguien quita
el bloqueo esta prueba se pone roja.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con prisa", tax_id="B14141414", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="prisa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Prisa",
            last_name="Equis",
        )


def consultas_de_fichar(company, quien):
    with tenant_context(company.id), CaptureQueriesContext(connection) as capturadas:
        register_punch(employee=quien, company=company)
    return [c["sql"] for c in capturadas]


@pytest.mark.django_db(transaction=False)
def test_fichar_bloquea_a_la_persona_antes_de_mirar_su_ultimo_fichaje(company, quien):
    consultas = consultas_de_fichar(company, quien)

    bloqueos = [i for i, sql in enumerate(consultas) if "FOR UPDATE" in sql.upper()]
    assert bloqueos, "fichar no bloquea nada: dos peticiones a la vez leerán el mismo estado"

    # Y sobre la persona, que es lo que serializa sus propias pulsaciones. No hay
    # fila de estado que bloquear: un fichaje no modifica al anterior.
    assert any("users_user" in consultas[i].lower() for i in bloqueos), [
        consultas[i] for i in bloqueos
    ]

    # Antes de la consulta que lee el último fichaje, o el bloqueo llega tarde.
    lecturas = [
        i
        for i, sql in enumerate(consultas)
        if "punches_punch" in sql.lower() and sql.strip().upper().startswith("SELECT")
    ]
    assert lecturas, "el control falla: fichar ya no lee los fichajes anteriores"
    assert min(bloqueos) < min(lecturas), (
        "el bloqueo va después de leer el último fichaje, así que no protege"
    )


@pytest.mark.django_db(transaction=False)
def test_y_el_fichaje_sigue_saliendo_bien(company, quien):
    """El control. Un bloqueo que rompiera el fichaje pasaría la prueba de arriba."""
    with tenant_context(company.id):
        primero = register_punch(employee=quien, company=company)

    assert primero.punch_type == PunchType.IN
    with tenant_context(company.id):
        assert Punch.objects.filter(employee=quien).count() == 1
        assert primero.verify_hash()
