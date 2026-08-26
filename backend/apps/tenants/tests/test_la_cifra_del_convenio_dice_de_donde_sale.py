"""Aplicar una ficha de convenio guardaba el número y perdía el artículo.

El docstring de `WorkingTimeRules` promete «la cifra con el artículo del que
viene», y ese artículo no se guardaba: se tomaba siempre del marco del país.
Medido con la ficha de jardinería, que está en el repositorio:

| | El convenio dice | La pantalla decía |
|---|---|---|
| Descanso entre jornadas | 12 h, **Art. 16** | 12 h, Art. 34.3 ET |
| Descanso en jornada continuada | 15 min, **Art. 16** | 15 min, Art. 34.4 ET |

La cifra coincide y el problema no es la cifra: es la procedencia. Cuando el
convenio se renueve, nadie sabrá que ese valor venía de él; y ante una
inspección, la empresa tiene que poder decir qué norma aplica, no una parecida.

Y hay un detalle que casi se cuela: la procedencia se anota **aunque el valor no
cambie**. Ese es el caso entero --- el convenio de jardinería confirma lo que ya
decía el Estatuto, así que registrarla solo cuando el número se mueve dejaba
fuera justo los campos que interesan.

La `note` del YAML viaja también: es donde la asesoría deja la cita textual y el
razonamiento de la conversión, y era trabajo hecho que no se veía en ninguna
parte.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.agreements import apply_to_rules, load
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
JARDINERIA = Path(settings.AGREEMENTS_DIR) / "es" / "jardineria-estatal.yaml"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Jardines SL", tax_id="B81818181", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Admin",
            last_name="Equis",
            role=Role.ADMIN,
        )


def citas_de(admin):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(admin).access_token)
    )
    return client.get("/api/working-time-rules/").data["citations"]


def aplica_jardineria(company):
    with tenant_context(company.id):
        return apply_to_rules(load(JARDINERIA), WorkingTimeRules.for_company(company))


@pytest.mark.django_db
def test_sin_convenio_la_cita_es_la_del_pais(company, admin):
    """El control: sin ficha aplicada manda el marco legal, como siempre."""
    citas = citas_de(admin)

    assert citas["daily_rest_hours"]["basis"] == "Art. 34.3 ET"
    assert "agreement" not in citas["daily_rest_hours"]


@pytest.mark.django_db
def test_con_el_convenio_aplicado_la_cita_es_la_suya(company, admin):
    aplica_jardineria(company)
    citas = citas_de(admin)

    assert citas["daily_rest_hours"]["basis"] == "Art. 16"
    assert "jardinería" in citas["daily_rest_hours"]["agreement"].lower()


@pytest.mark.django_db
def test_se_anota_aunque_el_valor_no_cambie(company, admin):
    """El caso que casi se cuela, y es el de la mayoría de los campos.

    Jardinería fija el descanso entre jornadas en doce horas, que es lo que ya
    decía el Estatuto: el valor no se mueve y la fuente sí.
    """
    hecho = aplica_jardineria(company)

    assert "daily_rest_hours" in hecho.unchanged, "el caso ya no separa cifra de fuente"
    assert citas_de(admin)["daily_rest_hours"]["basis"] == "Art. 16"


@pytest.mark.django_db
def test_lo_que_el_convenio_no_fija_sigue_citando_la_ley(company, admin):
    """Jardinería va por cómputo anual y no fija las horas semanales."""
    aplica_jardineria(company)

    assert citas_de(admin)["weekly_hours"]["basis"] == "Art. 34.1 ET"


@pytest.mark.django_db
def test_la_nota_de_la_asesoria_llega_a_la_pantalla(company, admin):
    """Es donde está la cita textual del convenio, y no se veía."""
    aplica_jardineria(company)
    nota = citas_de(admin)["daily_rest_hours"]["note"]

    assert "doce horas" in nota, nota


@pytest.mark.django_db
def test_el_suelo_del_pais_no_se_pierde(company, admin):
    """Ningún convenio puede bajar de él, así que sigue sirviendo para avisar."""
    aplica_jardineria(company)
    cita = citas_de(admin)["daily_rest_hours"]

    assert cita["floor"] == 12
    # Y queda dicho qué decía el marco, para no perder la referencia.
    assert cita["framework_basis"] == "Art. 34.3 ET"
