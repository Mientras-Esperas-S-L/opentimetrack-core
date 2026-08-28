"""Building a roster, and telling the truth about it.

Everything in `review_roster` reports; nothing refuses. That is a decision, not
an omission, and it is the same one taken in `apps.tenants.rules`: RD 1561/1995
modifies the rest periods for transport, on-call work and shift handovers, all
lawfully. A product that refused to save those rosters would be unusable in
exactly the sectors where working time matters most, and refusing would mean
deciding a compliance question that belongs to the company and its advisers.

What it does instead is say **what it found and on what basis**, so nobody can
claim they were not told.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from itertools import pairwise

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from apps import legal
from apps.absences.models import STOPS_THE_WHOLE_DAY, Absence, AbsenceStatus
from apps.common.clock import local_date_of
from apps.common.dst import change_across, real_gap
from apps.common.exceptions import BusinessRuleError
from apps.shifts.models import Shift, ShiftPattern, working_days_between
from apps.tenants.rules import WorkingTimeRules


@dataclass(frozen=True)
class Finding:
    """Something worth saying about a roster.

    `basis` is not decoration: a warning nobody can trace to an article is a
    warning nobody can argue with, and the person reading it is entitled to know
    which rule the company has configured and why.
    """

    day: date
    employee_id: str
    code: str
    message: str
    #: Filled in one pass at the end, from the company's country. Empty at
    #: construction because the place a finding is built has no business
    #: knowing which country's article covers it.
    basis: str = ""
    #: Carried alongside the id so a warning can name who it is about without
    #: the caller holding the whole workforce to look it up in --- which is what
    #: the roster screen was doing, and it only ever held the first page of it.
    employee_name: str = ""

    def as_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "employee": str(self.employee_id),
            "employee_name": self.employee_name,
            "code": self.code,
            "message": str(self.message),
            "basis": self.basis,
        }


# ------------------------------------------------------------------- assigning


@transaction.atomic
def assign_pattern(*, employee, company, pattern: ShiftPattern, days) -> list[Shift]:
    """Puts a pattern on a set of days, replacing whatever was there.

    Replacing rather than refusing: a roster gets redrawn, and making somebody
    clear the old one first turns one action into two with a broken state in
    between.

    The spans are **copied** from the pattern. Editing "morning" next month must
    not rewrite a day that was already published --- people arranged their lives
    around it.
    """
    wanted = list(days)
    if not wanted:
        raise BusinessRuleError(
            code="no_days",
            message=_("Choose at least one day."),
        )

    Shift.objects.filter(employee=employee, day__in=wanted).delete()

    return Shift.objects.bulk_create(
        [
            Shift(
                tenant=company,
                employee=employee,
                day=day,
                pattern=pattern,
                segments=pattern.segments,
            )
            for day in wanted
        ]
    )


@transaction.atomic
def paint_cells(*, company, cells) -> dict:
    """Sets a scattered handful of days at once, each to its own shift.

    `assign_pattern` paints one pattern over a rectangle of the calendar, which
    is how a roster gets built and not how it gets corrected. Dragging on the
    grid needs the other shape: *these* people on *these* days, each becoming
    whatever the stroke says --- and, for undo, each going back to whatever it
    was, which is a different pattern per cell and sometimes no pattern at all.

    A cell carries a pattern, or bare spans, or neither:

    **A pattern** copies its spans, exactly as assigning does. Editing "morning"
    next month must not rewrite a day already published.

    **Bare spans** are a day that never came from a pattern --- a one-off, a
    twelve-hour night somebody typed in. Undo has to be able to put those back
    as they were rather than approximating them with the nearest pattern.

    **Neither** rubs the day out.
    """
    wanted = list(cells)
    if not wanted:
        return {"painted": 0, "cleared": 0}

    # Resolved through the tenant manager, so a cell naming somebody else's
    # person or pattern finds nothing and is refused rather than written.
    people = {
        str(person.pk): person
        for person in _users().objects.filter(
            tenant=company, pk__in={c["employee"] for c in wanted}
        )
    }
    patterns = {
        str(pattern.pk): pattern
        for pattern in ShiftPattern.objects.filter(
            pk__in={c["pattern"] for c in wanted if c.get("pattern")}
        )
    }

    for cell in wanted:
        if str(cell["employee"]) not in people:
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("Somebody in that list is not in this company."),
            )
        if cell.get("pattern") and str(cell["pattern"]) not in patterns:
            raise BusinessRuleError(
                code="unknown_pattern", message=_("That shift pattern does not exist.")
            )

    # Every named day goes first, whatever it held. A stroke replaces; it does
    # not merge with what was underneath, and the unique constraint would refuse
    # the write anyway.
    #
    # One clause per person rather than one per cell --- for a dragged rectangle
    # that is the number of rows instead of rows times days --- and days crossed
    # with people, which would take out somebody else's Tuesday.
    days_of: dict = {}
    for cell in wanted:
        days_of.setdefault(str(cell["employee"]), set()).add(cell["day"])

    matcher = Q()
    for employee, days in days_of.items():
        matcher |= Q(employee_id=employee, day__in=days)
    Shift.objects.filter(matcher).delete()

    drawn = []
    for cell in wanted:
        pattern = patterns.get(str(cell["pattern"])) if cell.get("pattern") else None
        segments = pattern.segments if pattern else cell.get("segments")
        if not segments:
            continue
        drawn.append(
            Shift(
                tenant=company,
                employee=people[str(cell["employee"])],
                day=cell["day"],
                pattern=pattern,
                segments=segments,
            )
        )

    Shift.objects.bulk_create(drawn)
    return {"painted": len(drawn), "cleared": len(wanted) - len(drawn)}


def _users():
    """Imported late: `users` imports this module's app for the roster."""
    from apps.users import models

    return models.User


@transaction.atomic
def clear_shifts(*, employee, days) -> int:
    deleted, _detail = Shift.objects.filter(employee=employee, day__in=list(days)).delete()
    return deleted


def weekdays_in(first: date, last: date, weekdays: list[int]) -> list[date]:
    """Days in the range falling on the given weekdays (Monday = 0).

    What makes "every Monday to Friday in September" one action instead of
    twenty-two.
    """
    return [d for d in working_days_between(first, last) if d.weekday() in weekdays]


# -------------------------------------------------------------------- reviewing


def review_roster(*, company, first: date, last: date, employee=None) -> list[Finding]:
    """Reads the roster and says what departs from the company's own rules.

    Deliberately reads one day either side of the window: the rest between
    working days is a property of the boundary between two shifts, so checking a
    month in isolation would miss whether the first day of it clashes with the
    last day of the month before.

    **Y las semanas de los bordes, enteras.** El tope semanal es una propiedad de
    la semana, y una semana a caballo de dos meses no cabe en ninguno de los dos:
    revisando junio no salía, revisando julio tampoco, y solo aparecía mirando los
    dos juntos. Medido con cuarenta y cinco horas planificadas del 29 de junio al
    5 de julio de 2026 --- por encima de las cuarenta del art. 34.1, y quien revisa
    el cuadrante mes a mes no lo veía nunca.

    Los demás chequeos no se enteran: todos filtran por `first`/`last` antes de
    reportar, así que leer más días les da contexto y no les hace hablar de días
    que nadie pidió.
    """
    rules = WorkingTimeRules.for_company(company)

    # Hasta el lunes de la semana del primer día y el domingo de la del último.
    desde = first - timedelta(days=first.weekday() or 1)
    hasta = last + timedelta(days=(6 - last.weekday()) or 1)

    shifts = Shift.objects.filter(day__gte=desde, day__lte=hasta).select_related("employee")
    if employee is not None:
        shifts = shifts.filter(employee=employee)

    by_person: dict = {}
    for shift in shifts.order_by("employee_id", "day"):
        by_person.setdefault(shift.employee_id, []).append(shift)

    framework = legal.for_company(company)

    # De una vez, no una consulta por cabeza. Ver `reductions_in`.
    reducciones = reductions_in(company, first, last)

    findings: list[Finding] = []
    for employee_id, roster in by_person.items():
        findings.extend(_check_daily_rest(roster, rules, framework.shifts, first, last, company))
        findings.extend(_check_weekly_hours(employee_id, roster, rules, first, last, reducciones))
        findings.extend(_check_breaks(roster, rules, first, last))
        findings.extend(
            _check_weekly_rest(
                employee_id,
                roster,
                rules,
                framework.minors,
                framework.shifts,
                first,
                last,
                company,
            )
        )
        findings.extend(
            _check_night_work(roster, rules, framework.night, framework.shifts, first, last)
        )
        findings.extend(_check_under_eighteen(roster, rules, framework.minors, first, last))
    findings.extend(_check_leave_clashes(first, last, employee))
    findings.extend(_check_rostered_on_a_holiday(by_person, first, last))
    findings.extend(_check_outside_the_contract(by_person))
    findings.extend(_check_time_actually_worked(company, rules, first, last, employee, reducciones))
    findings.extend(
        _check_complementary_cap(company, framework.complementary, first, last, employee)
    )
    findings.extend(_check_reduction_within_the_right(company, first, last, employee))
    findings.extend(_check_remote_work_agreement(company, first, last, employee))
    findings.extend(_check_training_contract(company, rules, first, last, employee))
    findings.extend(_check_adaptation_deadline(company, first, last, employee))
    findings.extend(_check_relief_contracts(company, rules, first, last, employee))
    findings.extend(_check_irregular_balance(company, first, last, employee))
    findings.extend(_check_notice(company, by_person, rules, first, last))

    # The citation comes from the company's country, not from the place the
    # finding was built. Nine of them used to be typed in beside each `Finding`,
    # which made every warning quietly Spanish --- and made adding a country a
    # search-and-replace through this file.
    findings = [replace(f, basis=framework.finding_citation(f.code).basis) for f in findings]

    # Filled in one pass rather than at each of the nine places a Finding is
    # built: one of them would be forgotten, and a warning about a person whose
    # name is missing reads like a bug in the warning.
    # Only the blanks. The names map is built from the roster, and somebody with
    # no fixed schedule has no roster at all --- their findings come from the
    # record and already carry the name. Overwriting would blank exactly the
    # people the worked-time check exists for.
    names = {shift.employee_id: shift.employee.get_full_name() for shift in shifts}
    findings = [
        f if f.employee_name else replace(f, employee_name=names.get(f.employee_id, ""))
        for f in findings
    ]

    return sorted(findings, key=lambda f: (f.day, f.code))


def _check_notice(company, by_person, rules, first, last) -> list[Finding]:
    """Turnos puestos con menos preaviso del que la empresa tiene configurado.

    «El trabajador deberá conocer con un preaviso mínimo de cinco días el día y
    la hora de la prestación de trabajo resultante» (art. 34.2 ET). El plazo
    estaba en el modelo, en el marco legal y en la pantalla de ajustes con su
    cita --- y no lo leía ni una línea de código. Un ajuste que no lee nadie es
    peor que no tenerlo: quien lo configura se queda convencido de que el
    producto lo vigila.

    Se avisa, no se impide, como con el resto de los mínimos. Un cambio urgente
    ---alguien se pone malo y hay que cubrir el turno--- es legítimo y frecuente,
    y negarse a registrarlo dejaría el cuadrante real fuera del cuadrante.

    El plazo se cuenta desde que el turno **se puso o se cambió**, no desde hoy.
    Contra hoy, un turno planificado en enero para julio se volvería «con poco
    preaviso» solo por acercarse la fecha. Y se mira `updated_at` y no
    `created_at` porque mover un turno de las siete a las quince es un dato
    nuevo que la persona tiene que conocer: el artículo pide el día **y la
    hora**.
    """
    minimo = int(rules.roster_notice_days or 0)
    if minimo <= 0:
        return []

    found = []
    for roster in by_person.values():
        for shift in roster:
            if not (first <= shift.day <= last):
                continue
            # Sin marca de tiempo no se puede afirmar nada, y afirmar sin poder
            # es lo que convierte un aviso en ruido.
            if shift.updated_at is None:
                continue
            sabido = local_date_of(shift.updated_at, company)
            dias = (shift.day - sabido).days
            if dias >= minimo:
                continue
            # Anotado **después** del día: eso no es poco preaviso, es registrar
            # lo que ya pasó, y avisar ahí sería llamar incumplimiento a rellenar
            # el cuadrante de la semana pasada. Si de eso hay que decir algo, lo
            # dice el registro de actividad, que es donde consta quién lo tocó y
            # cuándo.
            if dias < 0:
                continue
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="short_roster_notice",
                    message=(
                        _("Rostered the same day.")
                        if dias <= 0
                        else ngettext(
                            "Rostered %(days)s day ahead, under the %(floor)s "
                            "the company asks for.",
                            "Rostered %(days)s days ahead, under the %(floor)s "
                            "the company asks for.",
                            dias,
                        )
                        % {"days": dias, "floor": minimo}
                    ),
                )
            )
    return found


def _check_daily_rest(roster, rules, shifts_law, first, last, company) -> list[Finding]:
    """Rest between one day and the next, against the floor that applies.

    Two floors, not one. The ordinary twelve hours, and --- for somebody on
    rotating shifts, on the day the rotation moves them --- the shorter one the
    law allows precisely so that the rotation is possible. Applying the ordinary
    floor to a changeover reported every rotating team in the country as being
    in breach, which is how this check came to be rewritten.

    The shorter rest is still reported. It is not a breach and the wording says
    so, but the difference has to be given back within four weeks and nobody
    gives back what nobody wrote down.
    """
    found = []
    person = roster[0].employee if roster else None
    rotating = bool(person and person.rotating_shifts and shifts_law)

    for previous, current in pairwise(roster):
        # En tiempo real, no de reloj. Un turno guarda horas de pared, y las
        # doce que van de las 22:00 a las 10:00 son **once** la madrugada del
        # último domingo de marzo: el cuadrante cumplía el suelo del art. 34.3
        # sobre el papel y dejaba a la persona con once horas sin avisar.
        gap = real_gap(previous.ends_at, current.starts_at, company).total_seconds() / 3600
        if gap >= rules.daily_rest_hours or not (first <= current.day <= last):
            continue

        # A changeover is a day the shift moved. Same hours two days running is
        # not a rotation, and a short rest there is short for the ordinary
        # reason --- the roster asked for it.
        moved = rotating and _start_of(current) != _start_of(previous)

        if moved and gap >= float(shifts_law.changeover_rest_hours):
            found.append(
                Finding(
                    day=current.day,
                    employee_id=current.employee_id,
                    code="changeover_rest_owed",
                    message=_(
                        "%(hours)s h of rest at a shift changeover, which is allowed. "
                        "The %(owed)s h missing from the usual %(usual)s h are owed back "
                        "within %(weeks)s weeks."
                    )
                    % {
                        "hours": f"{gap:.1f}",
                        "owed": f"{float(rules.daily_rest_hours) - gap:.1f}",
                        "usual": f"{float(rules.daily_rest_hours):g}",
                        "weeks": shifts_law.accumulation_weeks,
                    },
                )
            )
            continue

        floor = float(shifts_law.changeover_rest_hours) if moved else float(rules.daily_rest_hours)

        # Y de dónde sale la cifra, si sale de ahí. Quien lee el cuadrante ve
        # 22:00 y 10:00 y cuenta doce: sin esta frase, el aviso parece una
        # cuenta mal hecha del programa y se ignora justo la noche en que no
        # hay que ignorarlo. La cifra no se toca ---esas horas son las que la
        # persona descansó--- solo se explica.
        movio = change_across(
            previous.ends_at.replace(tzinfo=company.tzinfo),
            current.starts_at.replace(tzinfo=company.tzinfo),
            company,
        )
        porque = (
            " " + _("The clocks went forward that night, so the shifts are an hour closer.")
            if movio > 0
            else ""
        )

        found.append(
            Finding(
                day=current.day,
                employee_id=current.employee_id,
                code="short_daily_rest",
                message=(
                    _(
                        "Only %(hours)s h of rest since the previous shift, under the "
                        "%(floor)s h a changeover may go down to."
                    )
                    if moved
                    else _("Only %(hours)s h of rest since the previous shift.")
                )
                % {"hours": f"{gap:.1f}", "floor": f"{floor:g}"}
                + porque,
            )
        )
    return found


def _start_of(shift) -> str:
    """The shift's starting time as text, for telling one shift team from another."""
    return min(span["start"] for span in shift.segments)


def _check_weekly_hours(employee_id, roster, rules, first, last, reductions=None) -> list[Finding]:
    """Hours per week, against two different things.

    They used to be one check against the company's figure, which meant a
    twenty-five hour contract rostered for thirty-eight said nothing at all:
    thirty-eight is under forty, so the legal ceiling was fine and nobody was
    looking at the contract.

    They are not the same question and they do not have the same answer:

    **Over the legal maximum** is a breach. Art. 34.1 ET sets it and no contract
    may go above it.

    **Over what was agreed** is not. Those extra hours are lawful and they are a
    *different kind of hour* --- complementary, under art. 12.5 for part-time
    work --- with their own cap and their own duty to be recorded separately.
    Reporting it as an excess would be wrong; saying nothing loses the only
    signal that the roster is asking for hours nobody agreed to.

    Las semanas que **solapan** el periodo se cuentan enteras, con los turnos de
    los días de fuera incluidos --- `review_roster` los carga a propósito. Antes se
    exigía que la semana cupiera dentro y se descartaba si no, y eso dejaba sin
    revisar la semana de cada borde: la de un mes a caballo del siguiente no salía
    en ninguno de los dos.

    Lo que sigue sin hacerse, y con razón, es contar **media** semana y avisar de
    ella: quien lee un exceso a medias va a buscar horas que no están y deja de
    fiarse del resto. La diferencia es que ahora la semana se cuenta completa en
    vez de no contarse.
    """
    weeks: dict = {}
    for shift in roster:
        year, week, _weekday = shift.day.isocalendar()
        weeks.setdefault((year, week), []).append(shift)

    ceiling = float(rules.weekly_hours)
    person = roster[0].employee

    # Only a weekly figure can be compared week by week. An annual one --- 1700
    # hours in the gardening agreement --- is met or missed over a year, and
    # dividing it by 52 would produce a number nobody agreed to and that no
    # single week is supposed to match.
    agreed_pair = person.agreed_hours(rules)
    agreed = agreed_pair[0] if agreed_pair and agreed_pair[1] == "WEEK" else None

    found = []
    for (_year, _week), shifts_of_week in weeks.items():
        monday = min(s.day for s in shifts_of_week) - timedelta(
            days=min(s.day for s in shifts_of_week).weekday()
        )
        sunday = monday + timedelta(days=6)
        # Que **solape** el periodo, no que quepa entero dentro.
        #
        # Antes se exigía que cupiera, y el razonamiento era bueno para el caso
        # que tenía delante: contar media semana y avisar es peor que callar,
        # porque quien lo lee va a buscar horas que no están. Lo que no se
        # consideró es contar la semana **completa** --- esos turnos están en la
        # base, solo estaban fuera del rango pedido, y ahora se cargan.
        #
        # Sin esto, una semana a caballo de dos meses no cabía en ninguno:
        # cuarenta y cinco horas del 29 de junio al 5 de julio no salían
        # revisando junio, ni revisando julio, y quien revisa el cuadrante mes a
        # mes no las veía nunca.
        if sunday < first or monday > last:
            continue

        hours = sum(s.minutes for s in shifts_of_week) / 60

        # A week inside an ERTE that reduces the day is measured against the
        # reduced **contract**, not the full one. Without this, the whole roster
        # of a company on a partial ERTE reads as somebody being over their
        # hours every single week --- which is the opposite of what happened.
        #
        # The legal maximum does **not** move with it. Art. 34.1 is a ceiling
        # for everybody and an ERTE reduces what was agreed, not what the law
        # allows. Scaling that as well was the first version of this, and it
        # turned "over the contract" --- which during an ERTE is a serious
        # matter --- into "over the legal maximum", a different accusation.
        share = _reduced_share(person, monday, sunday, reductions)
        week_agreed = agreed * share if agreed is not None else None

        if hours > ceiling:
            found.append(
                Finding(
                    day=monday,
                    employee_id=employee_id,
                    code="weekly_hours_exceeded",
                    message=_("%(hours)s h rostered that week, over the %(limit)s h configured.")
                    % {"hours": f"{hours:.1f}", "limit": f"{ceiling:g}"},
                )
            )
        # Only when it is not already over the ceiling: two warnings about the
        # same week would bury the more serious one.
        elif week_agreed is not None and hours > week_agreed:
            found.append(
                Finding(
                    day=monday,
                    employee_id=employee_id,
                    code="over_contracted_hours",
                    message=_(
                        "%(hours)s h rostered that week against %(agreed)s h contracted. "
                        "The %(extra)s h over are complementary hours and count towards "
                        "their own limit."
                    )
                    % {
                        "hours": f"{hours:.1f}",
                        "agreed": f"{week_agreed:g}",
                        "extra": f"{hours - week_agreed:.1f}",
                    },
                )
            )

    # Somebody with no agreed weekly figure has nothing to be measured against.
    # Said once for the window rather than passed over in silence: a roster
    # screen with no warnings should mean "nothing to say", not "not looked at".
    if not person.has_agreed_hours and roster:
        found.append(
            Finding(
                day=first,
                employee_id=employee_id,
                code="no_agreed_weekly_hours",
                message=_(
                    "No agreed weekly hours on this contract, so the weekly total is "
                    "not checked. Only the legal maximum applies."
                ),
            )
        )

    return found


def reductions_in(company, first: date, last: date) -> dict:
    """Las reducciones aprobadas de toda la plantilla, en una consulta.

    Existe porque `_reduced_share` la hacía **por persona y por semana**, dentro
    de dos bucles. La revisión del cuadrante crecía una consulta por cabeza: doce
    para tres personas, veintiuna para doce, y más de doscientas para una
    plantilla de doscientas. Justo la pantalla que un responsable abre para ver
    qué incumple su cuadrante.

    Se devuelve la lista de tramos por persona en vez del porcentaje ya
    calculado porque el porcentaje depende de la ventana que se pregunte ---una
    semana concreta--- y esa cambia dentro del bucle.
    """
    from apps.absences.models import Absence, AbsenceStatus

    filas = Absence.objects.filter(
        status=AbsenceStatus.APPROVED,
        start_date__lte=last,
        end_date__gte=first,
        reduction_share__isnull=False,
        reduction_share__lt=100,
    ).values_list("employee_id", "start_date", "end_date", "reduction_share")

    por_persona: dict = {}
    for employee_id, desde, hasta, cuanto in filas:
        por_persona.setdefault(employee_id, []).append((desde, hasta, cuanto))
    return por_persona


def _reduced_share(person, first, last, reductions=None) -> float:
    """How much of the ordinary day is still expected, over that stretch.

    One unless there is an approved suspension that **reduces** rather than
    stops --- an ERTE under art. 47 taking forty per cent off for six months.
    The smallest share wins when two overlap, which should not happen and is the
    safe answer if it ever does.

    `reductions` es el mapa que devuelve `reductions_in`, ya traído de una vez.
    Sin él consulta por su cuenta, que es correcto para una llamada suelta y era
    un N+1 dentro de un bucle.
    """
    from apps.absences.models import Absence, AbsenceStatus

    person_id = getattr(person, "id", person)

    if reductions is None:
        tramos = Absence.objects.filter(
            employee=person,
            status=AbsenceStatus.APPROVED,
            start_date__lte=last,
            end_date__gte=first,
            reduction_share__isnull=False,
            reduction_share__lt=100,
        ).values_list("start_date", "end_date", "reduction_share")
    else:
        # El mapa se trae por la ventana entera, así que aquí hay que volver a
        # comprobar el solape con la ventana concreta que se pregunta: si no,
        # una reducción de marzo bajaría la cuota de una semana de septiembre.
        tramos = [
            (desde, hasta, cuanto)
            for desde, hasta, cuanto in reductions.get(person_id, [])
            if desde <= last and hasta >= first
        ]

    share = 1.0
    for _desde, _hasta, reduced in tramos:
        share = min(share, max(0.0, 1 - float(reduced) / 100))
    return share


def _check_breaks(roster, rules, first, last) -> list[Finding]:
    """A continuous day past the threshold needs its break.

    Only continuous days: a split shift already has one. And the break is
    reported as owed, not added to the hours --- art. 34.4 ET makes it working
    time only when the agreement says so, which is the company's setting to
    make.
    """
    threshold = float(rules.break_after_hours) * 60
    found = []
    for shift in roster:
        if not (first <= shift.day <= last):
            continue
        if len(shift.segments) > 1:
            continue
        if shift.minutes > threshold:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="break_owed",
                    message=_("A continuous day of %(hours)s h needs a break of %(minutes)s min.")
                    % {"hours": f"{shift.minutes / 60:.1f}", "minutes": rules.break_minutes},
                )
            )
    return found


def _check_weekly_rest(
    employee_id, roster, rules, minors, shifts_law, first, last, company
) -> list[Finding]:
    """Art. 37.1 ET: a day and a half uninterrupted, accumulable.

    The accumulation is why this looks at a period rather than at each week.
    Reporting a week without its full rest would be wrong for anybody on a
    pattern that concentrates it --- which is most of hospitality and retail ---
    and a warning that is wrong half the time gets ignored the other half.

    Fourteen days as a rule; four weeks for somebody on rotating shifts, which
    is the longer window art. 19.b RD 1561/1995 gives them. Reading a rotating
    rota against the shorter one produces the same false positive the daily rest
    used to: lawful patterns reported as breaches, on the days the law wrote the
    exception for.
    """
    if not roster:
        return []

    # Two uninterrupted days for a minor (art. 37.1), and the company's figure
    # for everybody else. Taken from the first day of the window: somebody who
    # turns eighteen inside it keeps the stronger floor for that fortnight,
    # which errs on the side of the protection.
    person = roster[0].employee
    minimum = timedelta(
        hours=minors.weekly_rest_hours if person.is_minor_on(first) else rules.weekly_rest_hours
    )
    found = []

    span_days = shifts_law.accumulation_weeks * 7 if shifts_law and person.rotating_shifts else 14

    # Longest gap in each rolling period that sits inside the window.
    days = sorted({s.day for s in roster})
    for anchor in days:
        window_end = anchor + timedelta(days=span_days - 1)
        if anchor < first or window_end > last:
            continue

        inside = [s for s in roster if anchor <= s.day <= window_end]
        if len(inside) < 2:
            continue

        ordered = sorted(inside, key=lambda s: s.day)
        # Tiempo real por lo mismo que el descanso diario: las treinta y seis
        # horas del art. 37.1 son treinta y cinco si el reloj se adelanta
        # dentro de ellas.
        gaps = [real_gap(a.ends_at, b.starts_at, company) for a, b in pairwise(ordered)]

        # The edges count too. A fortnight of ten days on followed by four off
        # has its rest at the end, and looking only between shifts would miss
        # it and report a pattern that is perfectly lawful.
        window_opens = datetime.combine(anchor, dt_time.min)
        window_closes = datetime.combine(window_end + timedelta(days=1), dt_time.min)
        gaps.append(real_gap(window_opens, ordered[0].starts_at, company))
        gaps.append(real_gap(ordered[-1].ends_at, window_closes, company))

        longest = max(gaps, default=timedelta(0))
        if longest < minimum:
            found.append(
                Finding(
                    day=anchor,
                    employee_id=employee_id,
                    code="short_weekly_rest",
                    message=_(
                        "The longest break in those %(days)s days is %(hours)s h, under "
                        "the %(minimum)s h configured."
                    )
                    % {
                        "days": span_days,
                        "hours": f"{longest.total_seconds() / 3600:.0f}",
                        "minimum": minimum.total_seconds() / 3600,
                    },
                )
            )
            break  # one per person is enough to say the pattern is wrong

    return found


def _check_night_work(roster, rules, night, shifts_law, first, last) -> list[Finding]:
    """Art. 36.1 and 36.3 ET: the status, then the limits it brings.

    The order matters and getting it backwards was one of the four errors the
    legal review corrected. The eight-hour average attaches to somebody who
    **holds the status of night worker**, not to anybody who happens to work
    between 22:00 and 06:00, so the status is settled first and the limits are
    only applied to whoever holds it.

    Three things come out of here:

    **The status is unrecorded but the roster shows it.** Reported, because it
    is a decision the company owes the person --- the status carries a health
    assessment and a pay supplement, neither of which this product handles.

    **The average over the reference period.** An average, not a ceiling: nine
    hours on Tuesday breaches nothing if the fortnight comes out at eight.

    **Too long on the night shift.** Art. 36.3 caps the run at two consecutive
    weeks on a rotation, unless the person asked to stay.
    """
    if not night or not roster:
        return []

    person = roster[0].employee
    window = (night.window_starts_at, night.window_ends_at)
    inside = [s for s in roster if first <= s.day <= last]
    if not inside:
        return []

    holds = person.holds_night_worker_status(night, roster)
    found = []

    # The roster's own reading, said out loud when the company has not answered.
    # An override to "no" is left alone: the company answered, and repeating the
    # reading underneath its answer would read as the product arguing.
    if person.night_worker == "AUTO" and holds:
        nightly = sum(
            1 for s in inside if s.night_minutes(*window) >= night.qualifying_daily_hours * 60
        )
        found.append(
            Finding(
                day=min(s.day for s in inside),
                employee_id=person.pk,
                code="looks_like_night_work",
                message=_(
                    "%(count)s of %(total)s days with %(hours)s h or more at night. If "
                    "the person holds the status of night worker, that brings a "
                    "%(limit)s h average over %(days)s days, a ban on overtime and a "
                    "health assessment. Nobody has recorded whether they do."
                )
                % {
                    "count": nightly,
                    "total": len(inside),
                    "hours": f"{night.qualifying_daily_hours:g}",
                    "limit": f"{night.average_daily_hours:g}",
                    "days": night.average_over_days,
                },
            )
        )

    if holds:
        declared = person.night_worker == "YES"
        found.extend(_check_night_average(person, inside, night, declared, first, last))

    # Art. 36.3 lives inside the shift-work article: "en la organización del
    # trabajo de los turnos... ningún trabajador estará en el de noche más de
    # dos semanas consecutivas, salvo adscripción voluntaria". A watchman on
    # permanent fixed nights is not on rotation, and reporting him as a
    # standing breach of a rule about rotations was the audit's finding.
    if (
        shifts_law
        and shifts_law.max_consecutive_night_weeks
        and person.rotating_shifts
        and not person.voluntary_night_shift
    ):
        found.extend(_check_consecutive_night_weeks(person, inside, night, shifts_law))

    return found


def _check_night_average(person, roster, night, declared, first, last) -> list[Finding]:
    """Eight hours a day on average across the reference period.

    Averaged over every day in the period, not over the days worked: art. 36.1
    says "de promedio, en un período de referencia de quince días", and the rest
    days are part of what the average is taken over. Dividing by days worked
    instead would make a four-on-four-off rota --- the commonest night pattern
    there is --- look like a breach on every single window.

    Two wordings, depending on who decided the status. When the company recorded
    it, this is a limit that was exceeded and says so. When the roster inferred
    it, the excess is stated conditionally --- the status carries obligations
    outside this product, the annual limb of art. 36.1 is invisible from a
    month of calendar, and telling a company it breached a limit its people may
    not even be subject to is the error the legal review already caught once.
    """
    by_day = {s.day: s.minutes for s in roster}
    span = night.average_over_days
    found = []

    for anchor in sorted(by_day):
        window_end = anchor + timedelta(days=span - 1)
        if anchor < first or window_end > last:
            continue
        worked = sum(minutes for day, minutes in by_day.items() if anchor <= day <= window_end)
        average = worked / 60 / span
        if average > night.average_daily_hours:
            found.append(
                Finding(
                    day=anchor,
                    employee_id=person.pk,
                    code="night_worker_average",
                    message=(
                        _(
                            "A night worker averaging %(average)s h a day over %(days)s "
                            "days, above the %(limit)s h allowed."
                        )
                        if declared
                        else _(
                            "Averaging %(average)s h a day over %(days)s days. The roster "
                            "reads like night work, and if the status applies that is "
                            "above the %(limit)s h of art. 36.1 ET."
                        )
                    )
                    % {
                        "average": f"{average:.1f}",
                        "days": span,
                        "limit": f"{night.average_daily_hours:g}",
                    },
                )
            )
            break  # one is enough to say the period is over; the rest overlap

    return found


def _check_consecutive_night_weeks(person, roster, night, shifts_law) -> list[Finding]:
    """Art. 36.3 ET: no more than two weeks running on the night shift.

    Only for somebody who did not volunteer --- the article's own exception, and
    the reason `voluntary_night_shift` is a field. A rota is read week by week:
    a week counts as a night week when most of its rostered days are nights,
    which is how a team is actually assigned to a shift.
    """
    window = (night.window_starts_at, night.window_ends_at)
    weeks: dict = {}
    for shift in roster:
        year, week, _weekday = shift.day.isocalendar()
        weeks.setdefault((year, week), []).append(shift)

    run, started = 0, None
    for key in sorted(weeks):
        days = weeks[key]
        nights = sum(
            1 for s in days if s.night_minutes(*window) >= night.qualifying_daily_hours * 60
        )
        if nights * 2 > len(days):
            run += 1
            started = started or min(s.day for s in days)
            if run > shifts_law.max_consecutive_night_weeks:
                return [
                    Finding(
                        day=started,
                        employee_id=person.pk,
                        code="consecutive_night_weeks",
                        message=_(
                            "%(weeks)s consecutive weeks on the night shift, over the "
                            "%(limit)s allowed. More needs the person to have asked for "
                            "it, which is a field on their record."
                        )
                        % {"weeks": run, "limit": shifts_law.max_consecutive_night_weeks},
                    )
                ]
        else:
            run, started = 0, None
    return []


def _check_under_eighteen(roster, rules, minors, first, last) -> list[Finding]:
    """The floors that apply to workers under eighteen.

    Age is read **per day**, not once: somebody turns eighteen mid-roster and
    the protections stop from that date. Evaluating it once for the whole window
    would either apply them a month too long or drop them a month too early.

    These are the only findings in the module phrased as prohibitions. Elsewhere
    the wording is careful to say "departs from the rules configured", because
    sector regimes lawfully modify them. Here nothing does: art. 6.2 and 6.3
    admit no amount that is allowed, and no agreement can lower art. 34.3 or
    34.4 for a minor.
    """
    found = []
    for shift in roster:
        if not (first <= shift.day <= last):
            continue
        if not shift.employee.is_minor_on(shift.day):
            continue

        hours = shift.minutes / 60

        if hours > minors.max_daily_hours:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="minor_over_daily_limit",
                    message=_(
                        "%(hours)s h rostered for somebody under eighteen. The limit is "
                        "%(limit)s h a day and no agreement can raise it."
                    )
                    % {"hours": f"{hours:.1f}", "limit": minors.max_daily_hours},
                )
            )

        if len(shift.segments) == 1 and hours > minors.break_after_hours:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="minor_break_owed",
                    message=_(
                        "A continuous day of %(hours)s h for somebody under eighteen "
                        "needs a break of %(minutes)s min, from %(after)s h."
                    )
                    % {
                        "hours": f"{hours:.1f}",
                        "minutes": minors.break_minutes,
                        "after": f"{minors.break_after_hours:g}",
                    },
                )
            )

        if shift.overlaps_night(rules.night_starts_at, rules.night_ends_at):
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="minor_night_work",
                    message=_(
                        "Night shift rostered for somebody under eighteen. Art. 6.2 ET "
                        "forbids it outright: there is no permitted amount."
                    ),
                )
            )

    return found


#: La horquilla del art. 37.6: la reducción va de un octavo a la mitad.
#:
#: Sobre **cuánto se reduce**, que es lo que guarda `reduction_share` ---«40
#: means they work 60 %», dice el modelo---. Lo escribí al revés la primera vez,
#: y lo cazó la prueba del cuadrante: con la lectura invertida, una reducción de
#: un cuarto se habría registrado como del 75 %, y la nota que lee quien la
#: apunta lo decía así.
GUARDA_LEGAL_MINIMO = 12.5
GUARDA_LEGAL_MAXIMO = 50.0

#: El código con el que el catálogo español siembra ese permiso. Se mira el
#: código y no el nombre porque la empresa edita su copia ---puede llamarlo
#: «Reducción por cuidado de hijos» y sigue siendo el mismo derecho---.
GUARDA_LEGAL = "es.childcare_reduced_hours"


#: Art. 11.2.b: el tiempo de trabajo efectivo del formativo en alternancia no
#: pasa del 65 % el primer año ni del 85 % el segundo, **de la jornada máxima**
#: del convenio o, en su defecto, de la legal. No de lo que se pactara: el tope
#: mide contra el máximo, así que un contrato de veinte horas sobre una jornada
#: de cuarenta va sobrado aunque él mismo diga cuarenta.
FORMATIVO_PRIMER_ANO = 65.0
FORMATIVO_SEGUNDO_ANO = 85.0


#: Art. 12.6: la jornada se reduce entre un 25 % y un 50 %, o hasta un 75 %
#: cuando el relevo es a jornada completa y de duración indefinida.
#:
#: Sobre **cuánto se reduce**, como todo `reduction_share`.
JUBILACION_MINIMA = 25.0
JUBILACION_MAXIMA = 50.0
JUBILACION_MAXIMA_CON_RELEVO_ENTERO = 75.0

#: El código con el que el catálogo español siembra la jubilación parcial.
JUBILACION_PARCIAL = "es.partial_retirement"


def _check_irregular_balance(company, first, last, employee) -> list[Finding]:
    """Horas de un año ya vencido que siguen sin compensar (art. 34.2).

    Solo para quien tiene la jornada pactada **por año**, que es donde la cifra
    viene neta de vacaciones y festivos y la resta es honesta. Con jornada
    semanal no se contesta: ver `apps.punches.irregular`.

    Se avisa en los dos sentidos, y eso importa. El exceso es lo que suele
    mirarse, pero el artículo dice «por exceso **o por defecto**»: haber
    trabajado de menos también es una diferencia que hay que compensar, y a
    quien la tiene le interesa saberlo antes de que alguien se la reclame de
    golpe.
    """
    from apps.punches.irregular import irregular_balance
    from apps.users.models import HoursPeriod, User

    quienes = User.objects.filter(
        tenant=company,
        is_active=True,
        contracted_period=HoursPeriod.YEAR,
        contracted_hours__isnull=False,
    )
    if employee is not None:
        quienes = quienes.filter(pk=employee.pk)

    found: list[Finding] = []
    for person in quienes:
        saldo = irregular_balance(employee=person, company=company, day=last)
        if not saldo or saldo["settled"]:
            continue
        cuantas = saldo["balance_hours"]
        found.append(
            Finding(
                day=last,
                employee_id=person.id,
                code="irregular_hours_unsettled",
                message=(
                    _(
                        "%(hours)s h over the %(agreed)s h agreed for %(year)s, and art. "
                        "34.2 gives %(months)s months to settle them."
                    )
                    if cuantas > 0
                    else _(
                        "%(hours)s h under the %(agreed)s h agreed for %(year)s, and art. "
                        "34.2 gives %(months)s months to settle them."
                    )
                )
                % {
                    "hours": f"{abs(cuantas):.1f}",
                    "agreed": f"{saldo['agreed_hours']:g}",
                    "year": saldo["year"],
                    "months": saldo["months"],
                },
            )
        )
    return found


def _check_relief_contracts(company, rules, first, last, employee) -> list[Finding]:
    """El par del art. 12.6 y 12.7, que es una sola pieza.

    Quien se jubila parcialmente reduce su jornada y **alguien tiene que cubrir
    lo que deja**. Por eso los dos artículos se comprueban juntos: la cifra que
    el 12.7 compara ---«la duración de la jornada deberá ser, como mínimo, igual
    a la reducción de jornada acordada por el trabajador sustituido»--- sale de
    la jubilación del otro, y sin ella no hay nada que comparar.

    Tres cosas, y las tres se avisan sin impedir nada:

    1. **La reducción, fuera de horquilla.** Del 25 al 50 %, o hasta el 75 % si
       el relevo es a jornada completa e indefinido. El acuerdo lo firman las
       partes y el convenio puede mejorarlo.
    2. **El relevista, por debajo de lo que releva.** Es el sentido del
       contrato.
    3. **Un relevo que no releva a nadie.** Sin jubilación registrada, la cifra
       del artículo no existe: se dice en vez de callar, que es lo que hacía el
       producto antes de tener el vínculo.
    """
    from apps.absences.models import Absence, AbsenceStatus
    from apps.users.models import User, WorkingTimeRegime

    jubilaciones = {
        fila.employee_id: fila
        for fila in Absence.objects.filter(
            status=AbsenceStatus.APPROVED,
            start_date__lte=last,
            end_date__gte=first,
            reduction_share__isnull=False,
            leave_type__code=JUBILACION_PARCIAL,
        ).select_related("employee")
    }

    relevistas = User.objects.filter(
        tenant=company, is_active=True, relieves__isnull=False
    ).select_related("relieves")
    if employee is not None:
        relevistas = relevistas.filter(pk=employee.pk)

    #: Quién tiene a alguien cubriéndole con jornada entera e indefinida, que es
    #: lo que sube el tope del 50 al 75 %.
    con_relevo_entero = {
        quien.relieves_id
        for quien in relevistas
        if quien.regime == WorkingTimeRegime.FULL_TIME and quien.contract_end is None
    }

    found: list[Finding] = []

    for employee_id, jubilacion in jubilaciones.items():
        if employee is not None and employee.id != employee_id:
            continue
        cuanto = float(jubilacion.reduction_share)
        tope = (
            JUBILACION_MAXIMA_CON_RELEVO_ENTERO
            if employee_id in con_relevo_entero
            else JUBILACION_MAXIMA
        )
        if JUBILACION_MINIMA <= cuanto <= tope:
            continue
        found.append(
            Finding(
                day=max(jubilacion.start_date, first),
                employee_id=employee_id,
                code="partial_retirement_out_of_range",
                message=_(
                    "The working day is cut by %(share)s %% for partial retirement, and "
                    "art. 12.6 runs from %(min)s %% to %(max)s %%."
                )
                % {
                    "share": f"{cuanto:g}",
                    "min": f"{JUBILACION_MINIMA:g}",
                    "max": f"{tope:g}",
                },
            )
        )

    for quien in relevistas:
        jubilacion = jubilaciones.get(quien.relieves_id)
        if jubilacion is None:
            found.append(
                Finding(
                    day=last,
                    employee_id=quien.id,
                    code="relief_without_partial_retirement",
                    message=_(
                        "This relief contract stands in for somebody with no partial "
                        "retirement on record, so there is nothing to measure it against."
                    ),
                )
            )
            continue

        suya = quien.agreed_hours(rules)
        del_otro = jubilacion.employee.agreed_hours(rules)
        # Las dos cifras tienen que ser comparables. Convertir un año en semanas
        # daría un número que nadie pactó, que es la misma razón por la que el
        # tope de complementarias tampoco convierte.
        if suya is None or del_otro is None or suya[1] != del_otro[1]:
            continue

        deja_de_trabajar = del_otro[0] * float(jubilacion.reduction_share) / 100
        if suya[0] + 0.001 >= deja_de_trabajar:
            continue
        found.append(
            Finding(
                day=last,
                employee_id=quien.id,
                code="relief_hours_below_the_reduction",
                message=_(
                    "%(hours)s h agreed, and art. 12.7 asks for at least %(needed)s: the "
                    "hours the person being relieved stops working."
                )
                % {"hours": f"{suya[0]:g}", "needed": f"{deja_de_trabajar:.1f}"},
            )
        )
    return found


def _check_adaptation_deadline(company, first, last, employee) -> list[Finding]:
    """Solicitudes del art. 34.8 que llevan más de quince días sin contestar.

    «La empresa, ante la solicitud de adaptación de jornada, abrirá un proceso de
    negociación con la persona trabajadora durante **un periodo máximo de quince
    días**.» Pasados, sigue sin haber respuesta escrita, que es lo que el
    artículo pide.

    Se avisa y no se hace nada más, porque no hay nada que impedir: el plazo se
    incumple **dejando pasar el tiempo**, y lo único que un producto puede hacer
    con eso es que no pase desapercibido. Lo que sí se impide, en el
    serializador, es contestar que no sin motivo, que ahí el artículo no da
    opción.

    El aviso se repite cada vez que se revisa el cuadrante mientras siga sin
    contestar, y está bien que se repita: es una obligación viva, no un suceso.
    """
    from apps.users.models import AdaptationStatus, ScheduleAdaptation

    pendientes = ScheduleAdaptation.objects.filter(
        status=AdaptationStatus.PENDING,
        # Pedidas antes del final de la ventana que se está mirando: una
        # solicitud de la semana que viene todavía no tiene plazo que contar.
        requested_on__lte=last,
    ).select_related("employee")
    if employee is not None:
        pendientes = pendientes.filter(employee=employee)

    found: list[Finding] = []
    for solicitud in pendientes:
        if not solicitud.out_of_time(last):
            continue
        found.append(
            Finding(
                day=max(solicitud.requested_on, first),
                employee_id=solicitud.employee_id,
                code="adaptation_answer_overdue",
                message=_(
                    "Asked for on %(day)s and still unanswered %(days)s days later: art. "
                    "34.8 gives fifteen."
                )
                % {
                    "day": solicitud.requested_on.isoformat(),
                    "days": solicitud.days_waiting(last),
                },
            )
        )
    return found


def _check_training_contract(company, rules, first, last, employee) -> list[Finding]:
    """El tope del contrato formativo en alternancia, y el que no dice cuál es.

    Dos avisos, y el segundo es el que más se va a ver al principio: los
    contratos formativos que ya estaban guardados no dicen si son de alternancia
    (art. 11.2) o para práctica profesional (art. 11.3), porque hasta hoy eran el
    mismo valor. **Sin saberlo no se puede decir si les toca el tope**, y
    adivinarlo sería inventar un incumplimiento o tapar uno.

    El del tope mira **lo contratado**, no lo trabajado. Un formativo en
    alternancia con cuarenta horas pactadas sobre una jornada de cuarenta nace ya
    fuera del artículo, y eso se sabe sin esperar a que fiche: decirlo cuando ya
    ha trabajado seis meses de más es llegar tarde a lo que se podía haber visto
    el primer día.
    """
    from apps.users.models import HoursPeriod, User, WorkingTimeRegime

    quienes = User.objects.filter(
        tenant=company,
        is_active=True,
        regime__in=[
            WorkingTimeRegime.TRAINING,
            WorkingTimeRegime.TRAINING_ALTERNATING,
        ],
    )
    if employee is not None:
        quienes = quienes.filter(pk=employee.pk)

    maxima = float(rules.weekly_hours or 0)
    found: list[Finding] = []
    for person in quienes:
        if person.regime == WorkingTimeRegime.TRAINING:
            found.append(
                Finding(
                    day=last,
                    employee_id=person.id,
                    code="training_kind_not_stated",
                    message=_(
                        "This training contract does not say whether it is alternating "
                        "(art. 11.2) or for work practice (art. 11.3), and only the first "
                        "one has a cap on working time."
                    ),
                )
            )
            continue

        pactadas = person.agreed_hours(rules)
        if not maxima or pactadas is None or pactadas[1] != HoursPeriod.WEEK:
            # Sin jornada máxima de la empresa, o con la del contrato en otro
            # cómputo, no hay dos cifras comparables. Se calla en vez de
            # convertir: dividir un año entre 52 daría un tope que nadie pactó.
            continue

        # Primer o segundo año, contando desde que empezó el contrato. Sin esa
        # fecha se usa el tope **más laxo**: acusar de pasarse del 65 % a quien
        # podría estar en su segundo año sería una acusación construida sobre un
        # dato que falta, y quien se pasa del 85 % se pasa en cualquier año.
        sin_fecha = person.contract_start is None
        segundo_ano = sin_fecha or (last - person.contract_start).days >= 365
        tope_pct = FORMATIVO_SEGUNDO_ANO if segundo_ano else FORMATIVO_PRIMER_ANO
        tope = maxima * tope_pct / 100

        if pactadas[0] > tope:
            found.append(
                Finding(
                    day=last,
                    employee_id=person.id,
                    code="training_hours_over_the_cap",
                    message=_(
                        "%(agreed)s h agreed against a cap of %(cap)s: art. 11.2.b allows "
                        "%(share)s %% of the %(max)s h maximum working week."
                    )
                    % {
                        "agreed": f"{pactadas[0]:g}",
                        "cap": f"{tope:.1f}",
                        "share": f"{tope_pct:g}",
                        "max": f"{maxima:g}",
                    },
                )
            )
    return found


def _check_remote_work_agreement(company, first, last, employee) -> list[Finding]:
    """Quien pasa del 30 % a distancia y no tiene acuerdo, o lo firmó tarde.

    El art. 1 de la Ley 10/2021 fija **cuándo se aplica**: trabajo a distancia
    de al menos el 30 % de la jornada en un periodo de tres meses. Cruzado ese
    umbral la ley entra entera, y lo primero que exige es acuerdo por escrito y
    **previo** (art. 5.1).

    Son dos avisos y no uno porque son dos incumplimientos distintos: no tener
    acuerdo, y tenerlo firmado después de haber empezado. El segundo se arregla
    de otra manera ---no se puede firmar hacia atrás--- y decir «falta acuerdo»
    a quien tiene uno con la fecha corrida sería mandarle a resolver un problema
    que no es el suyo.

    Las personas salen del registro, como en el tope de complementarias: quien
    teletrabaja no siempre tiene cuadrante.
    """
    from apps.punches.models import WorkMode
    from apps.punches.remote import remote_share
    from apps.users.models import RemoteWorkAgreement, User

    zone = company.tzinfo
    quienes = User.objects.filter(
        tenant=company,
        is_active=True,
        punches__timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        punches__timestamp__lt=datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=zone),
        punches__is_active=True,
        # Solo quien haya marcado algo a distancia. Sin esto habría que hacer la
        # cuenta de los tres meses para toda la plantilla en cada revisión de
        # cuadrante, y la respuesta sería «0 %» para casi todos.
        punches__work_mode=WorkMode.REMOTE,
    ).distinct()
    if employee is not None:
        quienes = quienes.filter(pk=employee.pk)

    found: list[Finding] = []
    for person in quienes:
        cuenta = remote_share(employee=person, company=company, day=last)
        if not cuenta or not cuenta["law_applies"]:
            continue

        acuerdo = (
            RemoteWorkAgreement.objects.filter(employee=person, starts_on__lte=last)
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=last))
            .order_by("-starts_on")
            .first()
        )
        if acuerdo is None:
            found.append(
                Finding(
                    day=last,
                    employee_id=person.id,
                    code="remote_work_without_agreement",
                    message=_(
                        "%(share)s %% of the time worked in the last three months was "
                        "remote, over the %(threshold)s %% that makes Law 10/2021 apply, "
                        "and no agreement is on record."
                    )
                    % {
                        "share": f"{cuenta['share']:g}",
                        "threshold": f"{cuenta['threshold']:g}",
                    },
                )
            )
        elif acuerdo.signed_late:
            found.append(
                Finding(
                    day=last,
                    employee_id=person.id,
                    code="remote_agreement_signed_late",
                    message=_(
                        "The remote work agreement was signed on %(signed)s and the "
                        "remote work began on %(started)s."
                    )
                    % {
                        "signed": acuerdo.signed_on.isoformat(),
                        "started": acuerdo.starts_on.isoformat(),
                    },
                )
            )
    return found


def _check_reduction_within_the_right(company, first, last, employee) -> list[Finding]:
    """Que una reducción por guarda legal quepa en lo que el art. 37.6 concede.

    «Entre, al menos, un octavo y un máximo de la mitad de la duración de la
    jornada»: quien la ejerce sigue trabajando entre el 50 % y el 87,5 %.

    **Avisa, no impide.** El artículo delimita el derecho, no lo que las partes
    pueden acordar: cabe pactar una reducción mayor, y el convenio puede mejorar
    las condiciones. Lo que no cabe es que una reducción del 70 % se registre
    como ejercicio de este derecho y nadie lo mire. La empresa decide; el
    producto pone el dato al lado.
    """
    from apps.absences.models import Absence, AbsenceStatus

    filas = (
        Absence.objects.filter(
            status=AbsenceStatus.APPROVED,
            start_date__lte=last,
            end_date__gte=first,
            reduction_share__isnull=False,
            leave_type__code=GUARDA_LEGAL,
        )
        .exclude(reduction_share__gte=GUARDA_LEGAL_MINIMO, reduction_share__lte=GUARDA_LEGAL_MAXIMO)
        .select_related("employee")
    )
    if employee is not None:
        filas = filas.filter(employee=employee)

    found: list[Finding] = []
    for ausencia in filas:
        cuanto = float(ausencia.reduction_share)
        found.append(
            Finding(
                # El primer día suyo que se ve en la ventana, para que el aviso
                # caiga dentro del cuadrante que se está mirando.
                day=max(ausencia.start_date, first),
                employee_id=ausencia.employee_id,
                code="reduction_outside_the_right",
                message=_(
                    "The working day is cut by %(share)s %%, and art. 37.6 runs from an "
                    "eighth to a half --- between %(min)s %% and %(max)s %%."
                )
                % {
                    "share": f"{cuanto:g}",
                    "min": f"{GUARDA_LEGAL_MINIMO:g}",
                    "max": f"{GUARDA_LEGAL_MAXIMO:g}",
                },
            )
        )
    return found


def _check_complementary_cap(company, complementary, first, last, employee) -> list[Finding]:
    """El tope de horas complementarias del art. 12.5.c, contra el registro.

    El aviso de `_check_weekly_hours` lleva tiempo diciendo que las horas por
    encima del contrato «cuentan para su propio límite», y **ese límite no lo
    llevaba nadie**: era una promesa que el producto hacía y no cumplía.

    Va sobre el periodo del contrato ---semana, mes o año--- y no sobre el mes,
    porque el artículo lo ata a «las horas ordinarias de trabajo objeto del
    contrato» y el objeto se pacta en el cómputo que sea. Ver
    `apps.punches.complementary`.

    Las personas salen del **registro**, no del cuadrante: quien no tiene turnos
    planificados es justo quien más fácilmente se pasa sin que nadie mire, y es
    el agujero que `_check_time_actually_worked` existe para tapar. Repetirlo
    aquí habría dejado fuera al mismo grupo.
    """
    from apps.punches.complementary import complementary_used
    from apps.users.models import HoursPeriod, User, WorkingTimeRegime

    # Donde el marco no define las complementarias, no las hay. La directiva
    # europea no las conoce ---son una construcción del ET--- y emitir aquí un
    # aviso con un porcentaje español sería inventarle a otro país un límite que
    # su ley no tiene.
    if complementary is None:
        return []

    zone = company.tzinfo
    quienes = User.objects.filter(
        # `User.objects` no acota por empresa ---no es un `TenantOwnedModel`--- y
        # el filtro por fichajes tampoco lo hace: el `join` no arrastra el
        # contexto. Sin este `tenant=` la revisión de un cuadrante podía traer a
        # gente del cliente de al lado.
        tenant=company,
        regime=WorkingTimeRegime.PART_TIME,
        is_active=True,
        punches__timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        punches__timestamp__lt=datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=zone),
        punches__is_active=True,
    ).distinct()
    if employee is not None:
        quienes = quienes.filter(pk=employee.pk)

    cuanto_dura = {
        HoursPeriod.WEEK: _("that week"),
        HoursPeriod.MONTH: _("that month"),
        HoursPeriod.YEAR: _("that year"),
    }

    found: list[Finding] = []
    for person in quienes:
        used = complementary_used(employee=person, company=company, day=last)
        if not used or not used["over_the_cap"]:
            continue
        found.append(
            Finding(
                # El último día mirado, que es el que la pantalla tiene a la
                # vista. La ventana del contrato puede ser el año entero y
                # fechar el aviso en enero lo sacaría del cuadrante que se está
                # revisando.
                day=last,
                employee_id=person.id,
                code="complementary_hours_cap",
                message=_(
                    "%(over)s h over the contract %(when)s, and only %(cap)s are allowed: "
                    "%(share)s %% of the %(agreed)s h agreed."
                )
                % {
                    "over": f"{used['complementary_hours']:.1f}",
                    "when": cuanto_dura.get(used["period"], ""),
                    "cap": f"{used['cap_hours']:.1f}",
                    "share": used["share"],
                    "agreed": f"{used['contracted_hours']:g}",
                },
            )
        )
    return found


def _check_time_actually_worked(
    company, rules, first, last, employee, reductions=None
) -> list[Finding]:
    """The same limits, against the record instead of the plan.

    Every other check here reads the roster, and that leaves two holes.

    Somebody with no fixed schedule has no roster at all --- which is right,
    there is nothing to plan --- and so had **no limits check of any kind**. They
    could work sixty hours a week and nothing said a word.

    And for everybody else the roster is a plan. A company that rosters forty
    and works fifty is over the maximum, and art. 34.1 ET is about hours
    actually worked, not hours intended.

    So this reads punches. Weeks only fully inside the window, for the same
    reason as the roster check: a half-counted week reported as an excess sends
    somebody looking for hours that are not there.
    """
    from apps.punches.models import Punch, PunchType

    zone = company.tzinfo
    punches = Punch.objects.filter(
        timestamp__gte=datetime.combine(first, dt_time.min, tzinfo=zone),
        timestamp__lt=datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=zone),
        is_active=True,
    ).select_related("employee")
    if employee is not None:
        punches = punches.filter(employee=employee)

    # Pair each person's events into worked spans. An unclosed one is left out
    # rather than guessed at: inventing an end would put hours in the total that
    # nobody recorded.
    spans: dict = {}
    for punch in punches.order_by("employee_id", "timestamp"):
        bucket = spans.setdefault(
            punch.employee_id, {"person": punch.employee, "open": None, "weeks": {}}
        )
        if punch.punch_type == PunchType.IN:
            bucket["open"] = punch.timestamp
        elif bucket["open"] is not None:
            local = bucket["open"].astimezone(zone)
            year, week, _weekday = local.date().isocalendar()
            hours = (punch.timestamp - bucket["open"]).total_seconds() / 3600
            bucket["weeks"][(year, week)] = bucket["weeks"].get((year, week), 0) + hours
            bucket["open"] = None

    ceiling = float(rules.weekly_hours)
    found = []
    for employee_id, bucket in spans.items():
        person = bucket["person"]
        agreed_pair = person.agreed_hours(rules)
        agreed = agreed_pair[0] if agreed_pair and agreed_pair[1] == "WEEK" else None

        for (year, week), hours in bucket["weeks"].items():
            monday = date.fromisocalendar(year, week, 1)
            if monday < first or monday + timedelta(days=6) > last:
                continue

            # The same reduction the roster check applies, or the two disagree:
            # the roster warned above the reduced contract while this warned
            # only above the full one --- and the hours in between, worked
            # during an ERTE, are exactly the ones an inspection of an ERTE
            # goes looking for. The legal maximum stays put, as everywhere.
            week_agreed = (
                agreed * _reduced_share(person, monday, monday + timedelta(days=6), reductions)
                if agreed is not None
                else None
            )

            if hours > ceiling:
                found.append(
                    Finding(
                        day=monday,
                        employee_id=employee_id,
                        code="worked_over_the_maximum",
                        employee_name=person.get_full_name(),
                        message=_(
                            "%(hours)s h actually worked that week, over the %(limit)s h "
                            "maximum. This is the record, not the roster."
                        )
                        % {"hours": f"{hours:.1f}", "limit": f"{ceiling:g}"},
                    )
                )
            elif week_agreed is not None and hours > week_agreed:
                found.append(
                    Finding(
                        day=monday,
                        employee_id=employee_id,
                        code="worked_over_the_contract",
                        employee_name=person.get_full_name(),
                        message=_("%(hours)s h actually worked against %(agreed)s h contracted.")
                        % {"hours": f"{hours:.1f}", "agreed": f"{week_agreed:g}"},
                    )
                )
    return found


def _check_outside_the_contract(by_person) -> list[Finding]:
    """Somebody rostered on a day their contract does not cover.

    Within one company there will be open-ended contracts, six-month ones and
    permanent-seasonal ones, and a roster drawn a month ahead does not know
    which ended last Friday. Nothing else catches it: the person still exists,
    is still active, and every other check passes happily on a day they are not
    engaged for.

    Y fuera de temporada, para el fijo discontinuo. El filtro de aquí abajo se
    saltaba a quien no tiene ninguna fecha de contrato, que es **justo** el fijo
    discontinuo indefinido: el aviso existía y no llegaba a quien más lo
    necesita. Con periodos de actividad declarados, un turno fuera de ellos es
    exactamente el caso que el art. 16 viene a distinguir.
    """
    found = []
    for _employee_id, roster in by_person.items():
        person = roster[0].employee
        tiene_temporadas = person.seasonal and person.activity_periods.exists()
        if not (person.contract_start or person.contract_end or tiene_temporadas):
            continue
        for shift in roster:
            if person.is_engaged_on(shift.day):
                continue
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="outside_the_season" if tiene_temporadas else "outside_the_contract",
                    message=(
                        _("Rostered outside their periods of activity (art. 16 ET).")
                        if tiene_temporadas
                        else _("Rostered on a day outside the dates of their contract.")
                    ),
                )
            )
    return found


def _check_rostered_on_a_holiday(by_person, first, last) -> list[Finding]:
    """Somebody rostered on a public holiday.

    Not a breach, and the wording says so. Art. 37.2 makes the fourteen days
    non-recoverable and paid, and working one is lawful --- what it generates is
    compensation, in rest or in pay, and which one is the collective agreement's
    business rather than ours.

    It is reported because it is a decision somebody has to have made, and
    because the compensation is owed from the moment the day is worked. The
    roster is where it first becomes visible.

    Which days are holidays depends on the **workplace**: two of the fourteen
    are the town hall's, so a company with sites in two provinces has two
    calendars and one of them is not the other's.
    """
    from apps.tenants.holidays import holidays_by_workplace, holidays_for

    # De una vez y por centro: la respuesta no depende de la persona.
    por_centro = holidays_by_workplace(first, last)

    found = []
    for roster in by_person.values():
        if not roster:
            continue
        person = roster[0].employee
        off = holidays_for(person, first, last, por_centro)
        if not off:
            continue
        for shift in roster:
            if first <= shift.day <= last and shift.day in off:
                found.append(
                    Finding(
                        day=shift.day,
                        employee_id=person.pk,
                        code="rostered_on_a_holiday",
                        message=_(
                            "Rostered on a public holiday. It is allowed, and it earns "
                            "compensation in rest or in pay under the agreement."
                        ),
                    )
                )
    return found


def _check_leave_clashes(first, last, employee) -> list[Finding]:
    """Somebody rostered on a day they have approved leave for.

    The most ordinary planning mistake there is, and the one that reaches the
    worker fastest: they turn up, or they do not and it looks like an absence.
    """
    # Only what stops the whole day. The two kinds this filter excludes are
    # people who are SUPPOSED to be rostered: a part-day absence works the rest
    # of the day, and a reducing suspension (an ERTE at 40 %) works the other
    # 60 % for months. Without it, one person on a partial ERTE produced
    # twenty-one false warnings in a single month --- and a warning that is
    # wrong twenty-three times out of thirty buries the seven that are right.
    absences = Absence.objects.filter(
        status=AbsenceStatus.APPROVED, start_date__lte=last, end_date__gte=first
    ).filter(STOPS_THE_WHOLE_DAY)
    if employee is not None:
        absences = absences.filter(employee=employee)

    found = []
    for absence in absences.select_related("employee"):
        clashing = Shift.objects.filter(
            employee_id=absence.employee_id,
            day__gte=max(absence.start_date, first),
            day__lte=min(absence.end_date, last),
        )
        for shift in clashing:
            found.append(
                Finding(
                    day=shift.day,
                    employee_id=shift.employee_id,
                    code="rostered_on_leave",
                    message=_("Rostered on a day of approved %(kind)s.")
                    % {"kind": absence.get_absence_type_display()},
                )
            )
    return found


# ------------------------------------------------------- roster against reality


@dataclass(frozen=True)
class DayReconciliation:
    """Expected against real for one day, classified, hiding nothing.

    The headline `status` is a best effort at the single most useful label, but
    the three figures below it are the truth and are always filled: a day can be
    late AND run into overtime, and collapsing that to one word would lose one
    of them. Overtime especially is never folded away --- surfacing it is the
    whole point of the exercise, and the reason assisted clock-in must never
    become the "fichaje de horario" that buries it.
    """

    day: date
    has_shift: bool
    state: str  # NOT_STARTED | WORKING | ON_BREAK | OFF
    expected_minutes: int
    worked_minutes: int
    late_minutes: int = 0
    early_minutes: int = 0
    overtime_minutes: int = 0
    status: str = "NO_SHIFT"

    def as_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "has_shift": self.has_shift,
            "state": self.state,
            "expected_minutes": self.expected_minutes,
            "worked_minutes": self.worked_minutes,
            "late_minutes": self.late_minutes,
            "early_minutes": self.early_minutes,
            "overtime_minutes": self.overtime_minutes,
            "status": self.status,
        }


def day_reconciliation(
    *, employee, company, day: date, shift=None, events=None
) -> DayReconciliation:
    """The day as the record holds it, against the day as the roster planned it.

    Never invents time --- it reads what was punched and what was rostered and
    says how they differ. The margins turn a small slip into a variation rather
    than an incident, which is how a company stops fighting every five minutes;
    they do not hide overtime, because overtime is time worked *beyond* the
    expected day plus its margin.
    """
    from apps.punches.services import build_day_status
    from apps.tenants.rules import WorkingTimeRules

    # `shift` se puede pasar hecho. Quien recorre un mes de cuadrante ya lo tiene
    # en la mano, y volver a pedirlo era una consulta por día y persona: en una
    # lectura de horas extra pendientes, doscientas cuarenta y tres.
    if shift is None:
        shift = Shift.objects.filter(employee=employee, day=day).first()
    status = build_day_status(employee, company, day, events=events)
    worked = status.worked_seconds // 60

    if shift is None:
        return DayReconciliation(
            day=day,
            has_shift=False,
            state=status.state,
            expected_minutes=0,
            worked_minutes=worked,
            overtime_minutes=worked,  # unplanned time is all "extra" to the plan
            status="NO_SHIFT",
        )

    rules = WorkingTimeRules.for_company(company)
    zone = employee.tzinfo
    entry_tol = timedelta(minutes=rules.entry_tolerance_minutes)
    exit_tol = timedelta(minutes=rules.exit_tolerance_minutes)

    # The rostered edges, made aware in the person's own zone so they compare
    # against the punches, which are stored in UTC.
    planned_start = shift.starts_at.replace(tzinfo=zone)
    planned_end = shift.ends_at.replace(tzinfo=zone)

    work_spans = [s for s in status.segments if s.interval == "WORK"]
    first_in = min((s.start for s in work_spans), default=None)
    last_out = max((s.end for s in work_spans if s.end is not None), default=None)

    if not status.segments:
        return DayReconciliation(
            day=day,
            has_shift=True,
            state=status.state,
            expected_minutes=shift.minutes,
            worked_minutes=0,
            status="MISSING",
        )

    late = early = overtime = 0
    if first_in is not None:
        lateness = first_in.astimezone(zone) - planned_start
        if lateness > entry_tol:
            late = int(lateness.total_seconds() // 60)

    if status.state in {"WORKING", "ON_BREAK"}:
        status_label = "OPEN"
    else:
        if last_out is not None:
            earliness = planned_end - last_out.astimezone(zone)
            if earliness > exit_tol:
                early = int(earliness.total_seconds() // 60)
        overtime = max(0, worked - shift.minutes)
        # A margin's worth of overtime is the rounding of a normal day, not an
        # extra hour; only what exceeds the tolerance is surfaced as overtime.
        if overtime <= rules.exit_tolerance_minutes:
            overtime = 0

        if overtime:
            status_label = "OVERTIME"
        elif late:
            status_label = "LATE"
        elif early:
            status_label = "LEFT_EARLY"
        else:
            status_label = "OK"

    return DayReconciliation(
        day=day,
        has_shift=True,
        state=status.state,
        expected_minutes=shift.minutes,
        worked_minutes=worked,
        late_minutes=late,
        early_minutes=early,
        overtime_minutes=overtime,
        status=status_label,
    )


def expected_vs_worked(*, employee, company, day: date) -> dict:
    """What was expected against what was recorded, for one day.

    Kept strictly one-directional. The shift never becomes a clock event, and no
    hour is inferred from a roster: a record that filled itself in from the plan
    would be precisely the fiction art. 34.9 ET exists to prevent, and it would
    look identical to a real one.
    """
    from apps.punches.services import build_day_status

    shift = Shift.objects.filter(employee=employee, day=day).first()
    status = build_day_status(employee, company, day)

    expected = shift.minutes if shift else 0
    worked = status.worked_seconds // 60

    return {
        "day": day.isoformat(),
        "expected_minutes": expected,
        "worked_minutes": worked,
        "difference_minutes": worked - expected,
        "has_shift": shift is not None,
        "state": status.state,
    }
