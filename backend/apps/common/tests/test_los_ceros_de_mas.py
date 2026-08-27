"""Un decimal se juzga por su valor, no por cómo se escribió.

`DecimalField` cuenta los decimales del `Decimal` tal como llega, no los
significativos. Con `decimal_places=1` eso rechazaba `20.00` --- que es
exactamente `20.0` --- con el mensaje «asegúrese de que no haya más de 1
decimales»: cierto, tiene dos, y ninguno cuenta.

Lo que lo delata es la asimetría. Medido antes de arreglarlo, sobre las horas
pactadas:

    20      -> 201        0020.0  -> 201
    20.0    -> 201        20.00   -> 400
    20.5    -> 201        20.50   -> 400

Los ceros de la izquierda daban igual y los de la derecha no. Y dos decimales es
como formatea cualquiera que venga del mundo de las nóminas, así que una
integración correcta se comía un 400 por escribir el mismo número de otra manera.

Pasaba en los tres campos que se pactan en horas --- las de la persona y las dos
del convenio --- y en el porcentaje del ERTE.

**Lo que no puede aflojarse**: `20.55` no es `20.5`. Media hora es el grano con
el que se pactan las jornadas, y esa precisión se sigue rechazando.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

#: Escrituras distintas del mismo número, todas válidas.
IGUALES = ["20", "20.0", "20.00", "20.000", "0020.00"]

#: Y una que no lo es: no cabe en el grano de media hora.
NO_CABE = "20.55"


@pytest.fixture
def api(db):
    t = Tenant.objects.create(name="Ceros SL", tax_id="B67676767", time_zone="Europe/Madrid")
    with tenant_context(t.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=t,
            first_name="Je",
            last_name="Fa",
            role=Role.ADMIN,
        )
        cliente = APIClient()
        cliente.force_authenticate(user=jefa)
        yield cliente, t


@pytest.mark.parametrize("escrito", IGUALES)
@pytest.mark.django_db
def test_las_horas_de_la_persona_dan_igual_como_se_escriban(api, escrito):
    cliente, t = api
    with tenant_context(t.id):
        r = cliente.post(
            "/api/employees/",
            {
                "email": f"h{escrito.replace('.', '_')}@example.com",
                "first_name": "H",
                "last_name": "Or",
                "regime": "PART_TIME",
                "contracted_hours": escrito,
            },
            format="json",
        )

    assert r.status_code == 201, f"«{escrito}» es 20 y se rechazó: {r.json()}"
    assert Decimal(r.json()["contracted_hours"]) == Decimal(20), (
        f"«{escrito}» se guardó como {r.json()['contracted_hours']}"
    )


@pytest.mark.django_db
def test_pero_la_precision_que_no_cabe_se_sigue_rechazando(api):
    """El contraste, y es la mitad que importa: sin él, esto pasaría igual si el
    campo hubiera dejado de mirar los decimales."""
    cliente, t = api
    with tenant_context(t.id):
        r = cliente.post(
            "/api/employees/",
            {
                "email": "fino@example.com",
                "first_name": "F",
                "last_name": "Ino",
                "regime": "PART_TIME",
                "contracted_hours": NO_CABE,
            },
            format="json",
        )

    assert r.status_code == 400, f"«{NO_CABE}» no es 20,5 y coló"
    assert "contracted_hours" in str(r.json())


@pytest.mark.parametrize("campo", ["weekly_hours", "break_after_hours"])
@pytest.mark.django_db
def test_las_dos_del_convenio_tambien(api, campo):
    cliente, t = api
    with tenant_context(t.id):
        bien = cliente.patch("/api/working-time-rules/", {campo: "6.00"}, format="json")
        mal = cliente.patch("/api/working-time-rules/", {campo: "6.55"}, format="json")

    assert bien.status_code == 200, f"{campo} rechazó «6.00»: {bien.json()}"
    assert mal.status_code == 400, f"{campo} aceptó «6.55»"


@pytest.mark.django_db
def test_y_lo_que_no_es_un_numero_sigue_dando_su_propio_error(api):
    """Normalizar no puede tragarse la basura: el mensaje del campo sobre lo que
    no es un número es mejor que cualquiera que se escriba aquí."""
    cliente, t = api
    with tenant_context(t.id):
        r = cliente.patch("/api/working-time-rules/", {"weekly_hours": "cuarenta"}, format="json")

    assert r.status_code == 400
    assert "weekly_hours" in str(r.json())
