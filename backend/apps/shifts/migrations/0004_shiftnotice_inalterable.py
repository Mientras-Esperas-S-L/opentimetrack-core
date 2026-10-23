"""Un aviso de cambio de turno no se reescribe ni se borra.

Lo mismo que el registro de actividad (`audit/0002`), con una diferencia: aquí
hay columnas que **se rellenan después** ---cuándo lo aceptó el correo, cuándo
llegó a la aplicación, cuándo se leyó---. Así que la regla no es «nunca un
UPDATE», sino que cada hora se escribe una vez: de vacía a un valor, y de ahí no
se mueve. Lo demás del aviso ---a quién, quién lo cambió, qué cambió y cuándo se
envió--- no cambia nunca.

Sin esto no es prueba de nada. El art. 6 del RD 723/2026 pide que la empresa
pueda acreditar la transmisión y la recepción, y una hora que la propia empresa
puede retocar con una consola no acredita nada.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION shift_notice_is_write_once() RETURNS trigger AS $$
BEGIN
    IF TG_OP <> 'UPDATE' THEN
        RAISE EXCEPTION 'shifts_shiftnotice is append-only: % is not allowed on this table', TG_OP
            USING HINT = 'A notice is evidence. Send a new one instead.';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.employee_id IS DISTINCT FROM OLD.employee_id
       OR NEW.changed_by_id IS DISTINCT FROM OLD.changed_by_id
       OR NEW.changes::text IS DISTINCT FROM OLD.changes::text
       OR NEW.first_day IS DISTINCT FROM OLD.first_day
       OR NEW.notice_days IS DISTINCT FROM OLD.notice_days
       OR NEW.short_notice IS DISTINCT FROM OLD.short_notice
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
    THEN
        RAISE EXCEPTION 'shifts_shiftnotice: what a notice says cannot be changed';
    END IF;

    IF (OLD.emailed_at IS NOT NULL AND NEW.emailed_at IS DISTINCT FROM OLD.emailed_at)
       OR (OLD.pushed_at IS NOT NULL AND NEW.pushed_at IS DISTINCT FROM OLD.pushed_at)
       OR (OLD.delivered_at IS NOT NULL AND (
            NEW.delivered_at IS DISTINCT FROM OLD.delivered_at
            OR NEW.delivered_via IS DISTINCT FROM OLD.delivered_via))
       OR (OLD.read_at IS NOT NULL AND (
            NEW.read_at IS DISTINCT FROM OLD.read_at
            OR NEW.read_via IS DISTINCT FROM OLD.read_via))
    THEN
        RAISE EXCEPTION 'shifts_shiftnotice: a time already recorded cannot be changed';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER shift_notice_write_once
    BEFORE UPDATE ON shifts_shiftnotice
    FOR EACH ROW EXECUTE FUNCTION shift_notice_is_write_once();

CREATE TRIGGER shift_notice_no_delete
    BEFORE DELETE ON shifts_shiftnotice
    FOR EACH ROW EXECUTE FUNCTION shift_notice_is_write_once();

-- De sentencia, porque TRUNCATE no dispara los de fila.
CREATE TRIGGER shift_notice_no_truncate
    BEFORE TRUNCATE ON shifts_shiftnotice
    FOR EACH STATEMENT EXECUTE FUNCTION shift_notice_is_write_once();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS shift_notice_no_truncate ON shifts_shiftnotice;
DROP TRIGGER IF EXISTS shift_notice_no_delete ON shifts_shiftnotice;
DROP TRIGGER IF EXISTS shift_notice_write_once ON shifts_shiftnotice;
DROP FUNCTION IF EXISTS shift_notice_is_write_once();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("shifts", "0003_shiftnotice"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD),
    ]
