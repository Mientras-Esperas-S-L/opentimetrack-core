"""Version the integrity hash so its payload can change without rewriting it.

Events already stored were hashed with the IP address in the payload. Rewriting
those hashes to match the new payload would be indistinguishable from tampering
with the record, so they stay as they are and keep verifying as version 1.
Everything recorded from here on uses version 2.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("punches", "0002_punchcorrection"),
    ]

    operations = [
        # Backfills existing rows with 1: they were hashed the old way.
        migrations.AddField(
            model_name="punch",
            name="hash_version",
            field=models.PositiveSmallIntegerField(
                default=1, editable=False, verbose_name="hash version"
            ),
        ),
        # And new rows get 2, which is what the model declares.
        migrations.AlterField(
            model_name="punch",
            name="hash_version",
            field=models.PositiveSmallIntegerField(
                default=2, editable=False, verbose_name="hash version"
            ),
        ),
    ]
