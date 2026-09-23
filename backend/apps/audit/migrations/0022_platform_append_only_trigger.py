"""The installation's trail is append-only in the database too.

The same three triggers as `audit_auditlog` (see 0002), for the same reason: a
trail the account it describes can edit is not evidence. Its own function, so
the message names the table that refused.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION platform_audit_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_platformauditentry is append-only: % is not allowed on this table', TG_OP
        USING HINT = 'Record a new entry instead.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER platform_audit_no_update
    BEFORE UPDATE ON audit_platformauditentry
    FOR EACH ROW EXECUTE FUNCTION platform_audit_is_append_only();

CREATE TRIGGER platform_audit_no_delete
    BEFORE DELETE ON audit_platformauditentry
    FOR EACH ROW EXECUTE FUNCTION platform_audit_is_append_only();

CREATE TRIGGER platform_audit_no_truncate
    BEFORE TRUNCATE ON audit_platformauditentry
    FOR EACH STATEMENT EXECUTE FUNCTION platform_audit_is_append_only();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS platform_audit_no_truncate ON audit_platformauditentry;
DROP TRIGGER IF EXISTS platform_audit_no_delete ON audit_platformauditentry;
DROP TRIGGER IF EXISTS platform_audit_no_update ON audit_platformauditentry;
DROP FUNCTION IF EXISTS platform_audit_is_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0021_platformauditentry"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD),
    ]
