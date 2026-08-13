"""Drops the IP, device and user agent of old clock events.

Why this exists: the working-time record has to be kept four years, but the
network metadata attached to each event does not serve that purpose. It is kept
to spot anomalies and to look into a disputed event, and once that window has
passed there is no basis for holding it. Keeping data because it might one day
be useful is not a basis.

The clock event itself is never touched. What comes out is the IP address, the
device identifier and the user agent --- the record of who clocked in, when and
how survives intact, and so does its hash.

Events recorded under hash version 1 are the exception: their payload included
the IP, so removing it would break verification for good. They are left alone
and counted, out loud. In a couple of years there will be none left.

Run it daily:

    python manage.py purge_security_metadata
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.punches.models import Punch
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Purge IP, device and user agent from clock events past their retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be purged without changing anything.",
        )
        parser.add_argument(
            "--tenant",
            help="Restrict to one company, by tax id. Default is every active company.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        companies = Tenant.objects.filter(is_active=True)
        if options.get("tenant"):
            companies = companies.filter(tax_id=options["tenant"])

        total_purged = total_stuck = 0

        for company in companies:
            cutoff = timezone.now() - timedelta(days=company.security_metadata_retention_days)

            # objects_all_tenants: this runs from cron, outside any request, so
            # there is no current company in context. The filter below is what
            # keeps it inside the boundary.
            expired = Punch.objects_all_tenants.filter(
                tenant=company, timestamp__lt=cutoff
            ).exclude(ip_address__isnull=True, device_id="", user_agent="", evidence={})

            stuck = expired.filter(hash_version=1).count()
            purgeable = expired.exclude(hash_version=1)
            count = purgeable.count()

            if not dry_run and count:
                purgeable.update(ip_address=None, device_id="", user_agent="", evidence={})
                # Deleting data leaves a trace too. Otherwise the only evidence
                # that something was removed is that it is no longer there.
                record(
                    action=AuditAction.METADATA_PURGED,
                    company=company,
                    target_type="company",
                    target_label=company.name,
                    changes={"purged": count, "before": cutoff.date().isoformat()},
                    note=f"{stuck} conservados por hash v1" if stuck else "",
                )

            total_purged += count
            total_stuck += stuck

            if count or stuck:
                self.stdout.write(
                    f"{company.name}: {count} purged past {cutoff:%Y-%m-%d}"
                    + (f", {stuck} skipped (hash v1 includes the IP)" if stuck else "")
                )

        prefix = "Would purge" if dry_run else "Purged"
        self.stdout.write(self.style.SUCCESS(f"{prefix} {total_purged} events."))
        if total_stuck:
            # Said plainly: a silent skip would read as "everything is purged".
            self.stdout.write(
                self.style.WARNING(
                    f"{total_stuck} events keep their IP because their hash was computed "
                    f"with it (version 1). Removing it would break their verification."
                )
            )
