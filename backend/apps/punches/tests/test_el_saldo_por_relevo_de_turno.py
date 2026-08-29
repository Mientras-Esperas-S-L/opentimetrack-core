"""El descanso que se debe por un relevo de turno (art. 19.a RD 1561/1995).

«Cuando el trabajador cambie de turno de trabajo y no pueda disfrutar del
descanso mínimo entre jornadas establecido en el artículo 34.3 del Estatuto de
los Trabajadores, se podrá reducir el mismo, en el día en que así ocurra, hasta
un mínimo de siete horas, **compensándose la diferencia hasta las doce horas**
establecidas con carácter general en los días inmediatamente siguientes.»

**No es un incumplimiento, y por eso hay que llevar la cuenta.** El artículo
permite el descanso corto para que la rotación sea posible; lo que exige a cambio
es devolver la diferencia. La mitad que faltaba era esa: el producto sabía decir
«ocho horas, y es lícito» y no «y quedan cuatro por devolver».

**El plazo no es de cuatro semanas.** Esas son del apartado b, que es del
descanso **semanal**; el producto las citaba aquí y daba mucho más margen del que
la norma concede. El 19.a dice «en los días inmediatamente siguientes», que es
más estricto que cualquier fecha, no menos.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.punches.rest_debt import rest_debt
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)
#: Un día dentro de la ventana. En agosto Madrid va en UTC+2.
EL_DIA = date(2026, 8, 17)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Continua SL", tax_id="B77777777", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="rota@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            rotating_shifts=True,
        )


def jornada(company, quien, dia, desde_utc, horas):
    entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=desde_utc)
    for momento, kind in ((entra, PunchType.IN), (entra + timedelta(hours=horas), PunchType.OUT)):
        Punch.objects.create(
            tenant=company,
            employee=quien,
            timestamp=momento,
            punch_type=kind,
            interval=PunchInterval.WORK,
        )


def la_fuente(company, quien):
    with tenant_context(company.id):
        saldo = rest_debt(employee=quien, company=company, day=HOY)
    if not saldo:
        return None
    return next((f for f in saldo["sources"] if f["source"] == "changeover"), None)


@pytest.mark.django_db
def test_el_relevo_deja_lo_que_le_falta_a_las_doce(company, quien):
    """Sale de una noche a las 06:00 y entra a una tarde a las 14:00.

    Ocho horas: por debajo de las doce del art. 34.3 y por encima de las siete
    que el RD permite. Lícito, y con **cuatro horas** que devolver.
    """
    with tenant_context(company.id):
        # 22:00 a 06:00 (20:00 UTC + 8 h), y luego 14:00 a 22:00 (12:00 UTC).
        jornada(company, quien, EL_DIA - timedelta(days=1), 20, 8)
        jornada(company, quien, EL_DIA, 12, 8)

    fuente = la_fuente(company, quien)
    assert fuente["owed_hours"] == 4
    assert fuente["citation"] == "Art. 19.a RD 1561/1995"
    assert fuente["changeovers"] == 1


@pytest.mark.django_db
def test_no_lleva_fecha_pero_tampoco_es_sin_plazo(company, quien):
    """**La corrección que motivó la vuelta.**

    El artículo no da una fecha, así que `due_on` es nulo; pero exige «los días
    inmediatamente siguientes», así que no puede leerse igual que el festivo
    trabajado, que de verdad no tiene ningún plazo. `promptly` los separa.
    """
    with tenant_context(company.id):
        jornada(company, quien, EL_DIA - timedelta(days=1), 20, 8)
        jornada(company, quien, EL_DIA, 12, 8)

    fuente = la_fuente(company, quien)
    assert fuente["due_on"] is None
    assert fuente["promptly"] is True
    assert fuente["overdue_hours"] == 0


@pytest.mark.django_db
def test_quien_no_rota_no_tiene_relevos(company, quien):
    """El contraste. Un descanso corto de quien no rota es el art. 34.3 a secas:
    un incumplimiento, no una excepción con deuda. Contarlo aquí le daría al
    incumplimiento el amparo de un artículo que no le corresponde."""
    with tenant_context(company.id):
        quien.rotating_shifts = False
        quien.save(update_fields=["rotating_shifts"])
        jornada(company, quien, EL_DIA - timedelta(days=1), 20, 8)
        jornada(company, quien, EL_DIA, 12, 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_el_mismo_turno_dos_dias_seguidos_no_es_un_relevo(company, quien):
    """Aunque quien lo hace rote.

    Entrar a la misma hora dos días seguidos y descansar poco no es un cambio de
    equipo: es una jornada que se alargó. El supuesto del artículo es el cambio
    de turno, y sin esta distinción cualquier descanso corto quedaría amparado.
    """
    with tenant_context(company.id):
        # Entra a las 08:00 los dos días, y el primero se alarga hasta las 23:00.
        jornada(company, quien, EL_DIA - timedelta(days=1), 6, 15)
        jornada(company, quien, EL_DIA, 6, 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_un_descanso_de_doce_o_mas_no_debe_nada(company, quien):
    with tenant_context(company.id):
        # De 22:00 a 06:00, y al día siguiente a las 20:00: catorce horas.
        jornada(company, quien, EL_DIA - timedelta(days=1), 20, 8)
        jornada(company, quien, EL_DIA, 18, 6)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_varios_relevos_suman(company, quien):
    with tenant_context(company.id):
        jornada(company, quien, EL_DIA - timedelta(days=1), 20, 8)
        jornada(company, quien, EL_DIA, 12, 8)
        # Y otro par igual, una semana después.
        jornada(company, quien, EL_DIA + timedelta(days=6), 20, 8)
        jornada(company, quien, EL_DIA + timedelta(days=7), 12, 8)

    fuente = la_fuente(company, quien)
    assert fuente["owed_hours"] == 8
    assert fuente["changeovers"] == 2


@pytest.mark.django_db
def test_medianoche_no_convierte_un_turno_fijo_en_un_relevo(company, quien):
    """Las 23:50 y las 00:10 distan veinte minutos, no mil cuatrocientos veinte.

    Restando las horas del día a pelo, un turno de noche que empieza unos minutos
    antes o después de medianoche salía como cambio de equipo, y con él aparecía
    una deuda de descanso que nadie debe.

    **Con el hueco de verdad corto**, que es lo que la primera versión de esta
    prueba no tenía: con jornadas de ocho horas, dos entradas casi a la misma
    hora quedan dieciséis horas de descanso aparte y la comprobación se salía por
    el filtro de las doce sin llegar a comparar nada. Hace falta una jornada
    larga ---quince horas--- para que el hueco baje de las doce **y** las dos
    entradas caigan a los dos lados de la medianoche.
    """
    with tenant_context(company.id):
        # Entra a las 23:50 locales y sale quince horas después, a las 14:50.
        entra = datetime.combine(EL_DIA - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        entra = entra.replace(hour=21, minute=50)
        for momento, kind in ((entra, PunchType.IN), (entra + timedelta(hours=15), PunchType.OUT)):
            Punch.objects.create(
                tenant=company,
                employee=quien,
                timestamp=momento,
                punch_type=kind,
                interval=PunchInterval.WORK,
            )
        # Y vuelve a las 00:10 locales: nueve horas y veinte minutos de descanso
        # ---por debajo de las doce--- con la entrada movida veinte minutos.
        otra = datetime.combine(EL_DIA, datetime.min.time(), tzinfo=UTC).replace(hour=22, minute=10)
        for momento, kind in ((otra, PunchType.IN), (otra + timedelta(hours=8), PunchType.OUT)):
            Punch.objects.create(
                tenant=company,
                employee=quien,
                timestamp=momento,
                punch_type=kind,
                interval=PunchInterval.WORK,
            )

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company, quien):
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B88888888", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        suyo = User.objects.create_user(
            email="suyo@vecina.example",
            password=PASSWORD,
            tenant=vecina,
            first_name="Ajeno",
            rotating_shifts=True,
        )
        jornada(vecina, suyo, EL_DIA - timedelta(days=1), 20, 8)
        jornada(vecina, suyo, EL_DIA, 12, 8)

    with tenant_context(company.id):
        jornada(company, quien, EL_DIA - timedelta(days=1), 20, 8)
        # Este entra a las 16:00, así que le faltan dos horas, no cuatro.
        jornada(company, quien, EL_DIA, 14, 8)

    assert la_fuente(company, quien)["owed_hours"] == 2, "solo los suyos"
