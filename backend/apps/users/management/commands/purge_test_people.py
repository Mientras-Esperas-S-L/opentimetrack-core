"""Retira del entorno de desarrollo la gente que dejaron las pruebas.

La suite de navegador da de alta personas y, al terminar, las retira con la misma
acción que usaría alguien de la empresa. Pero esa acción **se niega cuando la
persona dejó algo que explicar**, y hace bien: quien tiene una ausencia aprobada
no es un alta equivocada.

Una prueba choca de frente con eso a propósito. `14-decidir-en-bloque` crea gente
nueva cada pasada porque **aprueba** lo que pide, y una ausencia aprobada ya no se
puede cancelar ---el producto responde `already_resolved`---; con gente de la casa
iría llenando el calendario hasta que una pasada tropieza con lo que dejó otra. Así
que deja dos personas irrecuperables por tanda, y eso se acumula: el guard de la
propia suite avisa al pasar de sesenta, y lo que hay que hacer entonces es esto y no
subirle el tope.

No es una función del producto. Es mantenimiento del entorno de demostración, y por
eso vive en un comando y no en la API: en producción esta gente no existe, y si
existiera no habría que borrarla con un patrón.

    python manage.py purge_test_people            # en seco, dice qué haría
    python manage.py purge_test_people --hazlo
"""

from __future__ import annotations

import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.users.erase import rastro_de
from apps.users.models import User

#: La misma marca que reconoce el guard de la suite (`zz-sin-residuos`), y por el
#: mismo motivo escrita entera aquí: si las dos leyeran una lista compartida, un
#: cambio en las pruebas retiraría gente sin que nadie lo revisara.
MARCA = re.compile(
    r"(^|[ .-])(p[0-9a-z]{12,}|p\d{7,})"
    r"|^(prueba|bloque|masiva|idioma|colado|repe|cobertura|extremos)\b",
    re.I,
)

#: Sujetos fijos que la suite reutiliza a propósito. No son sedimento: son el
#: mismo de una tanda a la siguiente, y su correo está escrito en la prueba.
RESPETAR = {"rosa@vacia.local"}


class Command(BaseCommand):
    help = "Retira la gente de prueba dada de baja que no dejó rastro (solo con DEBUG)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hazlo",
            action="store_true",
            help="Borra de verdad. Sin esto solo dice qué haría.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "purge_test_people solo corre con DEBUG. Borra gente por un patrón de correo, "
                "y eso no se hace contra nada real."
            )

        candidatas = [
            persona
            for persona in User.objects.filter(is_active=False)
            if persona.email not in RESPETAR
            and (
                MARCA.search(persona.email or "")
                or MARCA.search(f"{persona.first_name} {persona.last_name}".strip())
            )
        ]

        sin_rastro, con_rastro = [], []
        for persona in candidatas:
            (con_rastro if rastro_de(persona).hay else sin_rastro).append(persona)

        de_baja = User.objects.filter(is_active=False).count()
        self.stdout.write(f"De baja: {de_baja}. Con marca de prueba: {len(candidatas)}.")
        self.stdout.write(f"  Se pueden retirar: {len(sin_rastro)}")
        self.stdout.write(f"  Se quedan porque dejaron rastro: {len(con_rastro)}")

        # Lo que se queda importa más que lo que se va: si crece tanda a tanda,
        # el sedimento seguirá subiendo por mucho que se corra esto.
        for persona in con_rastro[:10]:
            rastro = rastro_de(persona)
            self.stdout.write(f"    · {persona.email}: {rastro.suyo} {rastro.decidido}")
        if len(con_rastro) > 10:
            self.stdout.write(f"    … y {len(con_rastro) - 10} más")

        if not options["hazlo"]:
            self.stdout.write(self.style.WARNING("\nEn seco. Con --hazlo se retiran de verdad."))
            return

        for persona in sin_rastro:
            persona.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRetiradas {len(sin_rastro)}. "
                f"Quedan de baja: {User.objects.filter(is_active=False).count()}."
            )
        )
