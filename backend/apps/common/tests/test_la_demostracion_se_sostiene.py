"""Que lo que se enseña en una demostración diga la verdad.

La semilla no tenía ninguna prueba, y es **lo único del producto que alguien de
fuera mira antes de comprar**. El 28/08/2026 llevaba tres vueltas generando las
pausas al revés ---abriéndolas con una salida en vez de con una entrada--- y el
resultado era que **siete de las catorce personas aparecían con cero horas
trabajadas** cada día que hacían una pausa. Cuarenta y dos días mirados, cuarenta
y dos a cero.

No lo cazó nada porque las suites traen sus propios datos: nadie comprobaba que
los de la demostración se sostuvieran. Y el fallo es de los que no se ven de
pasada ---la lista de fichajes está llena, las horas de cada tramo son
correctas--- hasta que alguien mira el total del día.

Estas pruebas son baratas y no repiten lo que ya se comprueba en otro sitio: no
miran si el producto calcula bien ---de eso hay pruebas de sobra--- sino si **los
datos que se enseñan tienen sentido**.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval
from apps.punches.services import build_day_status
from apps.tenants.models import Tenant
from apps.users.models import User


@pytest.fixture(scope="module")
def sembrada(django_db_setup, django_db_blocker):
    """La demostración, sembrada una vez para todas las pruebas del fichero.

    Tarda unos segundos y no la modifica ninguna, así que repetirla por prueba
    sería pagar tres veces lo mismo.

    **Y se deshace al terminar, que es lo que faltaba.** La primera versión
    sembraba y ya está: en verde ejecutando este fichero solo, y en rojo en el
    momento en que corría la suite entera. Lo que `django_db_blocker.unblock()`
    abre es la base de datos de verdad, fuera de la transacción que pytest-django
    da a cada prueba, así que catorce personas y mil fichajes se quedaban puestos
    para todo lo que viniera detrás. Lo cazaron los barridos de aislamiento, que
    cuentan filas de todas las empresas y esperaban dos donde había siete.
    """
    # `seed_demo` se niega a correr sin `DEBUG`, y hace bien: escribe contraseñas
    # conocidas y eso en producción sería un agujero. Aquí se activa solo para
    # sembrar, que es exactamente el caso que la salvaguarda quiere permitir.
    with django_db_blocker.unblock(), override_settings(DEBUG=True), transaction.atomic():
        marca = transaction.savepoint()
        call_command("seed_demo", "--reset", verbosity=0)
        yield Tenant.objects.filter(name="Jardines Demo S.L.").first()
        transaction.savepoint_rollback(marca)


@pytest.mark.django_db
def test_hay_gente_con_pausas(sembrada):
    """El contraste de todas las de abajo.

    Si la semilla dejara de generar pausas, las pruebas siguientes pasarían sin
    comprobar nada: no habría días con pausa que pudieran salir mal.
    """
    with tenant_context(sembrada.id):
        assert Punch.objects.filter(interval=PunchInterval.BREAK).exists()
        quienes = set(
            Punch.objects.filter(interval=PunchInterval.BREAK).values_list("employee_id", flat=True)
        )
        assert len(quienes) >= 3, f"solo {len(quienes)} personas con pausas"


@pytest.mark.django_db
def test_un_dia_con_pausa_no_cuenta_cero(sembrada):
    """El fallo que esta prueba existe para que no vuelva.

    Una pausa se abre con una **entrada** y ocurre dentro de la jornada. Puesta
    al revés, la salida se ignora ---no hay pausa abierta que cerrar---, la
    entrada abre una que no se cierra nunca, y sus horas se restan de las
    trabajadas hasta dejar el día en cero.

    Lo peor es cómo se ve: los fichajes están todos, sus horas son correctas, y
    solo el total del día delata que algo no cuadra.
    """
    hoy = timezone.localdate()
    with tenant_context(sembrada.id):
        mirados = 0
        for quien in User.objects.filter(
            id__in=Punch.objects.filter(interval=PunchInterval.BREAK).values("employee_id")
        ):
            for atras in range(2, 12):
                dia = hoy - timedelta(days=atras)
                if not Punch.objects.filter(
                    employee=quien, timestamp__date=dia, interval=PunchInterval.BREAK
                ).exists():
                    continue
                estado = build_day_status(quien, sembrada, dia)
                assert estado.worked_seconds > 0, (
                    f"{quien.email} el {dia}: un día con pausa cuenta cero horas"
                )
                mirados += 1

        assert mirados >= 5, f"solo se han podido mirar {mirados} días con pausa"


@pytest.mark.django_db
def test_ningun_tramo_se_queda_abierto_en_dias_pasados(sembrada):
    """Un tramo sin cerrar en un día que ya pasó es un dato roto.

    Hoy puede haber uno abierto a propósito ---la semilla deja a alguien fichado
    para que la pantalla tenga una jornada en curso--- pero ayer, no.
    """
    hoy = timezone.localdate()
    with tenant_context(sembrada.id):
        abiertos = []
        for quien in User.objects.filter(tenant=sembrada)[:20]:
            for atras in range(2, 10):
                dia = hoy - timedelta(days=atras)
                estado = build_day_status(quien, sembrada, dia)
                for tramo in estado.segments:
                    if tramo.end is None:
                        abiertos.append(f"{quien.email} {dia} {tramo.interval or 'WORK'}")
        assert abiertos == [], "tramos sin cerrar en días pasados:\n  " + "\n  ".join(abiertos[:10])
