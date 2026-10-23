"""Avisa de los cambios de turno que llevan un rato quietos.

Corre cada pocos minutos desde cron o celery-beat, igual que los recordatorios
de fichar. Idempotente: lo que se avisa sale de la cola, así que ejecutarlo dos
veces no avisa dos veces.

    */5 * * * *  python manage.py send_shift_notices

Ver `apps.shifts.notices.publicar` para por qué hay espera.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.common.models import tenant_context
from apps.shifts.notices import publicar
from apps.tenants.models import Tenant

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send the shift change notices that have been still long enough."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Tax id. Without it, every active company.")

    def handle(self, *args, **options):
        companies = Tenant.objects.filter(is_active=True)
        if options["company"]:
            companies = companies.filter(tax_id=options["company"])

        total = 0
        for company in companies:
            with tenant_context(company.id):
                total += len(publicar(company))

        # Por el log y solo si hay algo que contar, como los recordatorios: una
        # línea cada cinco minutos diciendo «0» no la lee nadie.
        if total:
            log.info("%s shift change notices sent", total)
