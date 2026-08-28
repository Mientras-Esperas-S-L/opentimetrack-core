"""El tope de tiempo de presencia del transporte por carretera (RD 1561/1995).

    «El tiempo de presencia no podrá exceder en ningún caso de veinte horas
    semanales de promedio en un periodo de referencia de un mes» --- art. 8.b.

**Tiempo de presencia** es estar a disposición sin trabajo efectivo: esperas,
viajes sin servicio, averías, comidas en ruta. El producto ya sabía anotarlo
---`PunchInterval.STANDBY`, que es el art. 3.g del real decreto de registro--- y
no lo contaba contra nada.

**Lo que hace distinta a esta comprobación de todas las demás de la revisión:
solo aplica a un sector.** El resto mide contra el Estatuto, que es de todos.
Las veinte horas son del transporte por carretera, y aplicárselas a una oficina
sería inventarle un límite que su sector no tiene --- que es exactamente el error
contrario al que esta auditoría persigue, pero un error igual.

Por eso hay un régimen declarado, y por eso la prueba que más vale de este
fichero es la que comprueba que **sin declararlo no se avisa**.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import SpecialRegime, WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: Agosto de 2026: treinta y un días, o sea 4,43 semanas. Veinte horas de
#: promedio son 88,6 horas en el mes.
PRIMERO = date(2026, 8, 1)
MIRANDO = date(2026, 8, 31)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Transportes SL", tax_id="B31313131", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.special_regime = SpecialRegime.ROAD_TRANSPORT
        reglas.save(update_fields=["special_regime"])
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="camion@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Conduce",
        )


def espera(company, quien, horas_totales):
    """Reparte ese tiempo de presencia en tramos de cuatro horas."""
    dia = PRIMERO
    restan = horas_totales
    while restan > 0:
        cuanto = min(4, restan)
        entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=6)
        Punch.objects.create(
            tenant=company,
            employee=quien,
            timestamp=entra,
            punch_type=PunchType.IN,
            interval=PunchInterval.STANDBY,
        )
        Punch.objects.create(
            tenant=company,
            employee=quien,
            timestamp=entra + timedelta(hours=cuanto),
            punch_type=PunchType.OUT,
            interval=PunchInterval.STANDBY,
        )
        restan -= cuanto
        dia += timedelta(days=1)


def codigos(company):
    return [f.code for f in review_roster(company=company, first=PRIMERO, last=MIRANDO)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("horas", "avisa"),
    [(80, False), (88, False), (100, True)],
    ids=["holgado", "justo por debajo", "por encima"],
)
def test_el_promedio_semanal_del_mes(company, quien, horas, avisa):
    """Veinte horas de promedio en agosto son 88,6 en el mes.

    El promedio va sobre el **mes natural** porque la ley da un periodo de
    referencia de un mes; una ventana móvil daría un tope que cambia cada mañana
    y que nadie puede comprobar en un calendario.
    """
    with tenant_context(company.id):
        espera(company, quien, horas)
        assert ("standby_over_the_average" in codigos(company)) is avisa


@pytest.mark.django_db
def test_sin_declarar_el_regimen_no_se_avisa(company, quien):
    """**La prueba que más vale de este fichero.**

    Las veinte horas son del transporte por carretera. Una oficina con cien
    horas de espera anotadas no incumple nada: no tiene ese límite. Avisarle
    sería inventarle una norma de otro sector, que es el error contrario al que
    esta auditoría persigue y uno igual de malo.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.special_regime = SpecialRegime.NONE
        reglas.save(update_fields=["special_regime"])

        espera(company, quien, 100)
        assert "standby_over_the_average" not in codigos(company)


@pytest.mark.django_db
def test_otro_regimen_especial_tampoco_lo_hereda(company, quien):
    """El contraste del anterior, y no es lo mismo.

    Sin esto, «solo en transporte» y «en cualquier régimen especial» se verían
    igual: las dos harían pasar la prueba de arriba. Sanidad tiene guardias y
    tiene sus propias reglas, pero **no** las veinte horas del art. 8.b.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.special_regime = SpecialRegime.HEALTHCARE
        reglas.save(update_fields=["special_regime"])

        espera(company, quien, 100)
        assert "standby_over_the_average" not in codigos(company)


@pytest.mark.django_db
def test_el_trabajo_efectivo_no_cuenta_como_presencia(company, quien):
    """Son dos cosas distintas y el artículo las separa.

    Cien horas conduciendo no son cien horas de espera. Contarlas juntas
    convertiría una jornada normal en un incumplimiento, y de paso haría inútil
    la distinción que el art. 3.g pide anotar.

    **Quien conduce tiene las dos cosas**, y esa mezcla es la que hay que
    probar. La primera versión de esta prueba daba solo trabajo efectivo, y
    entonces la persona ni siquiera entraba en la cuenta ---el recorte de arriba
    la dejaba fuera por no tener presencia ninguna---. Pasaba por el sitio
    equivocado: contar mal la suma no la ponía roja.
    """
    with tenant_context(company.id):
        # Cuarenta horas de espera: por debajo del tope, no avisa.
        espera(company, quien, 40)

        # Y ciento cuatro conduciendo, en días que no chocan con las esperas.
        dia = PRIMERO + timedelta(days=15)
        for _ in range(13):
            entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=6)
            Punch.objects.create(
                tenant=company, employee=quien, timestamp=entra, punch_type=PunchType.IN
            )
            Punch.objects.create(
                tenant=company,
                employee=quien,
                timestamp=entra + timedelta(hours=8),
                punch_type=PunchType.OUT,
            )
            dia += timedelta(days=1)

        # Las 144 juntas pasarían de sobra del tope; las 40 de presencia, no.
        assert "standby_over_the_average" not in codigos(company)


@pytest.mark.django_db
def test_un_cero_apaga_el_tope(company, quien):
    """Para el convenio que fije el promedio de otra forma.

    Forzar el número del real decreto sobre un convenio que dice otra cosa sería
    decir algo falso con aire de dato.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.standby_weekly_hours = 0
        reglas.save(update_fields=["standby_weekly_hours"])

        espera(company, quien, 200)
        assert "standby_over_the_average" not in codigos(company)


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company, quien):
    """`User.objects` no acota por empresa, y aquí las personas salen de ahí."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B32323232", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        reglas = WorkingTimeRules.for_company(vecina)
        reglas.special_regime = SpecialRegime.ROAD_TRANSPORT
        reglas.save(update_fields=["special_regime"])
        suyo = User.objects.create_user(
            email="suyo@vecina.example", password=PASSWORD, tenant=vecina, first_name="Ajeno"
        )
        espera(vecina, suyo, 200)

    with tenant_context(company.id):
        espera(company, quien, 200)
        avisos = review_roster(company=company, first=PRIMERO, last=MIRANDO)
        de_quien = {f.employee_id for f in avisos if f.code == "standby_over_the_average"}

        assert quien.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suyo.id not in de_quien
