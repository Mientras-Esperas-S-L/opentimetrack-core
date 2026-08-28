"""Cuándo se espera que trabaje quien tiene contrato fijo discontinuo.

El art. 16 ET dice que el trabajo viene «en periodos de actividad». El sistema
sabía que alguien era fijo discontinuo ---el campo existe desde hace tiempo---
pero no **cuándo** lo estaba, y `is_engaged_on` lo decía en su propio texto: era
un hueco nombrado en vez de contestado mal.

Lo que se fija aquí es lo que se decidió al mirarlo, que no es lo que decía el
inventario. **Lo esperado sale del cuadrante**, así que fuera de temporada, si
nadie pone turnos, el sistema ya no espera jornada. Lo que faltaba era poder
decir cuándo es la temporada, que el cuadrante avise si se asigna fuera de ella,
y que quede constancia del llamamiento.

Y una decisión que se comprueba explícitamente abajo: **sin periodos declarados
la relación cubre todo el contrato**. Una empresa que marca a alguien como fijo
discontinuo y todavía no ha cargado sus campañas no puede quedarse con una
persona que no está en activo ningún día del año.
"""

from __future__ import annotations

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import ActivityPeriod, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Temporada SL", tax_id="B63636363", time_zone="Europe/Madrid")


def alguien(empresa, correo, *, seasonal=False, role=Role.EMPLOYEE, **extra):
    with tenant_context(empresa):
        return User.objects.create_user(
            email=correo,
            password=PASSWORD,
            first_name="Quien",
            last_name="Sea",
            role=role,
            tenant=empresa,
            seasonal=seasonal,
            **extra,
        )


def temporada(empresa, persona, desde, hasta=None, llamado=None):
    with tenant_context(empresa):
        return ActivityPeriod.objects.create(
            tenant=empresa,
            employee=persona,
            start_date=desde,
            end_date=hasta,
            called_on=llamado,
        )


# ------------------------------------------------------------------ la regla


def test_dentro_de_la_temporada_esta_en_activo(empresa):
    persona = alguien(empresa, "campania@temporada.local", seasonal=True)
    temporada(empresa, persona, dt.date(2026, 6, 1), dt.date(2026, 9, 30))

    assert persona.is_engaged_on(dt.date(2026, 7, 15))


def test_fuera_de_la_temporada_no(empresa):
    persona = alguien(empresa, "fuera@temporada.local", seasonal=True)
    temporada(empresa, persona, dt.date(2026, 6, 1), dt.date(2026, 9, 30))

    assert not persona.is_engaged_on(dt.date(2026, 2, 3))


def test_una_temporada_sin_fin_sigue_abierta(empresa):
    """Una campaña sabe cuándo empieza y no siempre cuándo acaba. Obligar a
    poner un cierre produciría un dato falso donde hay un hueco honesto."""
    persona = alguien(empresa, "abierta@temporada.local", seasonal=True)
    temporada(empresa, persona, dt.date(2026, 6, 1))

    assert persona.is_engaged_on(dt.date(2027, 1, 20))


def test_sin_temporadas_declaradas_cubre_todo_el_contrato(empresa):
    """La decisión deliberada, y la que sostiene a las de arriba: si esto
    devolviera False, marcar a alguien como fijo discontinuo lo dejaría sin un
    solo día en activo hasta que alguien cargara sus campañas."""
    persona = alguien(empresa, "sinnada@temporada.local", seasonal=True)

    assert persona.is_engaged_on(dt.date(2026, 2, 3))


def test_a_quien_no_es_fijo_discontinuo_no_le_aplica(empresa):
    """El contraste que hace que las demás signifiquen algo: si `is_engaged_on`
    mirara los periodos de cualquiera, las cuatro anteriores pasarían igual y
    esto sería una regla que se aplica a quien no le toca."""
    persona = alguien(empresa, "fija@temporada.local", seasonal=False)
    with tenant_context(empresa):
        ActivityPeriod.objects.create(
            tenant=empresa,
            employee=persona,
            start_date=dt.date(2026, 6, 1),
            end_date=dt.date(2026, 9, 30),
        )

    assert persona.is_engaged_on(dt.date(2026, 2, 3))


def test_la_temporada_no_alarga_un_contrato_terminado(empresa):
    """Las dos condiciones se suman, no se sustituyen."""
    persona = alguien(
        empresa,
        "terminado@temporada.local",
        seasonal=True,
        contract_end=dt.date(2026, 7, 31),
    )
    temporada(empresa, persona, dt.date(2026, 6, 1), dt.date(2026, 9, 30))

    assert persona.is_engaged_on(dt.date(2026, 7, 15))
    assert not persona.is_engaged_on(dt.date(2026, 8, 15))


# --------------------------------------------------------------------- la API


@pytest.fixture
def cliente_admin(empresa):
    admin = alguien(empresa, "admin@temporada.local", role=Role.ADMIN)
    cliente = APIClient()
    cliente.force_authenticate(user=admin)
    return cliente


def test_se_declara_una_temporada_por_la_api(cliente_admin, empresa):
    persona = alguien(empresa, "api@temporada.local", seasonal=True)

    respuesta = cliente_admin.post(
        "/api/activity-periods/",
        {
            "employee": str(persona.id),
            "start_date": "2026-06-01",
            "end_date": "2026-09-30",
            "called_on": "2026-05-15",
        },
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.data
    assert not persona.is_engaged_on(dt.date(2026, 3, 1))


def test_no_se_le_pone_temporada_a_quien_no_es_fijo_discontinuo(cliente_admin, empresa):
    """Guardarlo sería guardar un dato que no hace nada y que quien lo escribió
    cree que sí: `is_engaged_on` solo mira los periodos si `seasonal`."""
    persona = alguien(empresa, "nofijo@temporada.local", seasonal=False)

    respuesta = cliente_admin.post(
        "/api/activity-periods/",
        {"employee": str(persona.id), "start_date": "2026-06-01"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert "art. 16" in str(respuesta.data).lower()


def test_dos_temporadas_no_se_pisan(cliente_admin, empresa):
    persona = alguien(empresa, "solape@temporada.local", seasonal=True)
    temporada(empresa, persona, dt.date(2026, 6, 1), dt.date(2026, 9, 30))

    respuesta = cliente_admin.post(
        "/api/activity-periods/",
        {"employee": str(persona.id), "start_date": "2026-09-01", "end_date": "2026-12-31"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert "2026-06-01" in str(respuesta.data), "el error no dice con cuál se solapa"


def test_el_llamamiento_es_anterior_a_la_temporada(cliente_admin, empresa):
    """Art. 16.3: se llama para que vengan, no después de que hayan venido. La
    fecha es lo que acredita la antelación; un booleano no."""
    persona = alguien(empresa, "tarde@temporada.local", seasonal=True)

    respuesta = cliente_admin.post(
        "/api/activity-periods/",
        {
            "employee": str(persona.id),
            "start_date": "2026-06-01",
            "called_on": "2026-06-15",
        },
        format="json",
    )

    assert respuesta.status_code == 400
    # El motivo por campo, que es donde vive: el `message` de arriba es siempre
    # «los datos enviados no son válidos».
    assert "called_on" in respuesta.data["error"]["details"]
