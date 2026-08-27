"""El guardián del rastro tiene que ver también un trigger apagado.

`_check_audit_is_append_only` existe porque los tres triggers **se perdieron**
una vez en una base real, con la migración marcada como aplicada: una garantía
que solo vive en una migración se evapora sin ruido. Preguntaba si estaban.

Estar no basta. `ALTER TABLE ... DISABLE TRIGGER` los deja en `pg_trigger` con
el mismo nombre y sin disparar, que es lo que hace `pg_restore
--disable-triggers` --- la restauración que el propio comentario del guardián ya
citaba entre las formas de perderlos. Medido contra la base de desarrollo: con
`audit_log_no_update` apagado, la comprobación contestaba «ok» y una fila del
rastro se dejó reescribir.

«Un rastro de auditoría que puede editar aquel a quien incrimina no es prueba»,
dice la migración que los crea.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.common.views import GUARDIANES, _check_audit_is_append_only

TABLA = "audit_auditlog"


def _estado() -> dict[str, str]:
    with connection.cursor() as cursor:
        # El nombre de la tabla va como parámetro, no interpolado: aquí sería
        # inofensivo ---es una constante de este fichero--- pero un `f` dentro de
        # un `execute` es justo el patrón que no conviene tener escrito en
        # ningún sitio del que alguien copie luego.
        cursor.execute(
            "SELECT tgname, tgenabled FROM pg_trigger "
            "WHERE tgrelid = %s::regclass AND NOT tgisinternal",
            [TABLA],
        )
        return dict(cursor.fetchall())


@pytest.mark.django_db
def test_con_los_tres_encendidos_dice_que_si():
    """El control. Sin esto, las de abajo pasarían igual si el guardián dijera
    siempre que no."""
    bien, motivo = _check_audit_is_append_only()
    assert bien, motivo
    assert set(GUARDIANES) <= _estado().keys()


@pytest.mark.django_db
def test_un_trigger_apagado_no_cuela():
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {TABLA} DISABLE TRIGGER audit_log_no_update")
    try:
        assert _estado()["audit_log_no_update"] == "D", "no se llegó a apagar"
        bien, motivo = _check_audit_is_append_only()
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {TABLA} ENABLE TRIGGER audit_log_no_update")

    assert not bien, "un trigger apagado no dispara, y el guardián lo daba por bueno"
    assert "apagados" in motivo and "audit_log_no_update" in motivo, motivo


@pytest.mark.django_db
def test_y_uno_que_falta_se_distingue_de_uno_apagado():
    """Son dos averías distintas y el arreglo no es el mismo: una se vuelve a
    encender, la otra hay que recrearla."""
    # Sin restaurarlo a mano: `DROP TRIGGER` es transaccional en Postgres y la
    # prueba corre dentro de una transacción que se deshace al terminar. Y no se
    # puede forzar el rollback desde aquí ---hay un bloque atómico activo--- así
    # que intentarlo solo añade un fallo que no es el que se busca.
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TRIGGER audit_log_no_delete ON {TABLA}")

    bien, motivo = _check_audit_is_append_only()

    assert not bien
    assert "faltan" in motivo and "audit_log_no_delete" in motivo, motivo
