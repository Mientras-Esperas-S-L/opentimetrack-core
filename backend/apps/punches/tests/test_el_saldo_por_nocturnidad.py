"""El descanso que se debe por trabajo nocturno (art. 36.2).

«El trabajo nocturno tendrá una retribución específica que se determinará en la
negociación colectiva, salvo que el salario se haya establecido atendiendo a que
el trabajo sea nocturno por su propia naturaleza o se haya acordado la
compensación de este trabajo por descansos».

**Tres salidas y solo una llega al saldo.** Las otras dos se pagan, y lo que se
paga es una nómina: fuera de lo que hace este producto. Sin declarar cuál eligió
el convenio no se lleva nada, porque no habría de dónde sacar la cifra.

Y lo que se cuenta son **las horas dentro de la franja**, no las jornadas que la
tocan. Quien entra a las 21:00 y sale a las 23:00 ha hecho una hora de noche, no
dos. La franja cruza la medianoche, que es lo que hace el cálculo menos obvio de
lo que parece.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.punches.rest_debt import rest_debt
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)
#: Un día cualquiera dentro de la ventana, y en verano: Madrid va en UTC+2, así
#: que las 22:00 locales son las 20:00 en UTC.
EL_DIA = date(2026, 8, 17)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Vigilancia SL", tax_id="B55555555", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.night_worked_compensation = WorkingTimeRules.NIGHT_REST
        reglas.save(update_fields=["night_worked_compensation"])
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="noche@example.com", password=PASSWORD, tenant=company, first_name="Quien"
        )


def trabaja(company, quien, dia, desde_utc, horas):
    """Un tramo que empieza a esa hora **UTC** y dura lo que se diga."""
    entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=desde_utc)
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra,
        punch_type=PunchType.IN,
        interval=PunchInterval.WORK,
    )
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra + timedelta(hours=horas),
        punch_type=PunchType.OUT,
        interval=PunchInterval.WORK,
    )


def la_fuente(company, quien):
    with tenant_context(company.id):
        saldo = rest_debt(employee=quien, company=company, day=HOY)
    if not saldo:
        return None
    return next((f for f in saldo["sources"] if f["source"] == "night"), None)


@pytest.mark.django_db
def test_un_turno_de_noche_entero(company, quien):
    """De 22:00 a 6:00 son ocho horas, todas dentro de la franja."""
    with tenant_context(company.id):
        # 20:00 UTC son las 22:00 de Madrid en agosto.
        trabaja(company, quien, EL_DIA, 20, 8)

    fuente = la_fuente(company, quien)
    assert fuente["owed_hours"] == 8
    assert fuente["citation"] == "Art. 36.2 ET"


@pytest.mark.django_db
def test_solo_cuentan_las_horas_dentro_de_la_franja(company, quien):
    """**El caso que separa contar horas de contar jornadas.**

    De 21:00 a 23:00 son dos horas de jornada y **una** de noche. Un cálculo que
    contara el turno entero por tocar la franja daría el doble, y esa cifra va a
    un saldo que alguien va a disfrutar.
    """
    with tenant_context(company.id):
        # 19:00 UTC = 21:00 de Madrid; dos horas hasta las 23:00.
        trabaja(company, quien, EL_DIA, 19, 2)

    assert la_fuente(company, quien)["owed_hours"] == 1


@pytest.mark.django_db
def test_la_franja_cruza_la_medianoche(company, quien):
    """De 21:00 a 7:00 son diez de jornada y **ocho** de noche, en dos fechas.

    Comparando horas de reloj sueltas ---«22 o más, o menos de 6»--- el tramo se
    parte mal en cuanto cambia el día. Por eso se recorre día a día.
    """
    with tenant_context(company.id):
        trabaja(company, quien, EL_DIA, 19, 10)

    assert la_fuente(company, quien)["owed_hours"] == 8


@pytest.mark.django_db
def test_un_turno_de_dia_no_debe_nada(company, quien):
    """El contraste: sin esto, un cálculo que sumara todas las horas pasaría."""
    with tenant_context(company.id):
        # 6:00 UTC = 8:00 de Madrid, ocho horas hasta las 16:00.
        trabaja(company, quien, EL_DIA, 6, 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "compensacion",
    ["", WorkingTimeRules.NIGHT_PAID, WorkingTimeRules.NIGHT_IN_SALARY],
    ids=["sin declarar", "se paga aparte", "va en el salario"],
)
def test_las_otras_dos_salidas_no_dejan_deuda(company, quien, compensacion):
    """**Las tres salidas del artículo, y solo una llega aquí.**

    Sin declarar no hay de dónde sacar la cifra. Con retribución específica o con
    el salario ya establecido atendiendo a la nocturnidad, lo que queda es un
    concepto de nómina, y eso está fuera de este producto. Las tres dan cero y
    **no por el mismo motivo**, que es lo que estas tres filas separan.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.night_worked_compensation = compensacion
        reglas.save(update_fields=["night_worked_compensation"])
        trabaja(company, quien, EL_DIA, 20, 8)

    assert la_fuente(company, quien) is None


@pytest.mark.django_db
def test_el_multiplicador_del_convenio_manda(company, quien):
    """Hay convenios que devuelven más de una hora por hora nocturna."""
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.night_rest_multiplier = 1.25
        reglas.save(update_fields=["night_rest_multiplier"])
        trabaja(company, quien, EL_DIA, 20, 8)

    assert la_fuente(company, quien)["owed_hours"] == 10


@pytest.mark.django_db
def test_la_franja_de_la_empresa_manda(company, quien):
    """El convenio puede mover la franja, y entonces cambia lo que es de noche.

    Con la franja de 23:00 a 5:00, el turno de 22:00 a 6:00 tiene seis horas
    nocturnas y no ocho. Forzar las del Estatuto sobre un convenio que dice otra
    cosa daría de más o de menos según el caso.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.night_starts_at = time(23, 0)
        reglas.night_ends_at = time(5, 0)
        reglas.save(update_fields=["night_starts_at", "night_ends_at"])
        trabaja(company, quien, EL_DIA, 20, 8)

    assert la_fuente(company, quien)["owed_hours"] == 6


@pytest.mark.django_db
def test_la_pausa_de_noche_no_cuenta_como_trabajo(company, quien):
    """Media hora de cena dentro del turno no es trabajo nocturno.

    Los tramos de pausa se abren con una entrada dentro de la jornada, así que un
    recuento que no mirase el intervalo los sumaría dos veces: una por la jornada
    que los engloba y otra por sí mismos.
    """
    with tenant_context(company.id):
        trabaja(company, quien, EL_DIA, 20, 8)
        pausa = datetime.combine(EL_DIA, datetime.min.time(), tzinfo=UTC).replace(hour=23)
        for momento, tipo in (
            (pausa, PunchType.IN),
            (pausa + timedelta(minutes=30), PunchType.OUT),
        ):
            Punch.objects.create(
                tenant=company,
                employee=quien,
                timestamp=momento,
                punch_type=tipo,
                interval=PunchInterval.BREAK,
            )

    assert la_fuente(company, quien)["owed_hours"] == 8


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company, quien):
    """`User.objects` no acota por empresa, y el saldo se pide por persona."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B66666666", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        reglas = WorkingTimeRules.for_company(vecina)
        reglas.night_worked_compensation = WorkingTimeRules.NIGHT_REST
        reglas.save(update_fields=["night_worked_compensation"])
        suyo = User.objects.create_user(
            email="suyo@vecina.example", password=PASSWORD, tenant=vecina, first_name="Ajeno"
        )
        trabaja(vecina, suyo, EL_DIA, 20, 8)

    with tenant_context(company.id):
        trabaja(company, quien, EL_DIA, 20, 4)

    assert la_fuente(company, quien)["owed_hours"] == 4, "solo las suyas"
