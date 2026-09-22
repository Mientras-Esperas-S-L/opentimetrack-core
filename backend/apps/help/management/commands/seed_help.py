"""Command: python manage.py seed_help

Loads the help articles from `apps/help/content/*.json` into the database.

**Why the text lives in JSON and not in this file.** It is content, not code: a person
writing or correcting an article should not have to read Python to do it, and a
translation is a new file rather than a new branch of an `if`. It also keeps the
formatter out of the way --- prose does not wrap at a hundred columns, and forcing it
to turns every edit into a reflow.

**Why it is seeded at all, instead of typed into a screen.** An article that lives in
the repository is reviewed in the pull request like any other change, ships with the
deployment, can be put back into a fresh installation and survives a restore. Whatever
gets edited by hand later sits on top of that; this is the original.

**The slug is the screen's route.** The drawer takes the topic from the last segment
of the path --- `/panel/personas` asks for `personas`, the root asks for `fichar` ---
so an article named after anything else would never be found by the `?` button.

Idempotent: `update_or_create` on sections and articles, blocks recreated.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.help.models import HelpArticle, HelpBlock, HelpSection

CONTENT = Path(__file__).resolve().parents[2] / "content"


class Command(BaseCommand):
    help = "Loads the help content shipped with the code."

    def add_arguments(self, parser):
        parser.add_argument(
            "--language",
            default="",
            help="Only this language. By default, every file in content/.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        pedido = options["language"]
        ficheros = sorted(CONTENT.glob(f"{pedido or '*'}.json"))
        if not ficheros:
            self.stdout.write(self.style.WARNING(f"No content in {CONTENT}."))
            return

        total = 0
        for fichero in ficheros:
            datos = json.loads(fichero.read_text(encoding="utf-8"))
            total += self._load(datos)

        self.stdout.write(self.style.SUCCESS(f"\n{total} help article(s) seeded."))

    def _load(self, datos) -> int:
        language = datos["language"]
        secciones = {}
        for seccion in datos["sections"]:
            fila, _ = HelpSection.objects.update_or_create(
                slug=seccion["slug"],
                language=language,
                defaults={
                    "title": seccion["title"],
                    "order": seccion.get("order", 0),
                    "icon": seccion.get("icon", ""),
                    "is_active": True,
                },
            )
            secciones[seccion["slug"]] = fila

        for articulo in datos["articles"]:
            fila, created = HelpArticle.objects.update_or_create(
                slug=articulo["slug"],
                language=language,
                defaults={
                    "section": secciones[articulo["section"]],
                    "title": articulo["title"],
                    "summary": articulo.get("summary", ""),
                    "is_published": True,
                },
            )
            # Blocks are recreated whole, so re-running leaves no remains of an
            # earlier version of the text.
            HelpBlock.objects.filter(article=fila).delete()
            HelpBlock.objects.bulk_create(
                [
                    HelpBlock(article=fila, order=i, kind=b["kind"], data=b["data"])
                    for i, b in enumerate(articulo["blocks"], start=1)
                ]
            )
            self.stdout.write(
                f'  [{language}] "{fila.slug}" {"created" if created else "updated"}.'
            )

        return len(datos["articles"])
