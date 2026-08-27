"""Deletes clock events that have passed the company's retention period.

This is the only place in the product that deletes working time record, so it
is worth being explicit about what it does and does not touch.

**The floor is not a preference.** Art. 34.9 ET requires four years. The company
setting can only be longer, and the setting is not trusted here: it is read and
clamped again. The serializer already refuses anything below four, but a value
written by a shell, an import or a data migration never passed through it, and
this is the code that would do the deleting.

**The cut is a whole day, in the company's zone.** Cutting at an instant four
years ago to the minute would take the morning of a day and leave the afternoon,
and what is left reads as a day somebody worked four hours. `local_today` is
what makes the last kept day the same day for everybody in the company.

**What it does not touch**, and each for its own reason:

- *Leave and contracts*: they are not the working time record and they do not
  live off this period. A holiday taken in 2020 is still what explains a gap in
  a payroll from 2020.
- *Overtime decisions*: art. 35 has its own trail, and the decision is an
  agreement between the company and the person, not a clock event.
- *The audit trail*: it is append-only and it is the evidence that this purge
  happened. It records the count, not the hours, so keeping it does not defeat
  the purge ---checked, and it is the reason this command can exist at all.
- *Corrections still open*: a change nobody resolved is not a closed record. Its
  event is kept, and said out loud. In practice this means a four-year-old
  request that never got an answer, which is worth seeing rather than silently
  deleting.

Run it daily, next to `purge_security_metadata`:

    python manage.py purge_expired_records --dry-run
    python manage.py purge_expired_records
"""

from __future__ import annotations

from datetime import date, datetime, time

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.clock import local_today
from apps.punches.corrections import CorrectionStatus, PunchCorrection
from apps.punches.models import Punch
from apps.tenants.models import Tenant

#: Art. 34.9 ET. Aquí otra vez y no solo en el serializador porque este es el
#: código que borra: si el número de la fila fuera menor por cualquier vía, lo
#: que pasaría es que se borra registro que la ley obliga a tener.
LEGAL_FLOOR_YEARS = 4

#: Sin resolver: nadie ha dicho ni sí ni no. Se conservan.
OPEN_CORRECTIONS = [CorrectionStatus.PENDING, CorrectionStatus.AWAITING_EMPLOYEE]


def first_day_kept(company, today: date | None = None) -> date:
    """El día más antiguo que se conserva, en el calendario de la empresa."""
    today = today or local_today(company)
    years = max(company.record_retention_years, LEGAL_FLOOR_YEARS)
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        # 29 de febrero cayendo en un año que no lo tiene. Se conserva un día
        # más, que es el lado por el que hay que equivocarse.
        return date(today.year - years, 2, 28)


def cutoff_instant(company, today: date | None = None) -> datetime:
    """La medianoche con la que empieza el primer día que se guarda."""
    # `fold=0` por defecto: si esa medianoche fuera ambigua por un cambio de
    # hora ---no ocurre en España, donde el salto es a las 2:00--- se toma la
    # primera de las dos, que conserva más.
    return datetime.combine(first_day_kept(company, today), time.min, tzinfo=company.tzinfo)


class Command(BaseCommand):
    help = "Delete clock events past the company's declared retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without changing anything.",
        )
        parser.add_argument(
            "--tenant",
            help="Restrict to one company, by tax id. Default is every company.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        # Todas, también las que están de baja: el plazo de conservación no deja
        # de correr porque una empresa deje de usar el producto. Mismo
        # razonamiento que `purge_security_metadata`, y por la misma razón ---
        # filtrar por `is_active` deja los datos de quien ya no mira nadie.
        companies = Tenant.objects.all()
        if options.get("tenant"):
            companies = companies.filter(tax_id=options["tenant"])

        total_deleted = total_kept = 0

        for company in companies:
            cutoff = cutoff_instant(company)
            years = max(company.record_retention_years, LEGAL_FLOOR_YEARS)

            # objects_all_tenants: esto corre desde cron, fuera de toda petición,
            # así que no hay empresa en contexto. El filtro por `tenant` es lo
            # que mantiene esto dentro del límite.
            expired = Punch.objects_all_tenants.filter(tenant=company, timestamp__lt=cutoff)

            # Un fichaje con una corrección abierta se queda. Se resuelve como
            # ids y no como subconsulta porque hay que excluirlos y contarlos.
            held = set(
                PunchCorrection.objects_all_tenants.filter(
                    tenant=company, target__in=expired, status__in=OPEN_CORRECTIONS
                ).values_list("target_id", flat=True)
            )
            deletable = expired.exclude(pk__in=held)
            count = deletable.count()
            rows = 0

            if count and not dry_run:
                with transaction.atomic():
                    # Antes que los fichajes, porque `PunchCorrection.target` es
                    # PROTECT y el borrado se plantaría a mitad. Estas son las
                    # ya resueltas: las abiertas retienen su fichaje, arriba.
                    PunchCorrection.objects_all_tenants.filter(
                        tenant=company, target__in=deletable
                    ).delete()
                    # Se recuenta dentro de la transacción: si algo entró entre
                    # el conteo y el borrado, lo que se apunta en el rastro es lo
                    # que de verdad se fue.
                    rows, _por_modelo = Punch.objects_all_tenants.filter(
                        tenant=company, pk__in=list(deletable.values_list("pk", flat=True))
                    ).delete()
                    record(
                        action=AuditAction.RECORD_PURGED,
                        company=company,
                        target_type="company",
                        target_label=company.name,
                        changes={
                            "deleted": count,
                            "kept_from": cutoff.date().isoformat(),
                            "declared_years": company.record_retention_years,
                            "applied_years": years,
                        },
                        note=f"{len(held)} conservados por corrección abierta" if held else "",
                    )

            total_deleted += count
            total_kept += len(held)

            if count or held:
                self.stdout.write(
                    f"{company.name}: {count} events before {cutoff:%Y-%m-%d} "
                    f"({years} years)"
                    + (
                        f", {rows} rows counting what hung off them"
                        if count and not dry_run
                        else ""
                    )
                    + (f", {len(held)} kept (open correction)" if held else "")
                )

        prefix = "Would delete" if dry_run else "Deleted"
        self.stdout.write(self.style.SUCCESS(f"{prefix} {total_deleted} events."))
        if total_kept:
            # Dicho en voz alta: un salto callado se lee como «ya está todo».
            self.stdout.write(
                self.style.WARNING(
                    f"{total_kept} events are kept past their period because a correction "
                    f"on them is still open. Resolve it and they go on the next run."
                )
            )
        if not total_deleted and not total_kept:
            # Y esto también, porque «Deleted 0 events» es indistinguible de un
            # comando que no encontró la tabla, o la empresa, o nada.
            self.stdout.write(f"Nothing past its period, across {companies.count()} companies.")
