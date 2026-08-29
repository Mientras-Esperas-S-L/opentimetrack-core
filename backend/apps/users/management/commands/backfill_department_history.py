"""Estrena el historial de adscripción con lo que hay hoy.

Cada persona con departamento recibe **una** asignación abierta y **sin fecha de
inicio**. Eso no es un descuido: del pasado no hay dato ---nadie guardó los
cambios anteriores--- y ponerle la fecha del contrato diría que lleva en ese
departamento desde que entró, que no consta. «Sin fecha» significa «no consta
desde cuándo» y cuenta para cualquier periodo, o sea que el producto se comporta
como antes hasta que alguien cambie de departamento.

**Cada modelo con su manager, y no son iguales.** `DepartmentAssignment` es de
empresa, así que ahí va `objects_all_tenants`: el manager normal filtra por el
contexto y un comando no tiene ninguno ---otro backfill contó cero filas y dijo
que estaba todo hecho---. `User` es al revés: su manager **no** filtra por
empresa, y va `objects` a secas. Suponer que los dos se comportan igual habría
fallado en uno de los dos sentidos.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.users.models import DepartmentAssignment, User


class Command(BaseCommand):
    help = "Crea la asignación de departamento vigente para quien no tenga historial."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Dice cuántas y no toca nada.")

    def handle(self, *args, **options):
        con_historia = set(
            DepartmentAssignment.objects_all_tenants.values_list("employee_id", flat=True)
        )
        faltan = [
            quien
            for quien in User.objects.filter(department__isnull=False)
            if quien.id not in con_historia
        ]

        if options["dry_run"]:
            self.stdout.write(f"{len(faltan)} personas sin historial de adscripción.")
            return

        DepartmentAssignment.objects_all_tenants.bulk_create(
            [
                DepartmentAssignment(
                    tenant_id=quien.tenant_id,
                    employee=quien,
                    department_id=quien.department_id,
                    starts_on=None,
                )
                for quien in faltan
            ]
        )
        self.stdout.write(self.style.SUCCESS(f"{len(faltan)} asignaciones creadas."))

        # La comprobación, en el mismo comando: un backfill que dice «hecho» sin
        # mirar el resultado tranquiliza igual cuando ha funcionado y cuando no.
        quedan = [
            quien
            for quien in User.objects.filter(department__isnull=False)
            if not DepartmentAssignment.objects_all_tenants.filter(employee=quien).exists()
        ]
        if quedan:
            self.stdout.write(self.style.ERROR(f"Quedan {len(quedan)} sin historial."))
        else:
            self.stdout.write("Comprobado: nadie con departamento se queda sin su asignación.")
