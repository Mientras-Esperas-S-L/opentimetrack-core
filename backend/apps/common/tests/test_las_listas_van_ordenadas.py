"""Ninguna lista paginada puede venir sin un orden determinista.

Sin `ORDER BY`, PostgreSQL no promete nada entre dos consultas: la página 2
puede repetir filas de la 1 y saltarse otras. No falla, no avisa, y solo se nota
cuando hay más de cincuenta filas ---o sea, en una empresa de verdad y no en
desarrollo---.

## Lo que encontró, y por qué no era «se les olvidó»

Una de doce: el catálogo de turnos. Y su modelo **sí** declara
`ordering = ["name"]`.

Lo que pasa es más sutil: `annotate` con un agregado mete un `GROUP BY`, y
Django descarta la ordenación por defecto en las consultas agregadas. La
anotación se añadió para poder decir cuántos días usan un turno antes de
borrarlo, y se llevó el orden por delante. La única señal era un
`UnorderedObjectListWarning` de DRF que no se ve porque nada convierte los
avisos en fallos.

Por eso la prueba mira **el aviso** y no el código: buscar `order_by` en los
`get_queryset` habría dado limpio, porque el problema es lo que Django hace
después.
"""

from __future__ import annotations

import warnings

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

#: Todas las que paginan. Si aparece una nueva y no está aquí, no se comprueba;
#: por eso la segunda prueba las cuenta contra el enrutador.
LISTAS = [
    "/api/employees/",
    "/api/departments/",
    "/api/workplaces/",
    "/api/punches/",
    "/api/corrections/",
    "/api/absences/",
    "/api/shift-patterns/",
    "/api/shifts/",
    "/api/holidays/",
    "/api/leave-types/",
    "/api/audit/",
    "/api/applications/",
]


@pytest.fixture
def jefa(db):
    empresa = Tenant.objects.create(name="Orden SL", tax_id="B50000001", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        yield (
            empresa,
            User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Luisa",
                role=Role.ADMIN,
            ),
        )


@pytest.mark.django_db
def test_ninguna_lista_paginada_viene_sin_orden(jefa):
    empresa, quien = jefa
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(quien).access_token}")

    sin_orden = []
    respondieron = 0
    with tenant_context(empresa.id):
        for ruta in LISTAS:
            with warnings.catch_warnings(record=True) as avisos:
                warnings.simplefilter("always")
                respuesta = cliente.get(ruta)
            if respuesta.status_code == 200:
                respondieron += 1
            if any("unordered" in str(a.message).lower() for a in avisos):
                sin_orden.append(ruta)

    # Contraste: si las peticiones no llegaran ---un 403, una ruta mal escrita---
    # no habría avisos y la prueba pasaría sin comprobar nada.
    assert respondieron == len(LISTAS), f"solo {respondieron} de {len(LISTAS)} contestaron 200"

    assert not sin_orden, (
        "paginan sin orden, así que la página 2 puede repetir y saltarse filas:\n"
        + "\n".join(sin_orden)
    )


@pytest.mark.django_db
def test_el_catalogo_de_turnos_sigue_ordenado_pese_a_su_anotacion(jefa):
    """El caso concreto, fijado aparte porque su causa es fácil de reintroducir.

    Basta con que alguien añada otra anotación agregada y quite el `order_by`
    explícito creyendo que el `Meta.ordering` del modelo basta. No basta.
    """
    from apps.shifts.models import ShiftPattern
    from apps.shifts.views import ShiftPatternViewSet

    empresa, _quien = jefa
    with tenant_context(empresa.id):
        for nombre in ("Tarde", "Mañana", "Noche"):
            ShiftPattern.objects.create(
                tenant=empresa, name=nombre, segments=[{"start": "08:00", "end": "16:00"}]
            )

        consulta = ShiftPatternViewSet().get_queryset()
        assert consulta.ordered, "la anotación se volvió a llevar el orden por delante"
        assert [p.name for p in consulta] == ["Mañana", "Noche", "Tarde"]
