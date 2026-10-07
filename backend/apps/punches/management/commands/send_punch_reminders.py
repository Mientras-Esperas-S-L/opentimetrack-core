"""Send clock-in / clock-out reminders that are due right now.

Meant to run every few minutes from cron or celery-beat. Idempotent: the
`PunchReminder` dedup means running it twice sends nothing twice.

    */5 * * * *  python manage.py send_punch_reminders

Quiet when there is nothing to send: what it did goes to the log at INFO, and
only when it sent something. `-v 2` prints the count per company as well.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.common.models import tenant_context
from apps.punches.reminders import send_reminders
from apps.tenants.models import Tenant

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send due clock-in/out reminders across all active companies."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Tax id. Without it, every active company.")

    def handle(self, *args, **options):
        companies = Tenant.objects.filter(is_active=True)
        if options["company"]:
            companies = companies.filter(tax_id=options["company"])

        detalle = options["verbosity"] >= 2
        total = 0
        for company in companies:
            with tenant_context(company.id):
                sent = send_reminders(company)
            if sent and detalle:
                self.stdout.write(f"  {company.name}: {sent}")
            total += sent

        # Por el log y solo si hay algo que contar. Corre cada cinco minutos, y
        # escrito en la salida estándar cada vuelta dejaba 288 líneas al día de
        # «0 reminders sent» ---como WARNING, además: Celery pasa lo que un
        # trabajo escribe en la salida a su log con ese nivel---. Una línea que
        # sale siempre no se lee, y entre ellas se pierde la que sí importa.
        if total:
            log.info("%s reminders sent", total)
        else:
            log.debug("No reminders due")
        if detalle:
            self.stdout.write(self.style.SUCCESS(f"{total} reminders sent"))
