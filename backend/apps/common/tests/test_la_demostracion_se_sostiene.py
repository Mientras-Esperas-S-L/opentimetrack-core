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
from apps.punches.models import HoursNature, Punch, PunchInterval, PunchType
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


@pytest.mark.django_db
def test_las_horas_marcadas_se_ven_de_verdad(sembrada):
    """Marcar la naturaleza de las horas donde nadie la lee es no marcarla.

    Todo lo descriptivo de un tramo viaja en el evento que lo **abre**: `_span`
    copia de ahí el intervalo, el modo de trabajo y la naturaleza de las horas.
    La semilla las ponía en el evento de **salida** hasta el 28/08/2026, así que
    las complementarias de la demostración salían como ordinarias y el tope del
    art. 12.5.c no tenía nada que contar.

    Medido antes de arreglarlo: marcada en la salida, el tramo dice `ORDINARY`;
    marcada en la entrada, `COMPLEMENTARY`. Es el mismo error que las pausas al
    revés, en otro campo.
    """
    with tenant_context(sembrada.id):
        marcadas = set(
            Punch.objects.filter(punch_type=PunchType.IN)
            .exclude(hours_nature=HoursNature.ORDINARY)
            .values_list("hours_nature", flat=True)
        )
        assert marcadas, "ninguna hora especial en las entradas: no se verían"

        # Y en las salidas, ninguna: ahí no las lee nadie.
        en_salidas = (
            Punch.objects.filter(punch_type=PunchType.OUT)
            .exclude(hours_nature=HoursNature.ORDINARY)
            .count()
        )
        assert en_salidas == 0, f"{en_salidas} marcadas en la salida, donde no se leen"


@pytest.mark.django_db
def test_la_demostracion_ensena_los_dos_saldos_de_descanso(sembrada):
    """Sin un caso de cada, esas pantallas no aparecen en ninguna demostración.

    El saldo de descanso solo se enseña cuando hay deuda, y hay dos fuentes: las
    horas extra a compensar con descanso (art. 35.1) y los festivos trabajados
    (art. 37.2). La segunda además exige que la empresa haya declarado que los
    compensa con descanso, porque el artículo no lo dice ---lo dice el convenio---.

    Es la misma razón por la que la semilla marca horas complementarias: una
    función que no se ve en la demostración no se puede enseñar, y nadie se entera
    de que existe.
    """
    from apps.punches.rest_debt import rest_debt
    from apps.tenants.rules import WorkingTimeRules

    with tenant_context(sembrada.id):
        reglas = WorkingTimeRules.for_company(sembrada)
        assert reglas.holiday_worked_compensation == WorkingTimeRules.HOLIDAY_REST

        origenes = set()
        for quien in User.objects.filter(tenant=sembrada)[:20]:
            saldo = rest_debt(employee=quien, company=sembrada)
            if saldo:
                origenes |= {f["source"] for f in saldo["sources"]}

        assert "overtime" in origenes, "ninguna hora extra a compensar con descanso"
        assert "holiday" in origenes, "ningún festivo trabajado"


@pytest.mark.django_db
def test_la_demostracion_ensena_los_dias_por_antiguedad(sembrada):
    """Sin escala declarada, esa línea del saldo no aparece nunca.

    Los días de vacaciones por antigüedad no salen del Estatuto ---el art. 38.1
    no habla de antigüedad--- así que solo existen si el convenio los da. Una
    demostración sin ellos no puede enseñar la función, y es de las que un
    cliente reconoce al momento: casi cualquier convenio los tiene.
    """
    from apps.absences.services import vacation_balance
    from apps.tenants.rules import WorkingTimeRules

    with tenant_context(sembrada.id):
        assert WorkingTimeRules.for_company(sembrada).seniority_leave, "sin escala declarada"

        con_extra = [
            quien
            for quien in User.objects.filter(tenant=sembrada)[:20]
            if vacation_balance(quien, sembrada).seniority_days
        ]
        assert con_extra, "nadie de la demostración llega a ningún tramo de antigüedad"


@pytest.mark.django_db
def test_solo_queda_una_entrada_sin_cerrar_y_es_la_de_hoy(sembrada):
    """Una apertura huérfana se traga la jornada del día siguiente.

    `max_open_hours` vale dieciséis horas ---está para el turno de noche, que
    entra a las diez y sale a las seis--- así que una entrada de la tarde que
    nadie cerró **absorbe los fichajes de la mañana siguiente**: se atribuyen a
    la jornada anterior y el día siguiente cuenta cero horas.

    La demostración tenía una: la corrección que la empresa aplica sin acuerdo
    añadía «la entrada que faltaba» de un día que ya tenía la suya, y esa segunda
    entrada no cerraba nunca. El día siguiente salía a cero.

    **Y la prueba que existía para esto no lo veía.** Miraba tramos con final
    vacío, y aquel tramo sí tenía final: el de la salida del día siguiente. Por
    eso este guard cuenta las aperturas en vez de mirar los tramos.

    La de hoy se queda: la semilla deja a alguien fichado a propósito para que la
    pantalla tenga una jornada en curso.
    """
    with tenant_context(sembrada.id):
        # **Por balance y no con una pila con `setdefault`.** Esa es la regla del
        # producto ---dos entradas seguidas, la primera gana--- y copiarla aquí
        # haría que una entrada **repetida** no contara como suelta, que es
        # justamente el caso que se coló. Aquí se cuenta cuántas entradas no
        # llegan a tener salida, se parezca o no a como el producto las lee.
        sueltas = []
        for quien in User.objects.filter(tenant=sembrada):
            balance: dict[str, list] = {}
            for punch in Punch.objects.filter(employee=quien).order_by("timestamp"):
                cola = balance.setdefault(punch.interval, [])
                if punch.punch_type == PunchType.IN:
                    cola.append(punch)
                elif cola:
                    cola.pop()
            sueltas += [(quien.email, p.timestamp) for cola in balance.values() for p in cola]

        de_hoy = [x for x in sueltas if x[1].date() >= timezone.localdate() - timedelta(days=1)]
        viejas = [x for x in sueltas if x not in de_hoy]

        assert viejas == [], "entradas sin cerrar en días pasados:\n  " + "\n  ".join(
            f"{email} {cuando:%Y-%m-%d %H:%M}" for email, cuando in viejas[:5]
        )
        assert de_hoy, "la de hoy tiene que seguir ahí: es la jornada en curso de la pantalla"
