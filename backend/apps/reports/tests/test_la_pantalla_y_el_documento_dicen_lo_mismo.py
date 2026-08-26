"""El tope de jornada abierta lo resolvían dos sitios, y con un cero discrepaban.

`punches.services` decide qué jornada sigue abierta y el informe decide a qué día
pertenece cada evento. Los dos leen `max_open_hours`, y lo resolvían por su
cuenta: el primero con `getattr(rules, ..., None) or DEFAULT`, el segundo con el
campo a pelo.

Con el campo en **cero** ---que la API aceptaba con un 200 y sin avisos, porque
`PositiveSmallIntegerField` lo admite y no había suelo--- eso los separaba:

- fichar se comportaba como si el tope fuera 16, porque el cero caía al valor por
  defecto,
- y el informe se quedaba con el cero, así que un turno de noche bien fichado
  salía como `21:00;;00:00;entrada sin salida`.

El comentario del informe promete lo contrario: «la cifra en pantalla y la del
documento son el mismo día». Dos arreglos, uno por cada mitad: el tope tiene suelo
de una hora ---cero no significa nada--- y el informe pregunta a la misma función
que el fichaje.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.punches.services import max_open_hours
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="De noche", tax_id="B91500001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Noche",
        )
        # Entra el 10 a las 21:00 y sale el 11 a las 05:00.
        entrada = datetime(2026, 3, 10, 20, 0, tzinfo=UTC)
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type="IN",
            interval="WORK",
            timestamp=entrada,
            source="WEB",
            time_zone="Europe/Madrid",
        )
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type="OUT",
            interval="WORK",
            timestamp=entrada + timedelta(hours=8),
            source="WEB",
            time_zone="Europe/Madrid",
        )
        yield {"empresa": empresa, "jefa": jefa, "quien": quien}


def como(quien):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente


def fila_de_la_noche(mundo):
    respuesta = como(mundo["jefa"]).get(
        "/api/reports/working-time/"
        f"?date_from=2026-03-05&date_to=2026-03-15&employee={mundo['quien'].pk}&format=csv"
    )
    assert respuesta.status_code == 200, respuesta.content
    filas = [
        linea
        for linea in respuesta.content.decode("utf-8-sig", "replace").splitlines()
        if linea.startswith("2026-03-1")
    ]
    assert filas, "la jornada no aparecía"
    return filas[0]


@pytest.mark.django_db
def test_un_tope_de_cero_se_rechaza(mundo):
    respuesta = como(mundo["jefa"]).patch(
        "/api/working-time-rules/", {"max_open_hours": 0}, format="json"
    )

    assert respuesta.status_code == 400, "un tope de cero se aceptaba sin decir nada"
    assert "max_open_hours" in respuesta.json()["error"]["details"]


@pytest.mark.django_db
def test_y_la_jornada_de_noche_sale_entera(mundo):
    """Con el tope por defecto, entrada y salida son la misma jornada."""
    assert "05:00" in fila_de_la_noche(mundo), fila_de_la_noche(mundo)
    assert "entrada sin salida" not in fila_de_la_noche(mundo)


@pytest.mark.django_db
def test_los_dos_resuelven_el_tope_igual(mundo):
    """La razón de fondo: una sola función lo decide para los dos.

    Con dos resoluciones distintas, cualquier valor que una trate de forma
    especial ---el cero, un nulo--- separa la pantalla del documento sin que nada
    lo avise.
    """
    with tenant_context(mundo["empresa"].id):
        reglas = WorkingTimeRules.for_company(mundo["empresa"])
        # Se escribe sin pasar por la validación, como lo haría un dato heredado
        # de antes del suelo o una migración a medias.
        WorkingTimeRules.objects.filter(pk=reglas.pk).update(max_open_hours=0)
        mundo["empresa"].refresh_from_db()
        reglas.refresh_from_db()

        # El fichaje cae al valor por defecto...
        assert max_open_hours(mundo["quien"], mundo["empresa"], reglas) == 16

    # ...y el informe tiene que caer al mismo, no quedarse con el cero.
    assert "entrada sin salida" not in fila_de_la_noche(mundo), (
        "el documento leía el cero que la pantalla ignoraba"
    )


@pytest.mark.django_db
def test_subirlo_para_guardias_de_veinticuatro_horas_sigue_valiendo(mundo):
    """Lo que el ajuste existe para permitir, y que el suelo no puede estorbar."""
    respuesta = como(mundo["jefa"]).patch(
        "/api/working-time-rules/", {"max_open_hours": 24}, format="json"
    )
    assert respuesta.status_code == 200, respuesta.content

    with tenant_context(mundo["empresa"].id):
        assert WorkingTimeRules.for_company(mundo["empresa"]).max_open_hours == 24
