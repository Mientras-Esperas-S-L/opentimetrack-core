"""Makes append-only true in the database, not only in the code.

ADR-0003 called the database side "recommended in production". It is not
recommended, it is the whole point: overriding `save()` and `delete()` stops
honest mistakes and nothing else. A bug, a management command, a migration, or
an administrator with a psql prompt goes straight past Python.

An audit trail that can be edited by whoever it incriminates is not evidence.

`TRUNCATE` is included. Without it there is a one-word way to empty the table
that neither the model nor an UPDATE/DELETE trigger would notice.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION audit_log_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_auditlog is append-only: % is not allowed on this table', TG_OP
        USING HINT = 'Record a new entry instead. Retention is handled by policy.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();

CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();

-- Statement-level, because TRUNCATE does not fire row triggers.
CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_auditlog
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_is_append_only();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_auditlog;
DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_auditlog;
DROP TRIGGER IF EXISTS audit_log_no_update ON audit_auditlog;
DROP FUNCTION IF EXISTS audit_log_is_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD),
    ]
