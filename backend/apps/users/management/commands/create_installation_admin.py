"""The first account that can administer the installation.

Everything else about the installation is done from the screen; this one cannot
be, and it is not an oversight: creating it needs a session, and there is no
session until it exists. Chicken and egg.

So this command exists to be run once, right after standing the installation up,
and to be told about in the documentation. The second account and the ones after
it are created from the console, in **Installation**.

    python manage.py create_installation_admin --email you@example.com \\
        --first-name Ada --last-name Lovelace

What makes the account special is that it has **no company**: isolation returns
nothing without one, so it cannot reach anybody's data. It administers the
installation --- companies, their identity provider and their credentials --- and
nothing else.
"""

from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.users.models import User


class Command(BaseCommand):
    help = "Creates the first account that administers the installation."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", required=True)
        parser.add_argument("--last-name", required=True)
        parser.add_argument(
            "--password",
            default="",
            help="Left out, one is generated and printed. It is not stored anywhere else.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if User.objects.filter(email__iexact=email, tenant__isnull=True).exists():
            raise CommandError(
                f"{email} already administers this installation. "
                "Its password is reset from the Installation screen."
            )

        password = options["password"] or f"Ott-{secrets.token_urlsafe(12)}"
        User.objects.create_superuser(
            email=email,
            password=password,
            first_name=options["first_name"],
            last_name=options["last_name"],
            tenant=None,
        )

        self.stdout.write(self.style.SUCCESS("Installation administrator created."))
        self.stdout.write(f"  email:    {email}")
        self.stdout.write(f"  password: {password}")
        self.stdout.write("")
        self.stdout.write(
            "Sign in with it and go to Installation: that is where companies are "
            "created, where their people are told how to sign in, and where the "
            "credential other products use is issued. Any further installation "
            "account is created there too, so this command is only ever needed once."
        )
