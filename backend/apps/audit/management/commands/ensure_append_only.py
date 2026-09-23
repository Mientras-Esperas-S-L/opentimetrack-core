"""Vuelve a poner los guardianes del rastro si faltan.

Existe porque **faltaban**. La migración `0002_append_only_trigger` figuraba
aplicada, su función estaba creada, y los tres triggers no estaban en la base:
el rastro se podía editar y borrar sin que nada chistara. Da igual cómo se
perdieron ---una tabla recreada, una restauración, un `migrate --fake`---; lo que
importa es que una garantía que solo vive en una migración se puede evaporar sin
ruido, y que volver a aplicarla no puede obligar a deshacer siete migraciones.

`/api/health/` responde 503 cuando faltan. Esto es lo que se ejecuta después.

    python manage.py ensure_append_only [--dry-run]

Es idempotente: con todos puestos no toca nada y lo dice. Cubre las dos tablas
inmutables: el rastro de cada empresa y el de la instalación.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

#: El mismo SQL que las migraciones (`0002` y `0022`), palabra por palabra.
#: Repetido a propósito: si se importara de allí, editar una migración cambiaría en
#: silencio lo que este comando repone, y una migración ya aplicada no se edita.
TABLAS = {
    "audit_auditlog": (
        """
CREATE OR REPLACE FUNCTION audit_log_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_auditlog is append-only: % is not allowed on this table', TG_OP
        USING HINT = 'Record a new entry instead. Retention is handled by policy.';
END;
$$ LANGUAGE plpgsql;
""",
        {
            "audit_log_no_update": (
                "CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_auditlog "
                "FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();"
            ),
            "audit_log_no_delete": (
                "CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_auditlog "
                "FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();"
            ),
            # A nivel de sentencia: TRUNCATE no dispara los triggers de fila, y sin
            # este hay una palabra que vacía la tabla sin que los otros dos se enteren.
            "audit_log_no_truncate": (
                "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_auditlog "
                "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_is_append_only();"
            ),
        },
    ),
    "audit_platformauditentry": (
        """
CREATE OR REPLACE FUNCTION platform_audit_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_platformauditentry is append-only: % is not allowed on this table', TG_OP
        USING HINT = 'Record a new entry instead.';
END;
$$ LANGUAGE plpgsql;
""",
        {
            "platform_audit_no_update": (
                "CREATE TRIGGER platform_audit_no_update BEFORE UPDATE "
                "ON audit_platformauditentry "
                "FOR EACH ROW EXECUTE FUNCTION platform_audit_is_append_only();"
            ),
            "platform_audit_no_delete": (
                "CREATE TRIGGER platform_audit_no_delete BEFORE DELETE "
                "ON audit_platformauditentry "
                "FOR EACH ROW EXECUTE FUNCTION platform_audit_is_append_only();"
            ),
            "platform_audit_no_truncate": (
                "CREATE TRIGGER platform_audit_no_truncate BEFORE TRUNCATE "
                "ON audit_platformauditentry "
                "FOR EACH STATEMENT EXECUTE FUNCTION platform_audit_is_append_only();"
            ),
        },
    ),
}

#: Los del rastro de las empresas, con su nombre de siempre.
GUARDIANES = TABLAS["audit_auditlog"][1]


class Command(BaseCommand):
    help = "Recreates the append-only triggers on the audit trails if any are missing."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Say what is missing only.")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write("No es PostgreSQL: aquí no hay triggers que poner.")
            return

        repuestos = 0
        with connection.cursor() as cursor:
            for tabla, (funcion, guardianes) in TABLAS.items():
                cursor.execute(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = %s::regclass AND NOT tgisinternal",
                    [tabla],
                )
                puestos = {fila[0] for fila in cursor.fetchall()}
                faltan = [nombre for nombre in guardianes if nombre not in puestos]
                if not faltan:
                    continue

                self.stdout.write(self.style.WARNING(f"{tabla}: faltan " + ", ".join(faltan)))
                if options["dry_run"]:
                    continue
                cursor.execute(funcion)
                for nombre in faltan:
                    cursor.execute(guardianes[nombre])
                repuestos += len(faltan)

        if options["dry_run"]:
            self.stdout.write("--dry-run: no se ha tocado nada.")
        elif repuestos:
            self.stdout.write(
                self.style.SUCCESS(f"Repuestos {repuestos}. Los rastros vuelven a ser inmutables.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Todos están puestos. Nada que hacer."))
