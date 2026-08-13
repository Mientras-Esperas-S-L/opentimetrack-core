"""Print a VAPID key pair for this deployment's browser notifications.

Web Push needs a key pair that identifies *this server* to the browser vendors.
It is generated once, per deployment, and put in the environment:

    python manage.py vapid_keys

Nothing is written to disk or to the database on purpose: the private key is a
secret, and a command that quietly saved one somewhere would be the kind of
help that ends up in a git repository.
"""

from __future__ import annotations

import base64

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate the VAPID key pair for web push, to paste into the environment."

    def handle(self, *args, **options):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        private = ec.generate_private_key(ec.SECP256R1())
        public = private.public_key()

        # Both halves travel base64url without padding: that is what the Push
        # API expects in `applicationServerKey`, and what pywebpush reads back.
        private_bytes = private.private_numbers().private_value.to_bytes(32, "big")
        public_bytes = public.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

        self.stdout.write("# Añade esto al .env del despliegue:")
        self.stdout.write(f"WEBPUSH_PUBLIC_KEY={_b64(public_bytes)}")
        self.stdout.write(f"WEBPUSH_PRIVATE_KEY={_b64(private_bytes)}")
        self.stdout.write("WEBPUSH_SUBJECT=mailto:soporte@tu-dominio.example")
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "La clave privada es un secreto. Si cambia, todos los navegadores "
                "suscritos dejan de recibir avisos y tienen que volver a suscribirse."
            )
        )


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
