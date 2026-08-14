"""El turno de noche: entrar un día y salir al siguiente.

El fallo, y es el más grave que ha salido en toda la auditoría: quien entraba a
las 22:00 y salía a las 06:00 recibía **dos entradas y ninguna salida**. La
deducción del tipo miraba solo los fichajes del día local, y al salir el día
nuevo no tenía ninguno --- así que decía «entrada». La jornada no se cerraba
nunca, el día quedaba en cero horas y la persona figuraba trabajando
indefinidamente.

En una empresa de vigilancia, de limpieza o de residencias eso no es un caso
raro: es el registro entero mal, todos los días, para toda la plantilla de
noche. Y es justo la gente sobre la que el producto más avisa.

Lo que decide ahora es el último evento de ese intervalo, esté en el día que
esté, mientras siga abierto y no haya pasado tanto tiempo que ya no pueda ser la
misma jornada.
"""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import PunchInterval, PunchType
from apps.punches.services import build_day_status, register_punch
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def quien(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="noc@example.com", password=PASSWORD, tenant=empresa, first_name="Noc"
        )


@pytest.mark.django_db
def test_entrar_a_las_diez_y_salir_a_las_seis_cierra_la_jornada(empresa, quien):
    """El caso. En hora de Madrid: 22:00 del 8 y 06:00 del 9."""
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 20:00:00"):
            entrada = register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 04:00:00"):
            salida = register_punch(employee=quien, company=empresa)

    assert entrada.punch_type == PunchType.IN
    assert salida.punch_type == PunchType.OUT, "la salida se registraba como una segunda entrada"


@pytest.mark.django_db
def test_y_el_dia_deja_de_estar_abierto(empresa, quien):
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 20:00:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 04:00:00"):
            register_punch(employee=quien, company=empresa)
            assert build_day_status(quien, empresa).state == "OFF"


@pytest.mark.django_db
def test_el_dia_corriente_sigue_igual(empresa, quien):
    """El contraste que impide que el arreglo se lleve por delante lo que ya
    funcionaba: entrar y salir el mismo día no cambia en nada."""
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 06:00:00"):
            entrada = register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-08 14:00:00"):
            salida = register_punch(employee=quien, company=empresa)

    assert (entrada.punch_type, salida.punch_type) == (PunchType.IN, PunchType.OUT)


@pytest.mark.django_db
def test_pasado_el_tope_la_de_la_manana_siguiente_es_una_entrada(empresa, quien):
    """Quien se olvidó de fichar la salida ayer no cierra ayer al llegar hoy.

    Sin tope, la entrada del martes se leería como el cierre del lunes, que es
    otro error distinto y peor de deshacer. Para eso está el mecanismo de
    correcciones, donde queda constancia de qué se cambió y con acuerdo de las
    dos partes (art. 4.b).
    """
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 06:00:00"):
            register_punch(employee=quien, company=empresa)  # entra el lunes
        # No ficha la salida. Al día siguiente, veinticuatro horas después:
        with freeze_time("2026-09-09 06:00:00"):
            siguiente = register_punch(employee=quien, company=empresa)

    assert siguiente.punch_type == PunchType.IN


@pytest.mark.django_db
def test_una_jornada_larga_de_catorce_horas_sigue_cerrando(empresa, quien):
    """Entre el turno de noche y el olvido hay jornadas largas y legales."""
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 18:00:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 08:00:00"):
            salida = register_punch(employee=quien, company=empresa)

    assert salida.punch_type == PunchType.OUT


@pytest.mark.django_db
def test_la_pausa_de_madrugada_tampoco_se_confunde(empresa, quien):
    """Los intervalos siguen contándose por separado: empezar una pausa a las
    tres de la mañana no cierra la jornada que empezó a las diez."""
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 20:00:00"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-09 01:00:00"):
            pausa = register_punch(employee=quien, company=empresa, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-09 01:30:00"):
            fin = register_punch(employee=quien, company=empresa, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-09 04:00:00"):
            salida = register_punch(employee=quien, company=empresa)

    assert pausa.punch_type == PunchType.IN
    assert fin.punch_type == PunchType.OUT
    assert salida.punch_type == PunchType.OUT, "la pausa se llevó por delante la jornada"


@pytest.mark.django_db
def test_el_doble_toque_tambien_protege_a_caballo_de_la_medianoche(empresa, quien):
    """La guarda del doble toque miraba «los fichajes de hoy».

    A las 23:59:58 y otra vez a las 00:00:01 el día nuevo está vacío, así que no
    veía el primero y dejaba pasar el segundo: dos fichajes con tres segundos
    entre ellos, que es exactamente lo que esta guarda existe para evitar. Un
    turno que empieza a las 00:00 no es raro donde se trabaja de noche.
    """
    with tenant_context(empresa.id):
        # 23:59:58 y 00:00:01 en hora de Madrid.
        with freeze_time("2026-09-08 21:59:58"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-08 22:00:01"), pytest.raises(BusinessRuleError) as caido:
            register_punch(employee=quien, company=empresa)

    assert caido.value.code == "punch_too_soon"


@pytest.mark.django_db
def test_y_pasada_la_ventana_sigue_dejando_fichar(empresa, quien):
    """El contraste: la protección es para el dedo, no para la persona."""
    with tenant_context(empresa.id):
        with freeze_time("2026-09-08 21:59:58"):
            register_punch(employee=quien, company=empresa)
        with freeze_time("2026-09-08 22:00:30"):
            salida = register_punch(employee=quien, company=empresa)

    assert salida.punch_type == PunchType.OUT
