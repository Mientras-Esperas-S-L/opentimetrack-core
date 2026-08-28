"""Lleva a cada empresa los permisos del catálogo que aún no tiene.

`seed_leave_types` corre al dar de alta una empresa y **solo añade lo que
falta**: nunca toca lo que hay, porque lo que una empresa tiene es lo que dice su
convenio. Eso lo hace seguro de repetir, y es justo lo que hace falta cuando el
catálogo del país estrena un permiso: sin esto, un tipo nuevo solo lo tendrían
las empresas creadas después.

Sin contexto de empresa, como cualquier comando, así que las empresas salen de
`Tenant.objects` y el sembrado se hace dentro del contexto de cada una ---que es
lo que `LeaveType.objects` mira para saber de quién son las filas que crea---.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.absences.catalogue import seed_leave_types
from apps.common.models import tenant_context
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Añade a cada empresa los permisos del catálogo de su país que le falten."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Dice qué añadiría y no toca nada."
        )

    def handle(self, *args, **options):
        total = 0
        for empresa in Tenant.objects.all().order_by("name"):
            with tenant_context(empresa.id):
                if options["dry_run"]:
                    from apps import legal
                    from apps.absences.models import LeaveType

                    tiene = set(LeaveType.objects.values_list("code", flat=True))
                    faltan = [k.code for k in legal.for_company(empresa).leave_types]
                    cuantos = len([c for c in faltan if c not in tiene])
                else:
                    cuantos = seed_leave_types(empresa)["added"]

            total += cuantos
            if cuantos:
                self.stdout.write(f"  {empresa.name}: {cuantos}")

        verbo = "faltarían" if options["dry_run"] else "añadidos"
        self.stdout.write(self.style.SUCCESS(f"{total} permisos {verbo}."))
