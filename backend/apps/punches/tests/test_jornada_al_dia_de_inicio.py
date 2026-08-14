"""A qué día van las horas de un turno que cruza la medianoche.

La otra mitad del turno de noche. `test_turno_de_noche` comprobaba que la salida
de las 06:00 se **registra** como salida y no como una segunda entrada; esto
comprueba dónde **aparecen** esas ocho horas después.

Aparecían en ninguna parte. La deducción del tipo se arregló y la atribución no:
todo lo que agrupa fichajes ---el estado del día, el informe que se entrega a
una inspección, la cola de horas extra, la conciliación con el cuadrante--- lo
hacía por el día local de cada fichaje. Así, la entrada de las 22:00 caía en el
martes y la salida de las 06:00 en el miércoles, y como ninguno de los dos días
tenía un par completo, las horas no se sumaban en ninguno.

La regla, decidida y escrita en `apps.punches.workday`: **la jornada entera
cuenta en el día en que empieza**. Ocho horas del martes; el miércoles, a
efectos de jornada, no se trabajó.

El tope de horas que una jornada puede seguir abierta es de cada empresa
(`WorkingTimeRules.max_open_hours`, dieciséis por defecto) porque la frontera
entre «cerró tarde» y «se olvidó de fichar» no la fija ningún artículo, y quien
tiene guardias de veinticuatro horas ---bomberos, residencias, vigilancia---
necesita otra.
"""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time

from apps.common.models import tenant_context
from apps.punches.models import PunchInterval
from apps.punches.services import build_day_status, register_punch
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: En hora de Madrid (UTC+2 en septiembre): 22:00 del 8 y 06:00 del 9.
ENTRA = "2026-09-08 20:00:00"
SALE = "2026-09-09 04:00:00"
MARTES = date(2026, 9, 8)
MIERCOLES = date(2026, 9, 9)

OCHO_HORAS = 8 * 3600


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Vigilancia SL", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="noc@example.com", password=PASSWORD, tenant=empresa, first_name="Noc"
        )


def _turno_de_noche(empresa, quien):
    with freeze_time(ENTRA):
        register_punch(employee=quien, company=empresa)
    with freeze_time(SALE):
        register_punch(employee=quien, company=empresa)


@pytest.mark.django_db
def test_las_ocho_horas_van_al_dia_en_que_empezo(empresa, quien):
    """El caso, y la razón entera de todo esto."""
    with tenant_context(empresa.id):
        _turno_de_noche(empresa, quien)
        estado = build_day_status(quien, empresa, MARTES)

    assert estado.worked_seconds == OCHO_HORAS, "las horas de la noche no están en ningún día"
    assert estado.state == "OFF"


@pytest.mark.django_db
def test_y_no_aparecen_tambien_al_dia_siguiente(empresa, quien):
    """El contraste imprescindible: contarlas dos veces sería peor que perderlas.

    Un informe que suma dieciséis horas donde se trabajaron ocho no es un hueco,
    es una cifra falsa, y va firmado.
    """
    with tenant_context(empresa.id):
        _turno_de_noche(empresa, quien)
        estado = build_day_status(quien, empresa, MIERCOLES)

    assert estado.worked_seconds == 0
    assert estado.state == "NOT_STARTED"


@pytest.mark.django_db
def test_una_jornada_diurna_no_cambia_en_nada(empresa, quien):
    """El otro contraste: el arreglo no puede mover de día a quien nunca cruzó
    la medianoche, que son casi todos."""
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 06:00:00"):  # 08:00 en Madrid
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-08 14:00:00"):  # 16:00
            register_punch(employee=quien, company=empresa)

        assert build_day_status(quien, empresa, MARTES).worked_seconds == OCHO_HORAS
        assert build_day_status(quien, empresa, MIERCOLES).worked_seconds == 0


@pytest.mark.django_db
def test_a_las_tres_de_la_madrugada_la_pantalla_dice_que_esta_trabajando(empresa, quien):
    """Sin día, «la jornada de ahora» no es «hoy».

    Quien entró ayer a las 22:00 tiene abierta la jornada de **ayer**. Mirando
    hoy, su día no tiene ningún fichaje y su propia pantalla le decía «sin
    empezar» a las tres de la mañana, en mitad del turno.
    """
    with tenant_context(empresa.id):
        with freeze_time(ENTRA):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 01:00:00"):  # 03:00 en Madrid
            estado = build_day_status(quien, empresa)

    assert estado.state == "WORKING"
    assert estado.worked_seconds == 5 * 3600, "las horas de la noche no se le contaban en vivo"


@pytest.mark.django_db
def test_la_pausa_de_madrugada_descuenta_de_la_jornada_del_dia_de_entrada(empresa, quien):
    """Una pausa a las 03:00 pertenece al turno que la contiene.

    Si se atribuyera a su propio día natural saldría de la jornada a la que
    descuenta, y el turno de noche cobraría media hora que no trabajó.
    """
    with tenant_context(empresa.id):
        with freeze_time(ENTRA):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 01:00:00"):
            register_punch(employee=quien, company=empresa, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-09 01:30:00"):
            register_punch(employee=quien, company=empresa, interval=PunchInterval.BREAK)
        with freeze_time(SALE):
            register_punch(employee=quien, company=empresa)

        estado = build_day_status(quien, empresa, MARTES)

    # Ocho de reloj menos la media hora de pausa, que en esta empresa no cuenta
    # como trabajo (art. 34.4: solo cuenta si lo dice el convenio).
    assert estado.worked_seconds == OCHO_HORAS - 1800
    assert estado.break_seconds == 1800


@pytest.mark.django_db
def test_el_informe_las_pone_el_dia_de_la_entrada(empresa, quien):
    """El sitio donde más importa: es lo que se entrega a una inspección."""
    from apps.reports.services import build_report

    with tenant_context(empresa.id):
        _turno_de_noche(empresa, quien)
        informe = build_report(
            employee=quien, company=empresa, date_from=MARTES, date_to=MIERCOLES
        )

    por_dia = {fila.day: fila.seconds for fila in informe.rows}
    assert por_dia[MARTES] == OCHO_HORAS
    assert por_dia[MIERCOLES] == 0


@pytest.mark.django_db
def test_un_olvido_no_se_traga_el_dia_siguiente(empresa, quien):
    """El tope, por el lado que lo justifica.

    Sin él, la entrada del miércoles se leería como parte de la jornada del
    martes y a partir de ahí todo corrido: un olvido de un día convertido en un
    registro roto de una semana.
    """
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 06:00:00"):  # entra el martes y no sale
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 06:00:00"):  # entra el miércoles
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 14:00:00"):  # y sale el miércoles
            register_punch(employee=quien, company=empresa)

        del_miercoles = build_day_status(quien, empresa, MIERCOLES)

    assert del_miercoles.worked_seconds == OCHO_HORAS, "el olvido del martes se comió el miércoles"


@pytest.mark.django_db
def test_una_guardia_de_veinticuatro_horas_con_el_tope_subido(empresa, quien):
    """Por lo que el tope es de cada empresa y no nuestro.

    Con dieciséis, una guardia de veinticuatro se parte por la mitad: a las
    dieciséis horas su entrada deja de contar como abierta y la salida no cierra
    nada. Bomberos, residencias y vigilancia trabajan así, y no son un caso raro
    en un producto de fichaje.
    """
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.max_open_hours = 30
        reglas.save(update_fields=["max_open_hours"])
        # `for_company` memoriza en la empresa; sin esto se seguiría leyendo 16.
        empresa._working_time_rules = reglas

        with freeze_time("2026-09-08 06:00:00"):  # 08:00 del martes
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 06:00:00"):  # 08:00 del miércoles
            register_punch(employee=quien, company=empresa)

        estado = build_day_status(quien, empresa, MARTES)

    assert estado.worked_seconds == 24 * 3600, "la guardia se partió por la mitad"
    assert estado.state == "OFF"


@pytest.mark.django_db
def test_y_con_el_tope_por_defecto_esa_misma_guardia_no_cierra(empresa, quien):
    """El contraste del de arriba, que es el que demuestra que el ajuste hace algo.

    Sin esto, la prueba anterior pasaría igual aunque el tope se estuviera
    ignorando y todo siguiera con los dieciséis de siempre.
    """
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 06:00:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 06:00:00"):
            register_punch(employee=quien, company=empresa)

        estado = build_day_status(quien, empresa, MARTES)

    assert estado.worked_seconds != 24 * 3600
