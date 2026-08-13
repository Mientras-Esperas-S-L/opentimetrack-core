"""Vuelve a poner los guardianes del rastro si faltan.

Existe porque **faltaban**. La migración `0002_append_only_trigger` figuraba
aplicada, su función estaba creada, y los tres triggers no estaban en la base:
el rastro se podía editar y borrar sin que nada chistara. Da igual cómo se
perdieron ---una tabla recreada, una restauración, un `migrate --fake`---; lo que
importa es que una garantía que solo vive en una migración se puede evaporar sin
ruido, y que volver a aplicarla no puede obligar a deshacer siete migraciones.

`/api/health/` responde 503 cuando faltan. Esto es lo que se ejecuta después.

    python manage.py ensure_append_only [--dry-run]

Es idempotente: con los tres puestos no toca nada y lo dice.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

#: El mismo SQL que la migración, palabra por palabra. Repetido a propósito: si
#: se importara de allí, editar la migración cambiaría en silencio lo que este
#: comando repone, y una migración ya aplicada no se edita.
FUNCION = """
CREATE OR REPLACE FUNCTION audit_log_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_auditlog is append-only: % is not allowed on this table', TG_OP
        USING HINT = 'Record a new entry instead. Retention is handled by policy.';
END;
$$ LANGUAGE plpgsql;
"""

GUARDIANES = {
    "audit_log_no_update": (
        "CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_auditlog "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();"
    ),
    "audit_log_no_delete": (
        "CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_auditlog "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();"
    ),
    # A nivel de sentencia: TRUNCATE no dispara los triggers de fila, y sin este
    # hay una palabra que vacía la tabla sin que los otros dos se enteren.
    "audit_log_no_truncate": (
        "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_auditlog "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_is_append_only();"
    ),
}


class Command(BaseCommand):
    help = "Recreates the append-only triggers on the audit trail if any are missing."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Say what is missing only.")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write("No es PostgreSQL: aquí no hay triggers que poner.")
            return

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgrelid = 'audit_auditlog'::regclass AND NOT tgisinternal"
            )
            puestos = {fila[0] for fila in cursor.fetchall()}

            faltan = [nombre for nombre in GUARDIANES if nombre not in puestos]
            if not faltan:
                self.stdout.write(self.style.SUCCESS("Los tres están puestos. Nada que hacer."))
                return

            self.stdout.write(self.style.WARNING("Faltan: " + ", ".join(faltan)))
            if options["dry_run"]:
                self.stdout.write("--dry-run: no se ha tocado nada.")
                return

            cursor.execute(FUNCION)
            for nombre in faltan:
                cursor.execute(GUARDIANES[nombre])

        self.stdout.write(
            self.style.SUCCESS(f"Repuestos {len(faltan)}. El rastro vuelve a ser inmutable.")
        )
