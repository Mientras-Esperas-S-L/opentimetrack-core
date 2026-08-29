"""Lo que el saldo de descanso **no** cuenta, y por qué lo dice (RD 1561/1995).

Los arts. 4 a 10 amplían la jornada en sectores concretos ---porteros, guardas,
campo, hostelería, transporte por carretera, ferrocarril, mar, aire y sanidad---
y cada uno establece a cambio sus propios descansos compensatorios.

**El producto no los calcula, y es una decisión, no una laguna.** Haría falta la
cifra de cada sector: son quince números por cada uno de los trece regímenes, y
todos esos sectores tienen además convenio propio. Un número nuestro pisando el
suyo se leería como la ley.

Lo que sí se puede hacer, y es lo que faltaba: **decirlo**. Sin esa línea, quien
trabaja en hostelería abre su saldo, ve las fuentes con sus artículos y da por
hecho que están todas. Un saldo incompleto que no avisa de estarlo es peor que no
tener saldo: el primero se cree.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.punches.rest_debt import rest_debt
from apps.tenants.models import Tenant
from apps.tenants.rules import SpecialRegime, WorkingTimeRules
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
HOY = date(2026, 8, 28)
EL_DIA = date(2026, 8, 17)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Bar Demo SL", tax_id="B99999999", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.night_worked_compensation = WorkingTimeRules.NIGHT_REST
        reglas.save(update_fields=["night_worked_compensation"])
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        persona = User.objects.create_user(
            email="camarero@example.com", password=PASSWORD, tenant=company, first_name="Quien"
        )
        # Una noche trabajada, para que haya saldo del que hablar.
        entra = datetime.combine(EL_DIA, datetime.min.time(), tzinfo=UTC).replace(hour=20)
        for momento, kind in ((entra, PunchType.IN), (entra + timedelta(hours=8), PunchType.OUT)):
            Punch.objects.create(
                tenant=company,
                employee=persona,
                timestamp=momento,
                punch_type=kind,
                interval=PunchInterval.WORK,
            )
        yield persona


def declara(company, regimen):
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.special_regime = regimen
        reglas.save(update_fields=["special_regime"])


def el_saldo(company, quien):
    with tenant_context(company.id):
        return rest_debt(employee=quien, company=company, day=HOY)


@pytest.mark.django_db
def test_en_un_sector_de_ampliacion_el_saldo_dice_que_no_esta_completo(company, quien):
    declara(company, SpecialRegime.RETAIL_HOSPITALITY)

    aviso = el_saldo(company, quien)["sector"]
    assert aviso["citation"] == "RD 1561/1995"
    # Con el nombre del sector, no con la clave: «RETAIL_HOSPITALITY» en mitad de
    # una frase no le dice nada a quien la lee.
    assert aviso["regime"] and aviso["regime"] != SpecialRegime.RETAIL_HOSPITALITY.value


@pytest.mark.django_db
def test_sin_regimen_declarado_no_hay_nada_que_matizar(company, quien):
    """El contraste. La mayoría de las empresas van por la regla general, y un
    aviso ahí sería una advertencia sobre algo que no les pasa."""
    declara(company, "")

    assert el_saldo(company, quien)["sector"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "regimen",
    [
        SpecialRegime.HAZARDOUS,
        SpecialRegime.COLD_STORAGE,
        SpecialRegime.MINING,
        SpecialRegime.CONSTRUCTION,
    ],
)
def test_una_limitacion_no_deja_nada_pendiente(company, quien, regimen):
    """**La distinción que hace falta.** El RD tiene dos clases de régimen y solo
    una amplía la jornada. Una limitación la recorta: no trae descansos
    compensatorios que echar en falta, y avisar de ellos sería inventar una deuda
    a una empresa que no la tiene."""
    declara(company, regimen)

    assert el_saldo(company, quien)["sector"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "regimen",
    [
        SpecialRegime.URBAN_PROPERTY,
        SpecialRegime.GUARDS,
        SpecialRegime.FARMING,
        SpecialRegime.RETAIL_HOSPITALITY,
        SpecialRegime.ROAD_TRANSPORT,
        SpecialRegime.RAIL,
        SpecialRegime.SEA,
        SpecialRegime.AIR,
        SpecialRegime.HEALTHCARE,
    ],
)
def test_las_nueve_ampliaciones_avisan(company, quien, regimen):
    """Las nueve, una por una. Con una lista escrita a mano en dos sitios ---la
    clasificación y esta prueba--- añadir un régimen nuevo y olvidarse de
    clasificarlo se nota aquí y no en producción."""
    declara(company, regimen)

    assert el_saldo(company, quien)["sector"] is not None


@pytest.mark.django_db
def test_el_aviso_no_inventa_deuda(company, quien):
    """Avisa de lo que no cuenta; no suma horas.

    Si el aviso tocara las cifras, una empresa de hostelería vería un saldo
    distinto por haber declarado su sector, y ese número no saldría de ninguna
    parte. Se dice lo que falta; no se estima.
    """
    declara(company, "")
    sin_regimen = el_saldo(company, quien)
    declara(company, SpecialRegime.RETAIL_HOSPITALITY)
    con_regimen = el_saldo(company, quien)

    for campo in ("owed_hours", "remaining_hours", "overdue_hours"):
        assert sin_regimen[campo] == con_regimen[campo], campo
    assert [f["source"] for f in sin_regimen["sources"]] == [
        f["source"] for f in con_regimen["sources"]
    ]
