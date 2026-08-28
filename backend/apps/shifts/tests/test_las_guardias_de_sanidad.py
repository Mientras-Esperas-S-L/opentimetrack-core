"""La guardia de presencia en sanidad cuenta para la jornada máxima.

El producto separa jornada de tiempo de presencia porque el art. 3.g del real
decreto de registro obliga a anotarlos aparte, y `counts_as_work` solo es cierto
para la jornada. Fuera de sanidad eso es correcto: la espera de quien conduce no
es trabajo efectivo.

En sanidad la respuesta lleva veinte años dada y es la contraria. SIMAP
(C-303/98) y Jaeger (C-151/02): **la guardia de presencia física en el centro es
tiempo de trabajo en su totalidad** a efectos de la jornada máxima y de los
descansos, se atienda a alguien o se pase la noche entera sin que suene nada. La
guardia localizada no, salvo la parte de atención efectiva ---y esa se ficha como
jornada, así que ya contaba---.

Lo que había: una guardia de veinticuatro horas en el hospital no contaba **nada**
para el tope semanal. Con cuarenta de jornada y dos guardias, el producto veía
cuarenta horas y la persona había estado ochenta y ocho en el centro.

Lo que hay: un aviso. No se toca ningún total ---el registro sigue separando las
dos cosas, que es lo que la ley obliga--- y no se bloquea nada, porque quien tiene
que decidir cómo lo arregla es la empresa.

**Solo con el régimen de sanidad declarado**, por lo mismo que el tope de
presencia del transporte solo aplica al transporte: aplicárselo a una oficina
sería inventarle una regla de otro sector.
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

#: Una semana ISO entera, de lunes a domingo. Que el rango la cubra importa: una
#: semana partida por la mitad no llega al tope y no avisaría nunca.
LUNES = date(2026, 8, 24)
DOMINGO = date(2026, 8, 30)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Hospital Demo", tax_id="B41414141", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.special_regime = SpecialRegime.HEALTHCARE
        reglas.save(update_fields=["special_regime"])
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="guardia@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Guardia",
        )


def tramo(company, quien, dia, horas, *, desde=6, interval=PunchInterval.WORK):
    """Un tramo de ese tipo. `desde` va en UTC: las 6 son las ocho de Madrid."""
    entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=desde)
    for moment, kind in ((entra, PunchType.IN), (entra + timedelta(hours=horas), PunchType.OUT)):
        Punch.objects.create(
            tenant=company,
            employee=quien,
            timestamp=moment,
            punch_type=kind,
            interval=interval,
        )


def jornada_y_guardias(company, quien, *, jornada, guardia):
    """Jornada de lunes a viernes por la mañana, guardias por la tarde.

    Las dos cosas en días que no chocan entre sí, y **ninguna cruzando la
    medianoche**: ese caso tiene su propia prueba más abajo, porque es el que
    rompía el primer diseño de esta comprobación.
    """
    dia = LUNES
    restan = jornada
    while restan > 0:
        cuanto = min(8, restan)
        tramo(company, quien, dia, cuanto)
        restan -= cuanto
        dia += timedelta(days=1)

    dia, restan = LUNES, guardia
    while restan > 0:
        cuanto = min(7, restan)
        tramo(company, quien, dia, cuanto, desde=14, interval=PunchInterval.STANDBY)
        restan -= cuanto
        dia += timedelta(days=1)


def codigos(company):
    return [f.code for f in review_roster(company=company, first=LUNES, last=DOMINGO)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("jornada", "guardia", "avisa"),
    [(40, 0, False), (36, 10, False), (40, 12, True), (0, 49, True)],
    ids=[
        "solo jornada, no llega",
        "las dos cosas, aun por debajo",
        "la guardia cruza el tope",
        "guardia sola, que es el caso de SIMAP",
    ],
)
def test_la_guardia_suma_para_el_tope_semanal(company, quien, jornada, guardia, avisa):
    """Las dos primeras filas son el contraste de las dos últimas.

    Sin ellas, un chequeo que avisara a **cualquiera** que tenga una guardia
    anotada pasaría igual, y estaría diciendo algo falso: tener guardias no es
    incumplir nada, pasar de cuarenta y ocho horas sí.

    La última fila es SIMAP en una línea: cuarenta y nueve horas de presencia sin un
    minuto de jornada. Antes de esto el producto veía cero.
    """
    with tenant_context(company.id):
        jornada_y_guardias(company, quien, jornada=jornada, guardia=guardia)
        assert ("on_call_over_the_weekly_maximum" in codigos(company)) is avisa


@pytest.mark.django_db
def test_sin_declarar_sanidad_no_se_avisa(company, quien):
    """Fuera de sanidad la presencia no es trabajo, y decir lo contrario sería inventar.

    La espera de quien conduce un camión está expresamente excluida del trabajo
    efectivo. Avisar a esa empresa de que incumple la jornada máxima sería
    acusarla de algo que no ha hecho.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.special_regime = SpecialRegime.NONE
        reglas.save(update_fields=["special_regime"])

        jornada_y_guardias(company, quien, jornada=40, guardia=12)
        assert "on_call_over_the_weekly_maximum" not in codigos(company)


@pytest.mark.django_db
def test_otro_regimen_especial_tampoco_lo_hereda(company, quien):
    """El contraste del anterior, y no dicen lo mismo.

    Sin esto, «solo en sanidad» y «en cualquier régimen especial» se verían
    igual. El transporte tiene su propio tope de presencia ---veinte horas de
    promedio--- y **no** la regla de SIMAP: ahí la espera sigue sin ser trabajo.
    """
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.special_regime = SpecialRegime.ROAD_TRANSPORT
        reglas.save(update_fields=["special_regime"])

        jornada_y_guardias(company, quien, jornada=40, guardia=12)
        assert "on_call_over_the_weekly_maximum" not in codigos(company)


@pytest.mark.django_db
def test_la_pausa_no_infla_la_cuenta(company, quien):
    """La comida no es tiempo de trabajo, y sumarla pondría a gente por encima del tope.

    Con la pausa descontada son cuarenta y seis horas; sin descontarla, cincuenta
    y una. La diferencia entre avisar a quien va en regla y no avisar.

    **Esta prueba nació sin medir nada.** La primera versión daba solo jornada y
    pausas, y entonces la persona ni entraba en la cuenta: el chequeo empieza por
    quedarse con quien tiene presencia anotada, así que sin una sola guardia se
    salía por el filtro y la suma no se ejecutaba nunca. Pasaba con la pausa
    restada y pasaba sin restar. Las seis horas de guardia están aquí para que la
    persona llegue hasta donde se suma.
    """
    with tenant_context(company.id):
        dia = LUNES
        for _ in range(5):
            tramo(company, quien, dia, 9)
            entra = datetime.combine(dia, datetime.min.time(), tzinfo=UTC).replace(hour=10)
            for moment, kind in (
                (entra, PunchType.IN),
                (entra + timedelta(hours=1), PunchType.OUT),
            ):
                Punch.objects.create(
                    tenant=company,
                    employee=quien,
                    timestamp=moment,
                    punch_type=kind,
                    interval=PunchInterval.BREAK,
                )
            dia += timedelta(days=1)

        tramo(company, quien, LUNES + timedelta(days=5), 6, interval=PunchInterval.STANDBY)

        # 45 de jornada bruta - 5 de comidas + 6 de guardia = 46.
        assert "on_call_over_the_weekly_maximum" not in codigos(company)


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company, quien):
    """`User.objects` no acota por empresa, y aquí las personas salen de ahí."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B42424242", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        reglas = WorkingTimeRules.for_company(vecina)
        reglas.special_regime = SpecialRegime.HEALTHCARE
        reglas.save(update_fields=["special_regime"])
        suyo = User.objects.create_user(
            email="suyo@vecina.example", password=PASSWORD, tenant=vecina, first_name="Ajeno"
        )
        jornada_y_guardias(vecina, suyo, jornada=40, guardia=14)

    with tenant_context(company.id):
        jornada_y_guardias(company, quien, jornada=40, guardia=14)
        avisos = review_roster(company=company, first=LUNES, last=DOMINGO)
        de_quien = {f.employee_id for f in avisos if f.code == "on_call_over_the_weekly_maximum"}

        assert quien.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suyo.id not in de_quien


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("jornada", "avisa"),
    [(30, True), (16, False)],
    ids=["con la guardia se pasa", "sin llegar al tope, no"],
)
def test_una_guardia_que_cruza_la_medianoche_cuenta_entera(company, quien, jornada, avisa):
    """**La prueba que más vale de este fichero**, y la que tumbó el primer diseño.

    Una guardia de sanidad son veinticuatro horas y empieza por la mañana: cruza
    la medianoche por definición. La primera versión de esta comprobación leía
    cada día con `build_day_status` ---la pieza que ya sabe descontar pausas y
    separar la presencia--- y era la opción correcta salvo por esto: esa pieza
    recorta los eventos al día, así que el lunes veía una entrada que no se
    cierra y el martes una salida que no abre nada. **La guardia entera contaba
    cero en los dos.** Justo el caso que había que medir.

    Treinta horas de jornada más una guardia de veinticuatro son cincuenta y
    cuatro. La segunda fila es el contraste: dieciséis más veinticuatro son
    cuarenta, y ahí no hay nada que avisar.
    """
    with tenant_context(company.id):
        jornada_y_guardias(company, quien, jornada=jornada, guardia=0)
        # Del martes a las 08:00 al miércoles a las 08:00, sin tocar las mañanas
        # de jornada, que van de lunes a martes como mucho con estas cifras.
        tramo(
            company,
            quien,
            LUNES + timedelta(days=4),
            24,
            desde=6,
            interval=PunchInterval.STANDBY,
        )
        assert ("on_call_over_the_weekly_maximum" in codigos(company)) is avisa
