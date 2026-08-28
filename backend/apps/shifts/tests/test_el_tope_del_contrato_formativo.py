"""Los dos contratos formativos, que eran uno solo, y el tope de uno de ellos.

El art. 11 tiene **dos** contratos formativos y solo uno lleva tope de jornada:

- **En alternancia** (art. 11.2): alterna trabajo y formación, y por eso el
  art. 11.2.b limita el tiempo de trabajo efectivo al 65 % el primer año y al
  85 % el segundo **de la jornada máxima** del convenio o de la ley.
- **Para práctica profesional** (art. 11.3): la jornada es la ordinaria y no
  lleva ese tope.

El producto los tenía en el mismo cajón ---un único `TRAINING`--- y por eso no
podía aplicar el tope a uno sin aplicárselo al otro. Las dos filas del inventario
eran el mismo problema.

**El valor viejo se queda a propósito.** Los contratos formativos ya guardados no
dicen cuál de los dos son, y repartirlos sería decidirlo por quien los firmó: al
primero les inventaría un tope que quizá no les toca; al segundo les quitaría uno
que quizá sí. Se quedan nombrando el hueco, y la revisión lo pide.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import HoursPeriod, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"

LUNES = date(2026, 8, 3)
DOMINGO = LUNES + timedelta(days=6)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Formativa SL", tax_id="B24242424", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        # Cuarenta horas de jornada máxima, que es contra lo que mide el tope.
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.weekly_hours = 40
        reglas.save(update_fields=["weekly_hours"])
    return empresa


def alguien(company, *, email, regime, hours, empezó=None):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Apren",
        last_name="Diz",
        regime=regime,
        contracted_hours=hours,
        contracted_period=HoursPeriod.WEEK,
        contract_start=empezó,
    )


def codigos(company):
    return [f.code for f in review_roster(company=company, first=LUNES, last=DOMINGO)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("horas", "empezó_hace", "avisa"),
    [
        (26, 30, False),  # 65 % justo, primer año
        (28, 30, True),  # se pasa del 65 %
        (28, 400, False),  # el mismo contrato, ya en el segundo año: cabe en el 85 %
        (36, 400, True),  # se pasa hasta del 85 %
    ],
    ids=["65 % justo", "más del 65 %", "segundo año", "más del 85 %"],
)
def test_el_tope_cambia_con_el_ano_del_contrato(company, horas, empezó_hace, avisa):
    """65 % el primer año, 85 % el segundo, sobre las 40 h de jornada máxima.

    El caso del medio es el que da sentido a todo: **veintiocho horas son un
    incumplimiento o no según cuándo empezara el contrato**. Un tope fijo no
    podría distinguirlos, y el que se equivocara acusaría a quien está en regla
    o callaría con quien no lo está.
    """
    with tenant_context(company.id):
        alguien(
            company,
            email=f"alt{horas}-{empezó_hace}@example.com",
            regime=WorkingTimeRegime.TRAINING_ALTERNATING,
            hours=horas,
            empezó=DOMINGO - timedelta(days=empezó_hace),
        )
        assert ("training_hours_over_the_cap" in codigos(company)) is avisa


@pytest.mark.django_db
def test_el_de_practica_profesional_no_lleva_ese_tope(company):
    """El contraste que separa los dos artículos.

    Las mismas treinta y seis horas que en alternancia son un incumplimiento del
    art. 11.2.b, aquí no son nada: el art. 11.3 no tiene ese tope. Si esta prueba
    cayera, el producto estaría inventándole un límite a un contrato que no lo
    tiene, que es lo que hacía tenerlos en el mismo cajón.
    """
    with tenant_context(company.id):
        alguien(
            company,
            email="practica@example.com",
            regime=WorkingTimeRegime.TRAINING_PRACTICE,
            hours=36,
            empezó=DOMINGO - timedelta(days=30),
        )
        assert "training_hours_over_the_cap" not in codigos(company)


@pytest.mark.django_db
def test_el_formativo_sin_concretar_lo_dice(company):
    """El que no dice cuál es, y por qué no se adivina.

    Sin saber si es de alternancia o de práctica, no se puede decir si le toca el
    tope. El aviso pide que se concrete en vez de elegir por su cuenta.
    """
    with tenant_context(company.id):
        alguien(
            company,
            email="sinconcretar@example.com",
            regime=WorkingTimeRegime.TRAINING,
            hours=36,
            empezó=DOMINGO - timedelta(days=30),
        )
        salidas = codigos(company)
        assert "training_kind_not_stated" in salidas
        # Y **no** el del tope: eso sería adivinar que es de alternancia, que es
        # exactamente lo que este aviso existe para no hacer.
        assert "training_hours_over_the_cap" not in salidas


@pytest.mark.django_db
def test_sin_fecha_de_contrato_se_usa_el_tope_mas_laxo(company):
    """Acusar sobre un dato que falta es peor que no acusar.

    Sin `contract_start` no se sabe en qué año va, y quien podría estar en su
    segundo año no debería aparecer como incumplidor del 65 %. Se usa el 85 %:
    quien se pasa de ahí se pasa en cualquier año, y de ese sí se puede hablar.
    """
    with tenant_context(company.id):
        alguien(
            company,
            email="sinfecha@example.com",
            regime=WorkingTimeRegime.TRAINING_ALTERNATING,
            hours=30,  # pasa del 65 % (26) y no del 85 % (34)
            empezó=None,
        )
        assert "training_hours_over_the_cap" not in codigos(company)

        alguien(
            company,
            email="sinfecha-pasado@example.com",
            regime=WorkingTimeRegime.TRAINING_ALTERNATING,
            hours=38,  # pasa hasta del 85 %
            empezó=None,
        )
        assert "training_hours_over_the_cap" in codigos(company)


@pytest.mark.django_db
def test_el_tope_mide_contra_la_jornada_maxima_no_contra_lo_pactado(company):
    """Lo que dice el artículo: «de la jornada máxima prevista en el convenio».

    Medirlo contra lo que el propio contrato pactara sería una tautología ---todo
    contrato cumple el 100 % de sí mismo--- y el tope no diría nada nunca. La
    prueba lo fija bajando la jornada máxima de la empresa: las mismas 26 horas
    pasan de ir holgadas a pasarse, sin que el contrato cambie.
    """
    with tenant_context(company.id):
        alguien(
            company,
            email="contra-la-maxima@example.com",
            regime=WorkingTimeRegime.TRAINING_ALTERNATING,
            hours=26,
            empezó=DOMINGO - timedelta(days=30),
        )
        assert "training_hours_over_the_cap" not in codigos(company)

        reglas = WorkingTimeRules.for_company(company)
        reglas.weekly_hours = 35  # el 65 % son 22,75
        reglas.save(update_fields=["weekly_hours"])
        assert "training_hours_over_the_cap" in codigos(company)
