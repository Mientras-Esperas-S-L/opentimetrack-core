"""Validate the collective-agreement fichas under `agreements/`.

Meant to run in CI as well as by hand. A ficha that fails here is not a broken
build in the usual sense: it is a figure somebody transcribed wrong, and a
company would have run its rosters against it.

    python manage.py check_agreements
    python manage.py check_agreements --file agreements/es/jardineria-estatal.yaml
    python manage.py check_agreements --strict   # warnings fail too
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.tenants import agreements


class Command(BaseCommand):
    help = "Checks the agreement fichas against the schema and against the Estatuto."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Check one ficha instead of all of them.")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as failures.",
        )

    def handle(self, *args, **options):
        paths = [Path(options["file"])] if options["file"] else None

        try:
            fichas = [agreements.load(p) for p in paths] if paths else agreements.load_all()
        except agreements.FichaError as exc:
            raise CommandError(str(exc)) from exc

        if not fichas:
            self.stdout.write(self.style.WARNING("No fichas found."))
            return

        results = agreements.check_all(fichas)
        errors = warnings = 0

        for ficha in fichas:
            problems = results[ficha.path]
            fatal = [p for p in problems if p.fatal]
            soft = [p for p in problems if not p.fatal]
            errors += len(fatal)
            warnings += len(soft)

            relative = ficha.path.relative_to(agreements.AGREEMENTS_DIR.parent)
            headline = f"{relative}  ({ficha.name})"

            if fatal:
                self.stdout.write(self.style.ERROR(headline))
            elif soft:
                self.stdout.write(self.style.WARNING(headline))
            else:
                self.stdout.write(self.style.SUCCESS(headline))

            for problem in fatal:
                self.stdout.write(f"    error    {problem}")
            for problem in soft:
                self.stdout.write(f"    warning  {problem}")

            # What the ficha carries but the system cannot yet compare. Saying
            # it here beats letting somebody assume 1700 annual hours are being
            # enforced when nothing reads them.
            orphans = [
                k
                for k in ficha.values
                if k not in agreements.APPLICABLE and k not in agreements.QUALIFIERS
            ]
            if orphans:
                self.stdout.write(
                    f"    note     transcribed but not yet applied: {', '.join(sorted(orphans))}"
                )

            # Deferrals are the opposite of a gap and read the same on a screen.
            # "Not in the agreement" means the statutory minimum applies and the
            # company is done; "the agreement sends you elsewhere" means there is
            # another agreement to find, and nobody looks for what they were not
            # told about.
            if ficha.defers:
                self.stdout.write(
                    f"    note     left to a lower-scope agreement: "
                    f"{', '.join(sorted(ficha.defers))}"
                )

        self.stdout.write("")
        summary = f"{len(fichas)} fichas · {errors} errors · {warnings} warnings"

        if errors or (options["strict"] and warnings):
            raise CommandError(summary)

        self.stdout.write(self.style.SUCCESS(summary))
