"""Sample data for local development.

Refuses to run outside DEBUG. The passwords here are written in the open on
purpose --- they are for a throwaway database --- and that is exactly why this
must never execute against anything real.

## What it builds, and why this much

A gardening company of fourteen people, six weeks of history, and every
working-time situation the product claims to handle. Not for volume: for
**coverage**. Three people and a clean fortnight make every screen look
finished, and the cases that break things never appear.

So the roster is deliberately imperfect and the payroll is deliberately mixed:

* forty hours, twenty-five hours, a reduced day, a training contract, and
  somebody with no agreed figure at all --- all in the same company, because
  that is how companies are;
* an annual figure, because Spanish agreements often set the year and not the
  week (the state gardening one says 1700 hours);
* a fixed-term contract that has already ended and a permanent-seasonal one;
* somebody under eighteen, so the floors that only apply to them fire;
* a week that breaches the daily rest, one over the weekly maximum, and one
  over what was contracted --- which are three different findings;
* a correction waiting for the person, one they disagreed with, and one applied
  without agreement, so the art. 4.b screens have all three states;
* absences in every state, including one that clashes with the roster.

If a screen looks wrong with this data, it is wrong.
"""

from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import Absence, AbsenceStatus, AbsenceType, LeaveType
from apps.common.models import tenant_context
from apps.punches.corrections import (
    apply_without_agreement,
    dispute_correction,
    propose_correction,
    request_correction,
)
from apps.punches.models import HoursNature, Punch, PunchInterval, PunchSource, PunchType, WorkMode
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import (
    Department,
    HoursPeriod,
    RemoteWorkAgreement,
    Role,
    User,
    WorkingTimeRegime,
    Workplace,
)

# Sample data, DEBUG only. `random` is fine here and bandit is told so once:
# these are demo timings, not anything anybody has to be unable to predict ---
# in fact the seed is fixed on purpose so two runs match.
PASSWORD = "demo-password-2026"  # noqa: S105

TAX_ID = "B00000001"

#: La empresa de al lado. Existe para una sola cosa y no es decorativa: sin una
#: segunda empresa no se puede *demostrar* que el aislamiento funciona, y una
#: promesa que no se puede enseñar no vale nada delante de un cliente. Las
#: pruebas de interfaz la usan para intentar colarse con identificadores suyos.
NEIGHBOUR_TAX_ID = "B00000002"

#: Fixed so two runs produce the same company. A demo that differs every time
#: is one where "it looked different yesterday" is never a real observation.
SEED = 20260812


#: Quién trabaja desde casa y qué días de la semana, para que la demostración
#: enseñe la Ley 10/2021 ---que hasta ahora no salía por ninguna parte: los mil
#: fichajes eran presenciales sin excepción---.
#:
#: Los dos casos que hay que ver son distintos a propósito. Ana teletrabaja dos
#: días de cinco, el 40 %, **con acuerdo firmado antes de empezar**: la ley se
#: aplica y está cumplida. Luis, tres de cinco, el 60 % y **sin acuerdo**: la ley
#: se aplica y no está cumplida, que es justo lo que la revisión del cuadrante
#: tiene que sacar.
DESDE_CASA = {
    ("admin", 1): WorkMode.REMOTE,  # Ana, martes
    ("admin", 3): WorkMode.REMOTE,  # y jueves
    ("manager", 0): WorkMode.REMOTE,  # Luis, lunes
    ("manager", 2): WorkMode.REMOTE,  # miércoles
    ("manager", 4): WorkMode.REMOTE,  # y viernes
}


class Command(BaseCommand):
    help = "Creates a demo company with people, a roster, history and things to decide."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the demo company first and build it again.",
        )
        parser.add_argument(
            "--weeks",
            type=int,
            default=6,
            help="Weeks of history to generate. Default 6.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG enabled. It writes known passwords.")

        random.seed(SEED)

        if options["reset"]:
            self._wipe()

        if Tenant.objects.filter(tax_id=TAX_ID).exists():
            raise CommandError("The demo company already exists. Use --reset to rebuild it.")

        company = Tenant.objects.create(
            name="Jardines Demo S.L.",
            tax_id=TAX_ID,
            country="ES",
            time_zone="Europe/Madrid",
            annual_leave_days=23,
        )

        with tenant_context(company.id):
            rules = WorkingTimeRules.for_company(company)
            sites = self._workplaces(company)
            departments = self._departments(company)
            people = self._people(company, departments, sites)
            patterns = self._patterns(company)
            self._roster(company, people, patterns, weeks=options["weeks"])
            self._history(company, people, weeks=options["weeks"])
            seed_leave_types(company)
            self._absences(company, people)
            self._corrections(company, people)

        self._neighbour()
        self._report(company, people, rules)

    def _neighbour(self):
        """Una segunda empresa, mínima, para que el aislamiento sea comprobable.

        Dos personas y un departamento: lo justo para que otra empresa tenga
        identificadores que alguien de la primera pueda intentar usar. Todo lo
        demás sobra --- no es una demo, es un vecino.
        """
        if Tenant.objects.filter(tax_id=NEIGHBOUR_TAX_ID).exists():
            return

        neighbour = Tenant.objects.create(
            name="Vecina S.L.",
            tax_id=NEIGHBOUR_TAX_ID,
            country="ES",
            time_zone="Europe/Madrid",
        )
        with tenant_context(neighbour.id):
            admin = User.objects.create_user(
                email="admin@vecina.local",
                password=PASSWORD,
                tenant=neighbour,
                first_name="Elsa",
                last_name="Vecina",
                role=Role.ADMIN,
            )
            User.objects.create_user(
                email="operario@vecina.local",
                password=PASSWORD,
                tenant=neighbour,
                first_name="Tomás",
                last_name="Vecino",
            )
            Department.objects.create(tenant=neighbour, name="Vecina · Operaciones")
        return admin

    # ------------------------------------------------------------------ people

    def _workplaces(self, company):
        """Two, and the second one is the point.

        A company with an office in Cádiz and another in Las Palmas is one hour
        apart inside the same payroll, and one hour is the difference between a
        punch landing on Monday and on Sunday. Without a second site the zone
        field would be a form nobody could see the use of.
        """
        return {
            key: Workplace.objects.create(
                tenant=company,
                name=name,
                address=address,
                municipality=municipality,
                municipality_code=code,
                region=region,
                time_zone=zone,
            )
            for key, name, address, municipality, code, region, zone in [
                (
                    "main",
                    "Nave de Jerez",
                    "Polígono El Portal, nave 14",
                    "Jerez de la Frontera",
                    "11020",
                    "ES-AN",
                    "",
                ),
                (
                    "canarias",
                    "Delegación de Las Palmas",
                    "C/ León y Castillo 22",
                    "Las Palmas de Gran Canaria",
                    "35016",
                    "ES-CN",
                    "Atlantic/Canary",
                ),
            ]
        }

    def _departments(self, company):
        return {
            key: Department.objects.create(tenant=company, name=name)
            for key, name in [
                ("gardening", "Jardinería"),
                ("works", "Obras y mantenimiento"),
                ("climbing", "Poda en altura"),
                ("office", "Administración"),
            ]
        }

    def _people(self, company, departments, sites):
        """Fourteen, chosen so that every rule in the product has somebody it
        applies to and somebody it does not."""
        today = timezone.localdate()
        gardening = departments["gardening"]
        works = departments["works"]
        climbing = departments["climbing"]
        office = departments["office"]

        # (key, email, first, last, role, dept, staff, regime, hours, period, extra)
        roster = [
            (
                "admin",
                "admin@demo.local",
                "Ana",
                "García",
                Role.ADMIN,
                office,
                "EMP-0001",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {},
            ),
            (
                "manager",
                "manager@demo.local",
                "Luis",
                "Ferrer",
                Role.MANAGER,
                works,
                "EMP-0002",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"is_worker_representative": False},
            ),
            (
                "worker",
                "operario@demo.local",
                "Marta",
                "Ruiz",
                Role.EMPLOYEE,
                gardening,
                "EMP-0003",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"contracted_schedule": "L-V 07:00-15:00"},
            ),
            # The one the art. 4.b notice needs somebody to be.
            (
                "delegate",
                "delegada@demo.local",
                "Rocío",
                "Ibáñez",
                Role.EMPLOYEE,
                gardening,
                "EMP-0004",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"is_worker_representative": True, "contracted_schedule": "L-V 07:00-15:00"},
            ),
            # Twenty-five hours: the case that used to pass unnoticed, because
            # twenty-five is under forty.
            (
                "parttime",
                "parcial@demo.local",
                "Jose",
                "Almenara",
                Role.EMPLOYEE,
                gardening,
                "EMP-0005",
                WorkingTimeRegime.PART_TIME,
                25,
                HoursPeriod.WEEK,
                {"contracted_schedule": "L-V 08:00-13:00"},
            ),
            (
                "parttime2",
                "parcial2@demo.local",
                "Nuria",
                "Cobos",
                Role.EMPLOYEE,
                office,
                "EMP-0006",
                WorkingTimeRegime.PART_TIME,
                20,
                HoursPeriod.WEEK,
                {"contracted_schedule": "L-J 09:00-14:00"},
            ),
            # A reduced day is not part-time work, and the product has to know
            # the difference: overtime is lawful here and not there.
            (
                "reduced",
                "reducida@demo.local",
                "Elena",
                "Prats",
                Role.EMPLOYEE,
                office,
                "EMP-0007",
                WorkingTimeRegime.REDUCED,
                # Su contrato es de jornada completa: lo que está reducido es la
                # jornada, y eso vive en una solicitud con su fracción y sus
                # fechas ---ver `_suspensions`---. Antes ponía 30 aquí y «(guarda
                # legal)» en el horario, y así la reducción no se acababa nunca.
                40,
                HoursPeriod.WEEK,
                {"contracted_schedule": "L-V 09:00-17:00"},
            ),
            # The gardening agreement sets 1700 hours a year and no weekly
            # figure at all.
            (
                "annual",
                "anual@demo.local",
                "Paco",
                "Trillo",
                Role.EMPLOYEE,
                climbing,
                "EMP-0008",
                WorkingTimeRegime.FULL_TIME,
                1700,
                HoursPeriod.YEAR,
                {"contracted_schedule": "Jornada anual, distribución irregular"},
            ),
            # Fully flexible: no roster, no expected day, and until now no
            # limits check of any kind.
            (
                "flexible",
                "flexible@demo.local",
                "Iván",
                "Sedano",
                Role.EMPLOYEE,
                office,
                "EMP-0009",
                WorkingTimeRegime.VARIABLE,
                None,
                HoursPeriod.WEEK,
                {"contracted_schedule": "Horario flexible, sin franja fija"},
            ),
            (
                "oncall",
                "refuerzo@demo.local",
                "Sara",
                "Quiles",
                Role.EMPLOYEE,
                works,
                "EMP-0010",
                WorkingTimeRegime.VARIABLE,
                None,
                HoursPeriod.WEEK,
                {},
            ),
            # Under eighteen: eight hours a day, thirty minutes' break from four
            # and a half, no nights, no overtime.
            (
                "minor",
                "aprendiz@demo.local",
                "Adrián",
                "Nieto",
                Role.EMPLOYEE,
                gardening,
                "EMP-0011",
                # En alternancia, concreto: el art. 11.2.b le pone un tope de
                # trabajo efectivo ---65 % de la jornada máxima el primer año---
                # que el otro formativo, el de práctica profesional, no tiene.
                # Veinte horas sobre cuarenta son el 50 %, así que va holgado, y
                # la fecha de contrato es lo que decide si el tope es el 65 o el
                # 85.
                WorkingTimeRegime.TRAINING_ALTERNATING,
                20,
                HoursPeriod.WEEK,
                {
                    "date_of_birth": today - timedelta(days=365 * 17 + 100),
                    "contract_start": today - timedelta(days=200),
                },
            ),
            # Fixed-term, already finished: rostered anyway, on purpose.
            (
                "expired",
                "temporal@demo.local",
                "Cristina",
                "Vega",
                Role.EMPLOYEE,
                gardening,
                "EMP-0012",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {
                    "contract_start": today - timedelta(days=180),
                    "contract_end": today - timedelta(days=7),
                },
            ),
            # El par del art. 12.6 y 12.7: quien se jubila parcialmente y quien
            # le releva. Van juntos porque la ley los compara: la jornada del
            # relevo tiene que cubrir al menos lo que el otro deja de trabajar.
            (
                "retiring",
                "jubilacion@demo.local",
                "Manuel",
                "Cortés",
                Role.EMPLOYEE,
                works,
                "EMP-0018",
                WorkingTimeRegime.FULL_TIME,
                40,
                HoursPeriod.WEEK,
                {"contract_start": today - timedelta(days=365 * 12)},
            ),
            (
                "relief",
                "relevo@demo.local",
                "Nerea",
                "Pardo",
                Role.EMPLOYEE,
                works,
                "EMP-0019",
                WorkingTimeRegime.PART_TIME,
                # Veinte horas: exactamente lo que Manuel deja de trabajar con
                # su reducción del 50 %. El mínimo del art. 12.7, y por eso
                # cumple sin margen --- que es como se firman de verdad.
                20,
                HoursPeriod.WEEK,
                {"contract_start": today - timedelta(days=60)},
            ),
            # Permanent-seasonal.
            (
                "seasonal",
                "temporada@demo.local",
                "Yolanda",
                "Serra",
                Role.EMPLOYEE,
                gardening,
                "EMP-0013",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"seasonal": True, "contract_start": today - timedelta(days=400)},
            ),
            # A rotating three-shift team. Two people so the rotation has
            # somebody on each side of it, which is what makes the changeover
            # visible in the roster --- and the changeover is the case that used
            # to be reported as a breach on every single rotation.
            (
                "rotating",
                "turnos@demo.local",
                "Nerea",
                "Colomer",
                Role.EMPLOYEE,
                works,
                "EMP-0015",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"rotating_shifts": True, "contracted_schedule": "Turno rotatorio M/T/N"},
            ),
            # The one the company has answered about. Hired for nights, so the
            # status is a fact of the contract and not something the roster has
            # to guess at --- and having answered, the eight-hour average is a
            # limit rather than a question.
            (
                "night",
                "noches@demo.local",
                "Óscar",
                "Vidal",
                Role.EMPLOYEE,
                works,
                "EMP-0016",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {
                    "night_worker": "YES",
                    "rotating_shifts": True,
                    "contracted_schedule": "Noches 22:00-06:00",
                },
            ),
            # Permanent nights and nobody ever answered the question. The
            # commonest way this goes wrong: the status is never recorded, so
            # the eight-hour average is never applied and the health assessment
            # art. 36.4 requires is never booked.
            (
                "guard",
                "vigilante@demo.local",
                "Álvaro",
                "Pina",
                Role.EMPLOYEE,
                works,
                "EMP-0017",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"contracted_schedule": "Noches 22:00-06:00"},
            ),
            # Signs in through an identity provider: no password link for them.
            (
                "federated",
                "sso@demo.local",
                "Hugo",
                "Bermejo",
                Role.EMPLOYEE,
                works,
                "EMP-0014",
                WorkingTimeRegime.FULL_TIME,
                None,
                HoursPeriod.WEEK,
                {"oidc_sub": "okta|demo-hugo"},
            ),
        ]

        made = {}
        for key, email, first, last, role, dept, staff, regime, hours, period, extra in roster:
            made[key] = User.objects.create_user(
                email=email,
                password=PASSWORD,
                tenant=company,
                first_name=first,
                last_name=last,
                role=role,
                department=dept,
                employee_id=staff,
                workplace=sites["canarias"] if key == "federated" else sites["main"],
                regime=regime,
                contracted_hours=hours,
                contracted_period=period,
                **extra,
            )

        # El vínculo del relevo, después del bucle: apunta a otra persona de la
        # misma tanda y no existe hasta que las dos están creadas.
        made["relief"].relieves = made["retiring"]
        made["relief"].save(update_fields=["relieves"])
        return made

    # ------------------------------------------------------------------ roster

    def _patterns(self, company):
        return {
            key: ShiftPattern.objects.create(
                tenant=company, name=name, segments=segments, colour=colour
            )
            for key, name, segments, colour in [
                ("morning", "Mañana", [{"start": "07:00", "end": "15:00"}], "#1b5e4a"),
                (
                    "split",
                    "Partida",
                    [
                        {"start": "08:00", "end": "13:00"},
                        {"start": "15:00", "end": "18:00"},
                    ],
                    "#8a6d3b",
                ),
                ("short", "Reducida", [{"start": "08:00", "end": "13:00"}], "#4a6f8a"),
                ("long", "Refuerzo", [{"start": "07:00", "end": "17:00"}], "#8a3b3b"),
                # The three a rotating team turns through.
                ("t_morning", "Turno de mañana", [{"start": "06:00", "end": "14:00"}], "#2d6a4f"),
                ("t_evening", "Turno de tarde", [{"start": "14:00", "end": "22:00"}], "#7a5c2e"),
                ("t_night", "Turno de noche", [{"start": "22:00", "end": "06:00"}], "#2f4a7a"),
            ]
        }

    def _roster(self, company, people, patterns, *, weeks):
        """A month of shifts, with the mistakes on purpose.

        A clean roster produces no findings, which makes the review screen look
        like it does nothing.
        """
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        start = monday - timedelta(weeks=weeks - 2)

        rostered = ["worker", "delegate", "parttime", "parttime2", "reduced", "annual", "minor"]
        for offset in range((weeks + 2) * 7):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            for key in rostered:
                person = people[key]
                pattern = patterns["short"] if person.part_time else patterns["morning"]
                Shift.objects.create(
                    tenant=company,
                    employee=person,
                    day=day,
                    pattern=pattern,
                    segments=pattern.segments,
                )

        # And the deliberate problems, all in the current week.
        #
        # Over the contracted twenty-five: not a breach, but those hours are
        # complementary and have their own cap.
        for offset in range(5):
            Shift.objects.filter(
                employee=people["parttime"], day=monday + timedelta(days=offset)
            ).update(segments=patterns["long"].segments, pattern=patterns["long"])

        # Over the legal maximum, which is a different finding.
        for offset in range(6):
            Shift.objects.update_or_create(
                tenant=company,
                employee=people["worker"],
                day=monday + timedelta(days=offset),
                defaults={"pattern": patterns["long"], "segments": patterns["long"].segments},
            )

        # Nine hours for somebody under eighteen: art. 34.3 gives them eight,
        # with none of the "unless the agreement says" adults get.
        Shift.objects.filter(employee=people["minor"], day=monday + timedelta(days=1)).update(
            segments=[{"start": "07:00", "end": "16:00"}]
        )

        # Rostered after their contract ended.
        Shift.objects.create(
            tenant=company,
            employee=people["expired"],
            day=monday + timedelta(days=2),
            pattern=patterns["morning"],
            segments=patterns["morning"].segments,
        )

        self._rotation(company, people, patterns, start=start, weeks=weeks + 2)

    def _rotation(self, company, people, patterns, *, start, weeks):
        """Three shifts around the clock, so the night rules have a team.

        Nerea turns on the quick forward rotation --- two mornings, two evenings,
        two nights, two off --- which is the one occupational medicine actually
        recommends, and which produces **no findings at all**. That is the point
        of putting it in: a lawful rotation has to come out clean, or the
        exception for changeovers is just a way of hiding real short rests.

        Turning forward is what makes it clean. Each move gives twenty-four
        hours because the shift starts later than the one before it ended.
        Rotating backwards --- nights onto evenings --- is where the eight-hour
        changeover comes from, and there is one of those below, on purpose.

        Óscar does not rotate. He is the declared night worker, and a permanent
        night is what art. 36.3 caps at two consecutive weeks.
        Álvaro does not rotate either and nobody ever recorded his status, which
        is the commonest way this goes wrong in real companies.
        """
        cycle = [
            patterns["t_morning"],
            patterns["t_morning"],
            patterns["t_evening"],
            patterns["t_evening"],
            patterns["t_night"],
            patterns["t_night"],
            None,
            None,
        ]
        night = patterns["t_night"]

        for offset in range(weeks * 7):
            day = start + timedelta(days=offset)

            turn = cycle[offset % len(cycle)]
            if turn is not None:
                Shift.objects.update_or_create(
                    tenant=company,
                    employee=people["rotating"],
                    day=day,
                    defaults={"pattern": turn, "segments": turn.segments},
                )

            # Two off every eight for the two on permanent nights, so the weekly
            # rest lands somewhere and the run of night weeks is still a run.
            if offset % 8 < 6:
                for key in ("night", "guard"):
                    Shift.objects.update_or_create(
                        tenant=company,
                        employee=people[key],
                        day=day,
                        defaults={"pattern": night, "segments": night.segments},
                    )

        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())

        # The backward rotation, in the current week: off a night at 06:00 and
        # onto an evening at 14:00 the same day. Eight hours, which is under the
        # twelve and over the seven --- lawful, and owed back within four weeks.
        Shift.objects.update_or_create(
            tenant=company,
            employee=people["rotating"],
            day=monday,
            defaults={"pattern": night, "segments": night.segments},
        )
        Shift.objects.update_or_create(
            tenant=company,
            employee=people["rotating"],
            day=monday + timedelta(days=1),
            defaults={
                "pattern": patterns["t_evening"],
                "segments": patterns["t_evening"].segments,
            },
        )

        # Twelve-hour nights for a fortnight. Each one is lawful on its own; the
        # average over fifteen days is not, and an average is the only way to
        # see it. Centred on this week so the whole reference period falls
        # inside the month the roster screen opens on --- a window that runs off
        # the edge is skipped, and the finding would come and go with the date.
        for offset in range(-7, 8):
            day = monday + timedelta(days=offset)
            if (day - start).days % 8 >= 6:
                continue
            Shift.objects.update_or_create(
                tenant=company,
                employee=people["night"],
                day=day,
                defaults={"pattern": None, "segments": [{"start": "20:00", "end": "08:00"}]},
            )

    # ----------------------------------------------------------------- history

    def _history(self, company, people, *, weeks):
        """Punches, built directly rather than through `register_punch`.

        That service stamps the current time and infers the type from what else
        happened *today*, which is right for a real clock-in and useless for
        writing a past. The hash still comes out correct: it is computed on
        save from the fields, whatever they say.
        """
        zone = company.tzinfo
        today = timezone.localdate()
        start = today - timedelta(weeks=weeks)

        # El quinto elemento es el descanso de bocadillo, cuando lo hay: art.
        # 3.d pide anotar el principio y el final de las pausas que no son
        # tiempo de trabajo, el producto las registra y esta demostración no
        # enseñaba **ninguna**. Quien hace jornada partida larga la tiene; las
        # de media jornada, no, que es lo que pasa de verdad.
        clocking = [
            # La oficina ficha como todo el mundo: en una empresa de catorce
            # personas quien lleva la administración también trabaja, y la
            # demostración enseñaba su «Mi jornada» **en blanco**, que es la
            # primera pantalla que ve quien entra a probar el producto.
            ("admin", time(9, 0), time(17, 0), PunchSource.WEB, (time(14, 0), time(14, 30))),
            ("manager", time(8, 30), time(17, 0), PunchSource.WEB, (time(14, 0), time(14, 30))),
            ("worker", time(7, 0), time(15, 0), PunchSource.MOBILE, (time(10, 0), time(10, 20))),
            (
                "delegate",
                time(7, 5),
                time(15, 10),
                PunchSource.MOBILE,
                (time(10, 30), time(10, 50)),
            ),
            ("parttime", time(8, 0), time(13, 0), PunchSource.TERMINAL, None),
            ("parttime2", time(9, 0), time(14, 0), PunchSource.WEB, None),
            ("reduced", time(9, 0), time(15, 0), PunchSource.WEB, None),
            ("annual", time(7, 0), time(16, 0), PunchSource.MOBILE, (time(11, 0), time(11, 30))),
            ("minor", time(7, 0), time(13, 0), PunchSource.TERMINAL, None),
            ("seasonal", time(7, 0), time(15, 0), PunchSource.MOBILE, (time(10, 0), time(10, 15))),
            ("federated", time(8, 0), time(16, 0), PunchSource.WEB, (time(12, 0), time(12, 30))),
        ]

        for offset in range((today - start).days):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            for key, opens, closes, source, rest in clocking:
                # Not everybody every day: a record with no gaps is a record
                # nobody has to interpret, and interpreting is the job.
                if random.random() < 0.06:
                    continue
                jitter = timedelta(minutes=random.randint(-7, 12))
                # Y la pausa tampoco todos los días, por lo mismo: un día que
                # se sale corriendo también existe y hay que saber leerlo.
                self._pair(
                    company,
                    people[key],
                    day,
                    opens,
                    closes,
                    source,
                    zone,
                    jitter,
                    rest=rest if rest and random.random() < 0.85 else None,
                    mode=DESDE_CASA.get((key, day.weekday()), WorkMode.ONSITE),
                )

        # Somebody flexible: no roster, hours all over the place, and a week
        # well over the maximum that nothing was checking.
        for offset in range((today - start).days):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5 and random.random() > 0.3:
                continue
            opens = time(random.randint(7, 11), random.choice([0, 15, 30]))
            hours = random.choice([5, 6, 8, 9, 11])
            closes = (datetime.combine(day, opens) + timedelta(hours=hours)).time()
            self._pair(company, people["flexible"], day, opens, closes, PunchSource.WEB, zone)

        # And one still clocked in, so "today" has an open day on screen.
        Punch.objects.create(
            tenant=company,
            employee=people["worker"],
            timestamp=datetime.combine(today, time(7, 2), tzinfo=zone),
            punch_type=PunchType.IN,
            source=PunchSource.MOBILE,
        )

    def _pair(
        self,
        company,
        person,
        day,
        opens,
        closes,
        source,
        zone,
        jitter=timedelta(),
        *,
        rest=None,
        mode=WorkMode.ONSITE,
    ):
        """Un día de trabajo: entrada, la pausa si la hubo, y salida.

        Los dos eventos de una pausa llevan `interval=BREAK` --- el que la abre
        y el que la cierra ---, que es como el resto del producto la reconoce:
        `_add_span` mira el intervalo del evento que abrió para saber en qué
        cubo va el tramo.
        """
        entered = datetime.combine(day, opens, tzinfo=zone) + jitter
        left = datetime.combine(day, closes, tzinfo=zone) + jitter
        Punch.objects.create(
            tenant=company,
            employee=person,
            timestamp=entered,
            punch_type=PunchType.IN,
            source=source,
            # Art. 3.e. Va en el evento que **abre** el tramo, como todo lo
            # descriptivo: es el que dice qué es ese rato.
            work_mode=mode,
        )
        if rest:
            starts, ends = rest
            for moment, kind in (
                (starts, PunchType.OUT),  # sale a desayunar
                (ends, PunchType.IN),  # y vuelve
            ):
                Punch.objects.create(
                    tenant=company,
                    employee=person,
                    timestamp=datetime.combine(day, moment, tzinfo=zone) + jitter,
                    punch_type=kind,
                    source=source,
                    interval=PunchInterval.BREAK,
                )
        Punch.objects.create(
            tenant=company,
            employee=person,
            timestamp=left,
            punch_type=PunchType.OUT,
            source=source,
            # A few hours declared as complementary on the part-time contracts,
            # which is what the cap is about.
            hours_nature=(
                HoursNature.COMPLEMENTARY
                if person.part_time and random.random() < 0.15
                else HoursNature.ORDINARY
            ),
        )

    # ---------------------------------------------------------------- absences

    def _absences(self, company, people):
        today = timezone.localdate()
        wanted = [
            (
                "worker",
                AbsenceType.VACATION,
                40,
                47,
                AbsenceStatus.APPROVED,
                "Vacaciones de verano",
            ),
            ("parttime", AbsenceType.VACATION, 12, 16, AbsenceStatus.PENDING, "Puente"),
            ("delegate", AbsenceType.PERSONAL, 5, 5, AbsenceStatus.PENDING, "Asuntos propios"),
            ("annual", AbsenceType.SICK_LEAVE, -12, -5, AbsenceStatus.APPROVED, ""),
            ("parttime2", AbsenceType.VACATION, -30, -25, AbsenceStatus.REJECTED, "No procede"),
            # Clashes with the roster: the most ordinary planning mistake there
            # is, and the one that reaches the worker fastest.
            ("reduced", AbsenceType.VACATION, 1, 3, AbsenceStatus.APPROVED, "Días pedidos"),
        ]
        for key, kind, begins, ends, status, reason in wanted:
            Absence.objects.create(
                tenant=company,
                employee=people[key],
                absence_type=kind,
                start_date=today + timedelta(days=begins),
                end_date=today + timedelta(days=ends),
                status=status,
                reason=reason,
                approved_by=people["manager"] if status != AbsenceStatus.PENDING else None,
                resolved_at=timezone.now() if status != AbsenceStatus.PENDING else None,
            )

        self._partial_absences(company, people, today)
        self._suspensions(company, people, today)
        self._remote_agreements(company, people, today)

    def _remote_agreements(self, company, people, today):
        """El acuerdo de Ana, y el que Luis no tiene.

        La Ley 10/2021 se aplica desde el 30 % de la jornada a distancia en tres
        meses (art. 1), y entonces exige acuerdo por escrito y **previo** (art.
        5.1). Los dos casos están a propósito: Ana teletrabaja el 40 % y tiene el
        suyo firmado dos semanas antes de empezar; Luis el 60 % y no tiene
        ninguno, que es lo que la revisión del cuadrante saca a la luz.

        Sin el segundo, la demostración enseñaría la ley cumplida y no enseñaría
        para qué sirve mirarla.
        """
        empieza = today - timedelta(days=120)
        RemoteWorkAgreement.objects.create(
            tenant=company,
            employee=people["admin"],
            signed_on=empieza - timedelta(days=14),
            starts_on=empieza,
            agreed_share=40,
            note="Martes y jueves desde casa. Medios y gastos, en el anexo del contrato.",
        )

    def _suspensions(self, company, people, today):
        """Tres: una que para el contrato y dos que lo encogen.

        Las que encogen son las que hace falta ver. Un ERTE que reduce la
        jornada un cuarenta por ciento no suspende nada: la persona sigue
        viniendo, por menos tiempo, y sin él su cuadrante se leería como que se
        pasa de sus horas todas las semanas.

        Y la reducción por guarda legal del art. 37.6, que es la más corriente
        de todas y que hasta el 28/08 el producto **no dejaba registrar** ---
        reducir era cosa de lo que apuntaba la empresa, y esta la pide quien
        trabaja ---. La demostración la llevaba escrita en el horario contratado,
        que es donde no hay fracción ni fechas.
        """
        catalogue = {kind.code: kind for kind in LeaveType.objects.all()}
        wanted = [
            ("seasonal", "es.unpaid_leave", -60, 200, None, "Excedencia voluntaria"),
            ("parttime2", "es.erte", -20, 70, 40, "ERTE de reducción, 40 %"),
            # Un cuarto de reducción: `reduction_share` es **cuánto se reduce**,
            # así que 25 y no 75. Trabaja 30 de sus 40 horas, que es lo que
            # dicen sus fichajes. Y acaba, que es la mitad del asunto.
            # Jubilación parcial al 50 %, que es el máximo del art. 12.6 sin
            # relevo a jornada completa. Nerea cubre esas veinte horas.
            (
                "retiring",
                "es.partial_retirement",
                -90,
                1000,
                50,
                "Jubilación parcial, media jornada",
            ),
            (
                "reduced",
                "es.childcare_reduced_hours",
                -400,
                900,
                25,
                "Guarda legal, un cuarto de jornada",
            ),
        ]
        for key, code, begins, ends, share, reason in wanted:
            kind = catalogue.get(code)
            if kind is None:
                continue
            Absence.objects.create(
                tenant=company,
                employee=people[key],
                leave_type=kind,
                absence_type=kind.family,
                start_date=today + timedelta(days=begins),
                end_date=today + timedelta(days=ends),
                reduction_share=share,
                reason=reason,
                status=AbsenceStatus.APPROVED,
                approved_by=people["admin"],
                resolved_at=timezone.now(),
            )

    def _partial_absences(self, company, people, today):
        """Parts of a day, which is the commonest absence there is.

        Somebody leaving at eleven with a fever, an hour at the doctor, a
        family emergency counted in hours because art. 37.9 counts it in hours.
        None of these could be recorded until the leave had times, and every one
        of them left a short day in the record with nothing to explain it.
        """
        catalogue = {kind.code: kind for kind in LeaveType.objects.all()}
        wanted = [
            ("worker", "es.medical", -3, time(11, 0), time(13, 30), "Consulta del especialista"),
            ("delegate", "es.force_majeure", -1, time(9, 0), time(12, 0), "Aviso del colegio"),
            ("parttime", "es.exams", 4, time(15, 0), time(19, 0), "Examen de FP"),
            ("rotating", "es.breastfeeding", -2, time(6, 0), time(7, 0), ""),
        ]
        for key, code, offset, opens, closes, reason in wanted:
            kind = catalogue.get(code)
            if kind is None:
                continue
            day = today + timedelta(days=offset)
            Absence.objects.create(
                tenant=company,
                employee=people[key],
                leave_type=kind,
                absence_type=kind.family,
                start_date=day,
                end_date=day,
                start_time=opens,
                end_time=closes,
                reason=reason,
                status=AbsenceStatus.APPROVED if offset < 0 else AbsenceStatus.PENDING,
                approved_by=people["manager"] if offset < 0 else None,
                resolved_at=timezone.now() if offset < 0 else None,
            )

    # ------------------------------------------------------------- corrections

    def _corrections(self, company, people):
        """One in each art. 4.b state, so the screens have all three."""
        now = timezone.now()

        # Asked for by the person, still pending.
        request_correction(
            employee=people["parttime"],
            company=company,
            requested_by=people["parttime"],
            kind="ADD",
            proposed_type=PunchType.OUT,
            proposed_timestamp=now - timedelta(days=3, hours=6),
            reason="Me quedé sin batería y no pude fichar la salida.",
        )

        # Proposed by the company, waiting for the person.
        propose_correction(
            employee=people["worker"],
            company=company,
            proposed_by=people["manager"],
            kind="ADD",
            proposed_type=PunchType.OUT,
            proposed_timestamp=now - timedelta(days=5, hours=4),
            reason="No consta la salida; el encargado confirma que se fue a las 15:00.",
        )

        # Proposed, disagreed with, and still open. A MODIFY names the event it
        # corrects: without one there is nothing to point the new version at,
        # and the original has to stay readable beside it.
        target = (
            Punch.objects.filter(employee=people["delegate"], punch_type=PunchType.OUT)
            .order_by("-timestamp")
            .first()
        )
        disputed = propose_correction(
            employee=people["delegate"],
            company=company,
            proposed_by=people["manager"],
            kind="MODIFY",
            target=target,
            proposed_type=PunchType.OUT,
            proposed_timestamp=target.timestamp + timedelta(minutes=40),
            reason="La salida registrada no cuadra con el parte de trabajo.",
        )
        dispute_correction(
            disputed,
            employee=people["delegate"],
            account="Salí a las 15:40, estuve cerrando el riego del parque de la Alameda.",
        )

        # And one the company applied anyway, which is the state the record has
        # to be able to hold.
        imposed = propose_correction(
            employee=people["annual"],
            company=company,
            proposed_by=people["manager"],
            kind="ADD",
            proposed_type=PunchType.IN,
            proposed_timestamp=now - timedelta(days=11, hours=9),
            reason="Faltaba la entrada del día del temporal.",
        )
        dispute_correction(imposed, employee=people["annual"], account="Ese día no fui a trabajar.")
        apply_without_agreement(imposed, resolved_by=people["admin"])

    # ------------------------------------------------------------------ tidy up

    def _wipe(self):
        """Tira los datos de muestra. Solo con DEBUG, y solo estos.

        El rastro es inmutable **en la base**: tres triggers rechazan UPDATE,
        DELETE y TRUNCATE, y hacen bien --- «un rastro que puede editar aquel a
        quien incrimina no es prueba». Además `AuditLog.tenant` es PROTECT, que
        lo comprueba Django antes de llegar a la base, así que sin quitar esas
        filas tampoco se puede borrar la empresa.

        O sea que un reseteo tiene que apartar los triggers a propósito. Es
        defendible aquí y en ningún otro sitio: este comando se niega a correr
        sin DEBUG y su cometido es tirar datos de mentira. Con `finally` para que
        un fallo a mitad no los deje caídos, que sería dejar el rastro
        desprotegido sin decirlo.
        """
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE audit_auditlog DISABLE TRIGGER USER")
        try:
            for tax_id in (NEIGHBOUR_TAX_ID, TAX_ID):
                company = Tenant.objects.filter(tax_id=tax_id).first()
                if company is not None:
                    self._delete_everything(company)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE audit_auditlog ENABLE TRIGGER USER")

    def _delete_everything(self, company):
        """El orden importa, y eso es una virtud.

        `Punch.employee` es PROTECT, así que una persona con jornada registrada
        no se puede borrar. Tirar los datos de muestra obliga a desmontarlos a
        mano, que es justo la fricción que el modelo busca.
        """
        from apps.audit.models import AuditLog
        from apps.punches.corrections import PunchCorrection

        PunchCorrection.objects_all_tenants.filter(tenant=company).delete()
        Punch.objects_all_tenants.filter(tenant=company).delete()
        Shift.objects_all_tenants.filter(tenant=company).delete()
        ShiftPattern.objects_all_tenants.filter(tenant=company).delete()
        Absence.objects_all_tenants.filter(tenant=company).delete()
        AuditLog.objects.filter(tenant=company).delete()
        User.objects.filter(tenant=company).delete()
        Department.objects_all_tenants.filter(tenant=company).delete()
        company.delete()
        User.objects.filter(email="root@opentimetrack.local").delete()

    def _report(self, company, people, rules):
        with tenant_context(company.id):
            counts = {
                "personas": User.objects.count(),
                "fichajes": Punch.objects.count(),
                "turnos del cuadrante": Shift.objects.count(),
                "ausencias": Absence.objects.count(),
            }

        self.stdout.write(self.style.SUCCESS(f"\n{company.name} · {company.tax_id}"))
        for label, total in counts.items():
            self.stdout.write(f"  {total:>5}  {label}")

        self.stdout.write("\n  Entra con cualquiera de estos y la contraseña " + PASSWORD + ":")
        for key, label in [
            ("admin", "administración"),
            ("manager", "responsable"),
            ("worker", "jornada completa"),
            ("parttime", "25 h semanales"),
            ("reduced", "jornada reducida"),
            ("annual", "1700 h anuales"),
            ("flexible", "sin horario fijo"),
            ("minor", "menor de 18"),
        ]:
            self.stdout.write(f"    {people[key].email:<26} {label}")
