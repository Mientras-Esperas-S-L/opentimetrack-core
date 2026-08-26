"""El informe del art. 34.9 no puede releerse distinto según la empresa de hoy.

La marca se guarda en UTC y hay que leerla en algún huso para decir «las nueve».
Ese huso salía de la persona ---de su centro de trabajo, o de la empresa si no
tiene--- y eso es un dato de **hoy** aplicado a un hecho de **entonces**.

Medido antes de arreglarlo: alguien que fichó el 30 de mayo en un centro de
Canarias, y que ya no trabaja allí. Se retira el centro ---permitido, porque no
queda nadie dentro--- y **la misma fila del informe** pasa de:

    2026-05-30;09:00;17:00;08:00

a:

    2026-05-30;10:00;18:00;08:00

Una hora de diferencia en un documento que se entrega a la Inspección, provocada
por una reorganización que nadie relacionaría con el registro. El art. 34.9 lo
quiere **fiable**, y un asiento que se relee distinto según cómo esté organizada
la empresa hoy no lo es. Y el `hash_integrity` seguía cuadrando, porque la fila no
había cambiado: lo que cambiaba era cómo se leía.

El huso se congela ahora en el fichaje, por lo mismo que el hash congela el
contenido. Los anteriores al campo caen al huso de la persona, que es la mejor
respuesta disponible para ellos.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Dos husos", tax_id="B91100001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )
        canarias = Workplace.objects.create(
            tenant=empresa, name="Delegación", time_zone="Atlantic/Canary"
        )
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Fichó",
            workplace=canarias,
        )
        entrada = datetime(2026, 5, 20, 8, 0, tzinfo=UTC)
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type="IN",
            timestamp=entrada,
            source="WEB",
            time_zone="Atlantic/Canary",
        )
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type="OUT",
            timestamp=entrada + timedelta(hours=8),
            source="WEB",
            time_zone="Atlantic/Canary",
        )
        yield {"empresa": empresa, "jefa": jefa, "quien": quien, "centro": canarias}


def fila_del_dia(mundo):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=mundo["jefa"])
    respuesta = cliente.get(
        "/api/reports/working-time/"
        f"?date_from=2026-05-15&date_to=2026-05-25&employee={mundo['quien'].pk}&format=csv"
    )
    assert respuesta.status_code == 200, respuesta.content
    filas = [
        linea
        for linea in respuesta.content.decode("utf-8-sig", "replace").splitlines()
        if "2026-05-20" in linea
    ]
    assert filas, "el día no aparecía en el informe"
    return filas[0]


@pytest.mark.django_db
def test_retirar_el_centro_no_mueve_las_horas(mundo):
    antes = fila_del_dia(mundo)
    assert "09:00" in antes, f"el fichaje canario no salía a su hora: {antes}"

    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=mundo["jefa"])
    # Ya no queda nadie dentro, así que el centro se puede retirar.
    with tenant_context(mundo["empresa"].id):
        mundo["quien"].is_active = False
        mundo["quien"].save(update_fields=["is_active"])
    borrado = cliente.delete(f"/api/workplaces/{mundo['centro'].pk}/")
    assert borrado.status_code == 204, borrado.content

    assert fila_del_dia(mundo) == antes, "el registro cambió al reorganizar la empresa"


@pytest.mark.django_db
def test_cambiarle_el_huso_al_centro_tampoco(mundo):
    """El otro camino al mismo sitio, y el más fácil de dar sin querer."""
    antes = fila_del_dia(mundo)

    with tenant_context(mundo["empresa"].id):
        mundo["centro"].time_zone = "Europe/Madrid"
        mundo["centro"].save(update_fields=["time_zone"])

    assert fila_del_dia(mundo) == antes, "cambiar el huso del centro reescribió el pasado"


@pytest.mark.django_db
def test_moverla_de_centro_tampoco(mundo):
    antes = fila_del_dia(mundo)

    with tenant_context(mundo["empresa"].id):
        peninsula = Workplace.objects.create(
            tenant=mundo["empresa"], name="Central", time_zone="Europe/Madrid"
        )
        mundo["quien"].workplace = peninsula
        mundo["quien"].save(update_fields=["workplace"])

    assert fila_del_dia(mundo) == antes, "mudarse de centro reescribió su registro anterior"


@pytest.mark.django_db
def test_un_fichaje_de_antes_del_campo_usa_el_huso_de_la_persona(mundo):
    """Lo que había antes sigue leyéndose como se leía: no hay dato mejor."""
    with tenant_context(mundo["empresa"].id):
        Punch.objects.filter(employee=mundo["quien"]).update(time_zone="")

    # El de su centro, que es Canarias, así que a la misma hora que antes.
    assert "09:00" in fila_del_dia(mundo)


@pytest.mark.django_db
def test_un_huso_que_ya_no_existe_no_tumba_el_informe(mundo):
    """La base de husos del sistema cambia con los años."""
    with tenant_context(mundo["empresa"].id):
        Punch.objects.filter(employee=mundo["quien"]).update(time_zone="Marte/Olympus")

    fila = fila_del_dia(mundo)
    assert "2026-05-20" in fila
