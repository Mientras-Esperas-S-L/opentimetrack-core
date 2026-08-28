"""Activa la reducción de jornada en la lactancia ya copiada a cada empresa.

El art. 37.4 da **dos formas y las elige quien trabaja**: una hora de ausencia o
media hora de reducción de jornada. El catálogo del país solo traía la primera,
así que la copia de cada empresa nació sin poder reducir y la mitad del derecho
se rechazaba al pedirla.

**Por qué esto toca la copia de la empresa, cuando el principio del catálogo es
justo el contrario.** `seed_leave_types` no pisa nunca lo que hay, y hace bien:
lo que la empresa tiene es lo que su convenio dice, y una corrección nuestra no
puede reescribir en silencio algo que alguien negoció. Aquí no hay nada
negociado: ninguna empresa decidió que la lactancia no pudiera reducir la
jornada, lo heredaron de un dato nuestro que estaba mal. Y activar una
posibilidad no cambia ninguna ausencia ya registrada ---nadie pierde nada, y
quien no quiera usarla no la usa---.

Aun así solo toca las filas que **siguen como se copiaron**. Si una empresa lo
había puesto a mano, esto no se mete.

**`objects_all_tenants` y no `objects`.** Un comando corre sin contexto de
empresa, y el manager normal filtra por ese contexto: la primera versión de esto
contaba cero filas, decía «0 actualizadas · comprobado» y se quedaba tan ancha.
Un backfill que mira donde no es se ve exactamente igual que uno que no tenía
nada que hacer, así que aquí se distinguen las dos cosas a la fuerza.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.absences.models import LeaveType

CODIGO = "es.breastfeeding"


class Command(BaseCommand):
    help = "Deja que la lactancia se pida como reducción de jornada (art. 37.4 ET)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Dice a cuántas afectaría y no toca nada.",
        )

    def handle(self, *args, **options):
        todas = LeaveType.objects_all_tenants.filter(code=CODIGO)
        if not todas.exists():
            # No es «nada que hacer»: es que no estoy viendo el catálogo.
            raise CommandError(
                f"Ni una fila con código {CODIGO}. O el catálogo no está sembrado, "
                "o esto está mirando donde no es."
            )

        filas = todas.filter(can_reduce_the_day=False)
        cuantas = filas.count()

        if options["dry_run"]:
            self.stdout.write(f"{cuantas} de lactancia sin poder reducir la jornada.")
            return

        tocadas = filas.update(can_reduce_the_day=True)
        self.stdout.write(self.style.SUCCESS(f"{tocadas} actualizadas."))

        # La comprobación, en el mismo comando: un backfill que dice «hecho» sin
        # mirar el resultado es exactamente igual de tranquilizador cuando ha
        # funcionado y cuando no.
        quedan = todas.filter(can_reduce_the_day=False).count()
        total = todas.count()
        if quedan:
            self.stdout.write(self.style.ERROR(f"Quedan {quedan} sin actualizar."))
        else:
            self.stdout.write(f"Comprobado: las {total} de lactancia pueden reducir.")
