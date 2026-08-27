"""El sello vale por el instante, no por cómo se escribió el instante.

`compute_hash` metía en la huella `timestamp.isoformat()`, y esa cadena no
depende solo del momento sino del huso en que esté el objeto que lo lleva. El
mismo fichaje da dos escrituras:

    2026-07-02T06:58:00+02:00   <- construido en la hora de la empresa
    2026-07-02T04:58:00+00:00   <- releído de la base, que devuelve UTC

Así que todo lo que se escribiera con la hora local ---una importación, la
semilla, una integración que arme el instante en el huso del centro--- se sellaba
con una cadena y se verificaba con la otra. Medido sobre la base de desarrollo:
**577 de 1.185 fichajes daban el sello por roto y los 577 cuadraban en hora
local**. El informe del art. 34.9 los acusaba de haberse «alterado fuera de la
aplicación» sin que nadie los hubiera tocado, que es la acusación más grave que
ese documento puede hacer.

Lo que **no** puede pasar es que arreglar esto afloje el sello, así que la mitad
de este fichero son alteraciones de verdad que tienen que seguir cazándose.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.common.models import tenant_context
from apps.punches.models import (
    CURRENT_HASH_VERSION,
    Punch,
    PunchInterval,
    PunchSource,
    PunchType,
)
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
CUANDO = datetime(2026, 7, 2, 4, 58, tzinfo=UTC)


@pytest.fixture
def gente(db):
    empresa = Tenant.objects.create(
        name="Sello SL", tax_id="B33333333", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="sello@example.com", password=PASSWORD, tenant=empresa,
            first_name="Sel", last_name="Lo",
        )
        yield empresa, quien


def _ficha(empresa, quien, cuando, **extra):
    return Punch.objects.create(
        tenant=empresa, employee=quien, punch_type=PunchType.IN,
        interval=PunchInterval.WORK, timestamp=cuando, **extra,
    )


@pytest.mark.django_db
def test_sellado_en_hora_local_y_releido_en_utc(gente):
    """El caso que rompía. Se graba con el instante en la hora de la empresa,
    que es como lo arma cualquiera que trabaje con horas de pared."""
    empresa, quien = gente
    with tenant_context(empresa.id):
        creado = _ficha(empresa, quien, CUANDO.astimezone(empresa.tzinfo))
        # Releído: la base devuelve UTC, que es otra escritura del mismo momento.
        vuelto = Punch.objects.get(pk=creado.pk)

    assert vuelto.timestamp == CUANDO, "no es el mismo instante, la prueba no dice nada"
    assert vuelto.timestamp.isoformat() != CUANDO.astimezone(empresa.tzinfo).isoformat()
    assert vuelto.verify_hash(), (
        "nadie tocó este fichaje y el sello lo da por alterado: es la acusación "
        "que el informe del art. 34.9 pone por escrito"
    )


@pytest.mark.django_db
def test_los_nuevos_se_sellan_en_utc(gente):
    empresa, quien = gente
    with tenant_context(empresa.id):
        creado = _ficha(empresa, quien, CUANDO.astimezone(empresa.tzinfo))

    assert creado.hash_version == CURRENT_HASH_VERSION >= 4
    assert creado.hash_integrity == creado._hash_v4()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("punch_type", PunchType.OUT),
        ("source", PunchSource.ADMIN),
        ("interval", PunchInterval.BREAK),
        ("hours_nature", "OVERTIME"),
    ],
)
def test_cambiar_lo_que_el_sello_cubre_lo_rompe(gente, campo, valor):
    """El contraste. Sin esto, un `verify_hash` que devolviera siempre `True`
    pasaría las de arriba."""
    empresa, quien = gente
    with tenant_context(empresa.id):
        creado = _ficha(empresa, quien, CUANDO)
        setattr(creado, campo, valor)

    assert not creado.verify_hash(), f"cambiar {campo} tiene que romper el sello"


@pytest.mark.django_db
def test_mover_la_hora_lo_rompe_aunque_el_desfase_sea_el_del_huso(gente):
    """El caso que más de cerca pasa: adelantar el fichaje exactamente las dos
    horas que Madrid lleva en verano. El desfase va dentro de la cadena, así que
    no se confunde con la misma hora escrita en otro huso."""
    empresa, quien = gente
    with tenant_context(empresa.id):
        creado = _ficha(empresa, quien, CUANDO.astimezone(empresa.tzinfo))
        creado.timestamp = CUANDO.replace(hour=CUANDO.hour + 2)

    assert not creado.verify_hash(), "un fichaje movido dos horas no puede colar"


@pytest.mark.django_db
def test_las_versiones_viejas_siguen_verificando_bajo_su_regla(gente):
    """Nunca se reescribe un sello guardado. Un evento de la v3 se sigue
    comprobando con la v3, incluida su escritura en hora local."""
    empresa, quien = gente
    with tenant_context(empresa.id):
        creado = _ficha(empresa, quien, CUANDO.astimezone(empresa.tzinfo))
        # Se rehace como lo haría un registro antiguo: sello de la v3, calculado
        # sobre la hora local, tal como quedaron los 577 de la base.
        creado.hash_version = 3
        creado.hash_integrity = creado._hash_v3()
        creado.save(update_fields=["hash_version", "hash_integrity"])
        vuelto = Punch.objects.get(pk=creado.pk)

    assert vuelto.hash_version == 3
    assert vuelto.verify_hash(), "un fichaje de la v3 sellado en local tiene que seguir valiendo"

    vuelto.punch_type = PunchType.OUT
    assert not vuelto.verify_hash(), "y seguir rompiéndose si se le cambia algo"
