"""Brings a year's national and regional holidays into a company.

Same shape as applying a collective agreement ficha: the file ships with the
product, the company decides to take it, and what it writes is the company's own
data from then on.

Two things it deliberately does not do.

**It does not touch the local days.** Those are the two per municipality that
nobody can publish for us, so they are the two nobody can reimport either.
Wiping them on a re-run would destroy the only rows in the table that took
somebody's time.

**It does not guess a region.** A workplace with no region gets the national
days and a warning, because the alternative --- assuming the company's first
region, or the biggest one --- produces a calendar that looks right and gives
people the wrong days off.

Y no se fía del fichero. Lo puede escribir cualquiera ---`HOLIDAYS_DIR` existe
justo para que un despliegue traiga el suyo, transcrito por su asesoría--- y un
error ahí no se ve al leerlo: se ve en marzo, cuando alguien viene a preguntar
por qué le contaron un día de vacaciones que era festivo. Así que se comprueba
antes de escribir nada, y lo que no cuadre para el comando en vez de entrar a
medias.
"""

from __future__ import annotations

import datetime
import pathlib

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.common.models import tenant_context
from apps.tenants.holidays import HolidayScope, PublicHoliday
from apps.tenants.models import Tenant
from apps.users.models import Workplace

#: Configurable for the same reason `AGREEMENTS_DIR` is: a deployment may keep
#: its own calendars --- already checked against the bulletin, or maintained by
#: its adviser --- instead of waiting for us to publish next year.
ROOT = pathlib.Path(settings.HOLIDAYS_DIR)


class Command(BaseCommand):
    help = "Imports the national and regional public holidays of a year into a company."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument(
            "--company",
            help="Tax id. Without it, every company in the country the file is for.",
        )
        parser.add_argument(
            "--country",
            help="Solo el calendario de este país. Sin esto, todos los que haya del año.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Say what would change and write nothing.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        calendars = self._read(year, only=options.get("country"))

        alcanzadas = 0
        for data in calendars:
            if not data.get("verified", False):
                self.stdout.write(
                    self.style.WARNING(
                        f"  El calendario de {year} ({data['country']}) está marcado como no "
                        f"verificado contra el BOE. Revísalo antes de darlo por bueno."
                    )
                )

            companies = Tenant.objects.filter(is_active=True, country=data["country"])
            if options["company"]:
                companies = companies.filter(tax_id=options["company"])

            for company in companies:
                alcanzadas += 1
                self._apply(company, year, data, dry_run=options["dry_run"])

        if not alcanzadas:
            raise CommandError("No matching company.")

    def _read(self, year: int, *, only: str | None = None) -> list[dict]:
        """Los calendarios de ese año, uno por país.

        Antes se quedaba con el primero que encontrara ordenando por nombre de
        directorio, y eso hacía **imposible** importar el segundo: con `es/` y
        `pt/` publicando 2031, pedir 2031 aplicaba el español y las empresas
        portuguesas se quedaban sin festivos, con el comando diciendo que había
        terminado. La cabecera de este módulo presume de que añadir un país es
        un fichero y no un cambio de código, y eso era justo lo que no se
        cumplía.
        """
        calendars = []
        for country_dir in sorted(ROOT.glob("*")):
            if not country_dir.is_dir():
                continue
            path = country_dir / f"{year}.yaml"
            if not path.exists():
                continue
            data = self._validate(path, year)
            if only and data["country"] != only:
                continue
            calendars.append(data)

        if not calendars:
            donde = f" para {only}" if only else ""
            raise CommandError(f"No calendar shipped for {year}{donde}. Look in {ROOT}.")
        return calendars

    def _validate(self, path: pathlib.Path, year: int) -> dict:
        """Lee un calendario y se niega a usarlo si no cuadra.

        Sin esto, un fichero sin `country` reventaba con un `KeyError` pelado, y
        una fecha del año equivocado ---«2025-01-06» dentro del de 2026, que es
        la errata natural al copiar del año anterior--- se escribía tan
        tranquila. Esa además no se puede deshacer reimportando: el comando
        limpia por el rango del año que le pides, así que el día fantasma se
        queda hasta que alguien entre en la base a quitarlo.
        """
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise CommandError(f"{path} no es un YAML válido: {error}") from error

        if not isinstance(data, dict):
            raise CommandError(f"{path} no contiene un calendario.")
        if data.get("year") != year:
            raise CommandError(f"{path} says year {data.get('year')}, not {year}.")
        if not data.get("country"):
            raise CommandError(f"{path} no dice de qué país es (falta `country`).")

        vistos: dict[str, set] = {}
        grupos = [("national", data.get("national") or [])]
        grupos += list((data.get("regions") or {}).items())

        for grupo, entradas in grupos:
            for entrada in entradas:
                dia = (entrada or {}).get("day")
                if not isinstance(dia, datetime.date):
                    raise CommandError(f"{path}: en «{grupo}», {dia!r} no es una fecha.")
                if dia.year != year:
                    raise CommandError(f"{path}: en «{grupo}», {dia} está fuera de {year}.")
                if not (entrada.get("name") or "").strip():
                    raise CommandError(f"{path}: en «{grupo}», {dia} no tiene nombre.")
                # Repetido dentro del mismo grupo, o una comunidad repitiendo un
                # nacional: los dos los tragaba `ignore_conflicts` sin decir
                # nada, y el resumen seguía contando el día que no se escribió.
                if dia in vistos.setdefault(grupo, set()):
                    raise CommandError(f"{path}: en «{grupo}», {dia} está dos veces.")
                vistos[grupo].add(dia)
                if grupo != "national" and dia in vistos.get("national", set()):
                    raise CommandError(f"{path}: «{grupo}» repite el día nacional {dia}.")

        return data

    @transaction.atomic
    def _apply(self, company, year, data, *, dry_run: bool) -> None:
        self.stdout.write(f"\n{company.name}")

        with tenant_context(company.id):
            first = datetime.date(year, 1, 1)
            last = datetime.date(year, 12, 31)

            # Only what this command wrote last time. The local days and
            # anything the company added stay: they are the ones nobody else
            # can put back.
            replacing = PublicHoliday.objects.filter(
                day__gte=first,
                day__lte=last,
                scope__in=[HolidayScope.NATIONAL, HolidayScope.REGIONAL],
            )
            self.stdout.write(f"  se reemplazan {replacing.count()} días importados antes")

            rows = [
                PublicHoliday(
                    tenant=company,
                    day=entry["day"],
                    name=entry["name"],
                    scope=HolidayScope.NATIONAL,
                    note="Irrenunciable (art. 37.2 ET)" if entry.get("irrenunciable") else "",
                )
                for entry in data.get("national") or []
            ]

            sites = list(Workplace.objects.filter(is_active=True))
            regional = data.get("regions") or {}
            for site in sites:
                for entry in regional.get(site.region, []):
                    rows.append(
                        PublicHoliday(
                            tenant=company,
                            day=entry["day"],
                            name=entry["name"],
                            scope=HolidayScope.REGIONAL,
                            workplace=site,
                        )
                    )

            blind = [site.name for site in sites if not site.region]
            if blind:
                self.stdout.write(
                    self.style.WARNING(
                        "  sin comunidad, solo reciben los nacionales: " + ", ".join(blind)
                    )
                )
            if not sites:
                self.stdout.write(
                    self.style.WARNING(
                        "  la empresa no tiene centros de trabajo: sin ellos no hay a qué "
                        "asignar los festivos autonómicos ni los locales"
                    )
                )

            local = PublicHoliday.objects.filter(
                day__gte=first, day__lte=last, scope=HolidayScope.LOCAL
            ).count()
            self.stdout.write(f"  {len(rows)} días a escribir · {local} locales que no se tocan")

            if dry_run:
                self.stdout.write(self.style.WARNING("  --dry-run: no se ha escrito nada"))
                return

            replacing.delete()
            PublicHoliday.objects.bulk_create(rows, ignore_conflicts=True)

            # Contado, no supuesto. `ignore_conflicts` se traga en silencio lo
            # que choque con un día que ya estaba ---uno local, o uno que puso
            # alguien a mano para toda la empresa--- y el resumen anterior
            # cantaba los que iban a escribirse. Un número que se lee y se da
            # por bueno debe salir de mirar, no de contar la lista de entrada.
            escritos = PublicHoliday.objects.filter(
                day__gte=first,
                day__lte=last,
                scope__in=[HolidayScope.NATIONAL, HolidayScope.REGIONAL],
            ).count()
            if escritos != len(rows):
                self.stdout.write(
                    self.style.WARNING(
                        f"  {len(rows) - escritos} no se escribieron: ya había otro día "
                        f"puesto en esa fecha, y el que estaba manda"
                    )
                )
            self.stdout.write(self.style.SUCCESS(f"  hecho · {escritos} escritos"))
