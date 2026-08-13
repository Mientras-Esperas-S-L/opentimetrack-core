"""Send clock-in / clock-out reminders that are due right now.

Meant to run every few minutes from cron or celery-beat. Idempotent: the
`PunchReminder` dedup means running it twice sends nothing twice.

    */5 * * * *  python manage.py send_punch_reminders
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.common.models import tenant_context
from apps.punches.reminders import send_reminders
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Send due clock-in/out reminders across all active companies."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Tax id. Without it, every active company.")

    def handle(self, *args, **options):
        companies = Tenant.objects.filter(is_active=True)
        if options["company"]:
            companies = companies.filter(tax_id=options["company"])

        total = 0
        for company in companies:
            with tenant_context(company.id):
                sent = send_reminders(company)
            if sent:
                self.stdout.write(f"  {company.name}: {sent}")
            total += sent

        self.stdout.write(self.style.SUCCESS(f"{total} reminders sent"))
