"""Working-time reports.

This is the output the law actually asks for. Article 34.9 requires the daily
record to be kept for four years and to be available to the labour inspectorate,
the workforce and their representatives, so what matters here is not that the
document looks nice: it is that it says who worked, when, for how long, and that
it can be shown not to have been altered afterwards.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.utils.translation import gettext as _

from apps.absences.models import Absence, AbsenceStatus
from apps.common.csv_export import EscritorSeguro
from apps.punches.models import HoursNature, Punch, PunchInterval, PunchSource, PunchType


@dataclass
class DayRow:
    day: date
    entries: list[tuple[datetime, datetime | None]] = field(default_factory=list)
    seconds: int = 0
    incidents: list[str] = field(default_factory=list)
    absence: str | None = None
    delegated: bool = False

    # Art. 3 of the pending decree. Reported apart from the hours, never folded
    # into them: the whole reason a break or a stretch of waiting time is
    # recorded is that it does **not** count as working time.
    breaks: list[tuple[datetime, datetime | None]] = field(default_factory=list)
    break_seconds: int = 0
    standby: list[tuple[datetime, datetime | None]] = field(default_factory=list)
    standby_seconds: int = 0
    overtime_seconds: int = 0
    overtime_settlement: str = ""
    force_majeure_seconds: int = 0
    complementary_seconds: int = 0
    remote: bool = False
    onsite: bool = False

    # Quién registró, y **cuál** de los tres, no «no fue la persona». El modelo
    # los agrupa en `was_delegated` con razón ---para él los tres significan lo
    # mismo--- pero el informe tiene que separarlos: una aplicación fichando en
    # nombre de alguien, la empresa corrigiendo tras el art. 4.b y una
    # importación son tres pruebas distintas.
    corrected: bool = False
    imported: bool = False
    arrangements: list[str] = field(default_factory=list)

    # Art. 4.b. A day whose entries were changed over the person's objection,
    # and what they said. Both, or neither: a report that showed the change
    # without the objection would be hiding the disagreement the article
    # exists to preserve.
    disputed: bool = False
    dissent: list[str] = field(default_factory=list)


@dataclass
class ReportData:
    company_name: str
    company_tax_id: str
    time_zone: str
    employee_name: str
    employee_staff_number: str
    date_from: date
    date_to: date
    rows: list[DayRow]
    total_seconds: int
    generated_at: datetime
    fingerprint: str = ""

    #: Las reglas de cómputo con las que se calculó, impresas en el documento.
    #:
    #: No cambian el resultado: lo explican. Estas reglas se leen del ajuste
    #: **de hoy**, así que cambiarlas reescribe periodos ya cerrados ---medido,
    #: un abril pasaba de 7:00 a 8:00 al marcar que la pausa cuenta como trabajo,
    #: y un turno de noche pasaba de `22:00;06:00;08:00` a «entrada sin salida»
    #: con cero horas al bajar el tope de jornada abierta.
    #:
    #: Que las reglas puedan cambiar es legítimo ---salen del convenio--- y que
    #: el cambio alcance al pasado es lo que no lo es. Arreglarlo de verdad pide
    #: reglas con fechas de vigencia, que es una decisión de producto y está
    #: anotada en el cuaderno. Mientras tanto, al menos el documento dice bajo qué
    #: reglas se emitió, así que dos versiones del mismo mes son comparables en
    #: vez de inexplicables.
    computed_break_counts: bool = False
    computed_max_open_hours: int = 0

    # Art. 3.b: the agreed regime, which is what the hours are measured against.
    regime: str = ""
    contracted_hours: str = ""
    contracted_schedule: str = ""

    # Art. 3.j asks for a daily **and monthly** total. Daily is each row; this
    # is the month, keyed by YYYY-MM.
    monthly_seconds: dict = field(default_factory=dict)
    total_break_seconds: int = 0
    total_standby_seconds: int = 0
    total_overtime_seconds: int = 0


def _add_span(row: DayRow, opening, start: datetime, end: datetime, seconds: int) -> None:
    """Files a closed span under what it actually was.

    Art. 3 wants the working day (3.c), breaks that are not working time (3.d)
    and waiting time (3.g) told apart, plus the nature of the hours (3.f), the
    mode (3.e) and any arrangement (3.i). Keeping them in separate buckets is
    what stops an inspector having to take the total on trust.
    """
    if opening.interval == PunchInterval.BREAK:
        row.breaks.append((start, end))
        row.break_seconds += seconds
        return

    if opening.interval in {PunchInterval.STANDBY, PunchInterval.DISCONNECTION}:
        row.standby.append((start, end))
        row.standby_seconds += seconds
        return

    row.entries.append((start, end))
    row.seconds += seconds

    if opening.work_mode == "REMOTE":
        row.remote = True
    else:
        row.onsite = True

    if opening.hours_nature == HoursNature.OVERTIME:
        row.overtime_seconds += seconds
        if opening.overtime_settlement:
            row.overtime_settlement = opening.get_overtime_settlement_display()
    elif opening.hours_nature == HoursNature.COMPLEMENTARY:
        row.complementary_seconds += seconds

    if opening.force_majeure:
        row.force_majeure_seconds += seconds

    if opening.flexibility_measure:
        label = opening.get_flexibility_measure_display()
        if label not in row.arrangements:
            row.arrangements.append(label)


def _format_hours(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def _agreed_as_text(employee, rules) -> str:
    """The agreed hours as art. 3.b wants them stated.

    The period is spelled out because the number alone is ambiguous: "1700" is
    a year in the gardening agreement and would read as nonsense as a week. And
    the share of a full day only appears for part-time work, which is the only
    regime the article asks it for.
    """
    agreed = employee.agreed_hours(rules)
    if agreed is None:
        return ""

    hours, period = agreed
    labels = {"WEEK": _("a week"), "MONTH": _("a month"), "YEAR": _("a year")}
    text = f"{hours:g} h {labels.get(period, '')}".strip()

    share = employee.share_of_full_time(rules)
    if share is not None and employee.part_time:
        text += f" ({share:g} %)"
    return text


def zone_of(punch, fallback):
    """El huso con el que se grabó ese fichaje, o el de la persona si no lo tiene.

    Los anteriores a que el campo existiera caen al de la persona, que es la
    mejor respuesta disponible para ellos y la que tenían antes.
    """
    import zoneinfo

    guardado = getattr(punch, "time_zone", "")
    if not guardado:
        return fallback
    try:
        return zoneinfo.ZoneInfo(guardado)
    except Exception:
        # Un huso que ya no existe en la base de datos del sistema no puede
        # tumbar el informe del art. 34.9.
        return fallback


def build_report(*, employee, company, date_from: date, date_to: date) -> ReportData:
    """Collect the working days of one person over a period."""
    from django.utils import timezone

    from apps.tenants.rules import WorkingTimeRules

    rules = WorkingTimeRules.for_company(company)
    # Theirs, which is their workplace's or the company's. A record for somebody
    # in Las Palmas rendered in Madrid time would show every day shifted by an
    # hour, and the ones that start before 01:00 on the wrong date entirely.
    #
    # Es el huso de **hoy**, y se usa para elegir los días del periodo y para
    # agrupar. Cada evento se lee además con el que se guardó con él, que es lo
    # que impide que el registro cambie hacia atrás: medido, borrar un centro de
    # trabajo movía una fila de `09:00;17:00` a `10:00;18:00`.
    zone = employee.tzinfo

    # El margen cubre el tope de la empresa y no un día fijo: con guardias de
    # veinticuatro horas una jornada del día anterior al pedido puede terminar
    # dentro, y un día de margen se quedaría corto.
    margen = timedelta(hours=rules.max_open_hours) + timedelta(days=1)
    punches = list(
        Punch.objects.filter(
            employee=employee,
            is_active=True,
            timestamp__gte=datetime.combine(date_from, time.min, tzinfo=zone) - margen,
            timestamp__lt=datetime.combine(date_to, time.min, tzinfo=zone)
            + timedelta(days=1)
            + margen,
        ).order_by("timestamp")
    )

    absences = list(
        Absence.objects.filter(
            employee=employee,
            status=AbsenceStatus.APPROVED,
            start_date__lte=date_to,
            end_date__gte=date_from,
        )
    )

    # Por jornadas, no por días naturales. Agrupar por el día local de cada
    # fichaje ---que es lo que hacía, con un comentario diciendo que así se
    # arreglaba el turno de noche--- parte la jornada de quien entra a las 22:00
    # y sale a las 06:00: dos horas en un día, seis en el siguiente, y el
    # informe que se entrega a una inspección dice que trabajó dos días. El
    # porqué, con los artículos, en `apps.punches.workday`.
    from apps.punches.workday import assign_workdays

    de_quien = assign_workdays(punches, employee, max_open_hours=rules.max_open_hours)
    by_day: dict[date, list[Punch]] = {}
    #: Los días en los que algún fichaje ya no cuadra con su propio sello.
    #:
    #: El sello se calculaba y se guardaba desde el principio, y **nadie lo
    #: comprobaba**: `verify_hash` solo se llamaba desde las pruebas. Medido:
    #: adelantando dos horas un fichaje por SQL directo ---la API no deja editar
    #: uno, las correcciones crean otro y anulan el viejo--- el informe pasaba
    #: de ocho horas a diez y se generaba sin una queja.
    #:
    #: Se comprueba aquí porque este es el momento en que el registro sale del
    #: sistema como prueba. La huella del documento no sirve para esto: certifica
    #: que el papel entregado es el que se generó, no que lo que se generó
    #: refleje lo que se fichó. Y sale gratis: los fichajes ya están cargados y
    #: es un sha256 por fila.
    #:
    #: Lo que se hace es **decirlo**, no ocultar la fila ni corregir la cifra.
    #: Quien lee el informe tiene que poder ver que ese día no es de fiar; el
    #: dato es el que hay en el registro y no nos toca a nosotros enmendarlo.
    sellos_rotos: set[date] = set()
    for punch in punches:
        jornada = de_quien.get(punch.id)
        if jornada is not None and date_from <= jornada <= date_to:
            by_day.setdefault(jornada, []).append(punch)
            if not punch.verify_hash():
                sellos_rotos.add(jornada)

    rows: list[DayRow] = []
    total = 0
    monthly: dict[str, int] = {}

    # Corrections applied without the person's agreement, by the day they
    # concern. Art. 4.b: the modification and the disagreement travel together.
    from apps.punches.corrections import CorrectionStatus, PunchCorrection

    disputes: dict = {}
    imposed_on = PunchCorrection.objects.filter(
        employee=employee, status=CorrectionStatus.DISPUTED
    ).select_related("target", "result")
    for imposed in imposed_on:
        moment = imposed.proposed_timestamp or (
            imposed.target.timestamp if imposed.target else None
        )
        if moment is None:
            continue
        day_of = moment.astimezone(zone).date()
        if date_from <= day_of <= date_to:
            disputes.setdefault(day_of, []).append(imposed)

    current = date_from
    while current <= date_to:
        row = DayRow(day=current)

        for absence in absences:
            if absence.start_date <= current <= absence.end_date:
                row.absence = absence.get_absence_type_display()
                break

        for imposed in disputes.get(current, []):
            row.disputed = True
            if imposed.employee_dissent:
                row.dissent.append(imposed.employee_dissent)

        events = by_day.get(current, [])
        # One opening per kind of span: a break runs inside the working day, so
        # a single cursor would close the day when the break starts.
        open_by_interval: dict = {}

        for event in events:
            if event.source == PunchSource.ADMIN:
                row.corrected = True
            elif event.source == PunchSource.IMPORT:
                row.imported = True
            elif event.was_delegated:
                row.delegated = True
            local = event.timestamp.astimezone(zone_of(event, zone))
            kind = event.interval

            if event.punch_type == PunchType.IN:
                if kind in open_by_interval:
                    if kind == PunchInterval.WORK:
                        row.incidents.append(_("two entries with no exit in between"))
                    continue
                open_by_interval[kind] = (local, event)
                continue

            if kind not in open_by_interval:
                if kind == PunchInterval.WORK:
                    row.incidents.append(_("exit with no matching entry"))
                continue

            start, opening = open_by_interval.pop(kind)
            seconds = int((local - start).total_seconds())
            _add_span(row, opening, start, local, seconds)

        for kind, (start, _opening) in open_by_interval.items():
            if kind == PunchInterval.WORK:
                row.entries.append((start, None))
                row.incidents.append(_("entry with no exit"))
            elif kind == PunchInterval.BREAK:
                row.breaks.append((start, None))
                row.incidents.append(_("break with no end"))
            else:
                row.standby.append((start, None))

        # A break happens inside the day, so its time comes off the total ---
        # unless the agreement says otherwise. Art. 34.4 ET makes it working
        # time only when the agreement or the contract says so, and that answer
        # lives in the company's rules, not here. `build_day_status` asks the
        # same question, and the two must agree: the figure on screen and the
        # figure in the document are the same day.
        if not rules.break_counts_as_work:
            row.seconds = max(row.seconds - row.break_seconds, 0)

        # Al final, y con las horas ya sumadas: la cifra es la que hay en el
        # registro. Lo que se añade es el aviso de que ese día no cuadra con su
        # propio sello, para que quien lo lee no lo dé por bueno.
        if current in sellos_rotos:
            row.incidents.append(
                _("an entry no longer matches its integrity seal: it was altered outside the app")
            )

        total += row.seconds
        month = current.strftime("%Y-%m")
        monthly[month] = monthly.get(month, 0) + row.seconds
        rows.append(row)
        current += timedelta(days=1)

    data = ReportData(
        company_name=company.name,
        company_tax_id=company.tax_id,
        time_zone=company.time_zone,
        computed_break_counts=rules.break_counts_as_work,
        computed_max_open_hours=rules.max_open_hours,
        employee_name=employee.get_full_name(),
        employee_staff_number=employee.employee_id or "",
        date_from=date_from,
        date_to=date_to,
        rows=rows,
        total_seconds=total,
        generated_at=timezone.now(),
        regime=employee.get_regime_display(),
        # Art. 3.b asks for the agreed hours and, when part time, the share of a
        # full day. Both from the same source so they cannot disagree.
        contracted_hours=_agreed_as_text(employee, rules),
        contracted_schedule=employee.contracted_schedule,
        monthly_seconds=monthly,
        total_break_seconds=sum(r.break_seconds for r in rows),
        total_standby_seconds=sum(r.standby_seconds for r in rows),
        total_overtime_seconds=sum(r.overtime_seconds for r in rows),
    )
    data.fingerprint = _fingerprint(data)
    return data


def _fingerprint(data: ReportData) -> str:
    """Fingerprint of the report's content.

    Lets anyone check later that the document handed over is the one that was
    generated. Deliberately excludes the generation time, so regenerating the
    same period yields the same fingerprint and two copies can be compared.
    """
    parts = [data.company_tax_id, data.employee_name, str(data.date_from), str(data.date_to)]
    for row in data.rows:
        for entry, exit_ in row.entries:
            parts.append(f"{row.day}|{entry.isoformat()}|{exit_.isoformat() if exit_ else ''}")
        # Breaks and waiting time are in the document, so they are in the
        # fingerprint. Leaving them out would let somebody change what a span
        # was without the seal noticing.
        for start, end in row.breaks:
            parts.append(f"{row.day}|B|{start.isoformat()}|{end.isoformat() if end else ''}")
        for start, end in row.standby:
            parts.append(f"{row.day}|S|{start.isoformat()}|{end.isoformat() if end else ''}")
        parts.append(f"{row.day}|{row.seconds}|{row.overtime_seconds}")

        # Y lo que la fila **dice**, no solo lo que dura. El principio ya estaba
        # escrito tres líneas más arriba ---«están en el documento, así que están
        # en la huella»--- y se aplicaba a la mitad: la ausencia y las
        # observaciones salen impresas y no entraban.
        #
        # Lo grave era la discrepancia del art. 4.b. Dos informes del mismo
        # periodo, uno con una corrección impuesta sobre la objeción de la
        # persona y otro sin ella, daban **la misma huella**. El sello promete
        # que el documento entregado es el que se generó, y no lo cubría justo
        # en la parte que más peso tiene.
        #
        # Se sellan las notas ya montadas y no cada campo suelto: así lo que se
        # añada mañana al documento entra en el sello sin que nadie se acuerde.
        # El texto va traducido, así que se sella la marca y no la frase ---la
        # misma jornada en catalán y en castellano es el mismo hecho---.
        if row.absence:
            parts.append(f"{row.day}|A|{row.absence}")
        if row.disputed:
            parts.append(f"{row.day}|D|{'|'.join(row.dissent)}")
        if row.incidents or row.delegated or row.corrected or row.imported:
            parts.append(
                f"{row.day}|N|{len(row.incidents)}"
                f"|{int(row.delegated)}{int(row.corrected)}{int(row.imported)}"
            )

    parts.append(str(data.total_seconds))
    parts.append(f"{data.total_break_seconds}|{data.total_standby_seconds}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------- CSV


def day_notes(row: DayRow) -> str:
    """Notes for one day: incidents, delegation, y la discrepancia del art. 4.b.

    Delegation is stated in both outputs, and it is stated here rather than in
    each renderer so the two cannot drift apart -- which they already did once,
    with the PDF saying it and the CSV keeping quiet.

    La discrepancia se añadió aquí por lo mismo, y porque **no estaba en
    ninguno de los dos**. `build_report` calculaba `row.disputed` y
    `row.dissent`, y los dos renderizadores los ignoraban: la corrección
    impuesta sobre la objeción de la persona salía en el informe exactamente
    igual que una aceptada.

    Eso es justo lo que el art. 4.b existe para impedir. El propio código lo
    tenía escrito en dos sitios ---«it travels to the inspection report: a
    reader has to be able to tell a correction both parties accepted from one
    imposed over an objection», y «the modification and the disagreement travel
    together»--- y no viajaba.
    """
    notes = list(row.incidents)
    if row.delegated:
        notes.append(_("recorded by an application on the person's behalf"))
    if row.corrected:
        # Un día con una corrección aplicada lleva marca, que es lo que el manual
        # promete ---«los días con eventos corregidos van señalados»--- y lo que
        # antes solo pasaba si además había discrepancia.
        notes.append(_("corrected by the company"))
    if row.imported:
        notes.append(_("imported from another system"))
    if row.disputed:
        # Primero la marca, y después lo que dijo la persona. Sin la marca, un
        # día sin texto de discrepancia ---puede no haberlo escrito--- se leería
        # como un día normal.
        notes.append(_("changed without the person's agreement (art. 4.b)"))
        notes.extend(row.dissent)
    return "; ".join(str(n) for n in notes)


def to_csv(data: ReportData) -> str:
    buffer = io.StringIO()
    # `lineterminator` explícito: `csv.writer` pone «\r\n» por defecto ---lo que
    # dice la RFC 4180--- y eso llena el fichero de «^M» en cualquier editor de
    # Unix. Molesto a la vista, pero lo que de verdad importa es que el «\r» se
    # queda **pegado a la última columna** de cada línea: un `awk -F";"` o un
    # `split(";")` de andar por casa devuelve «05:00\r» donde esperaba «05:00»,
    # y eso no se ve hasta que alguien compara horas y no le cuadran.
    #
    # Excel y LibreOffice abren las dos formas igual de bien, así que no se
    # pierde nada. Reportado el 13/08/2026.
    # Seguro: el nombre de una persona y la discrepancia del art. 4.b son texto
    # libre, y este fichero se abre en Excel. Ver `apps/common/csv_export.py`.
    writer = EscritorSeguro(buffer, delimiter=";", lineterminator="\n")

    writer.writerow([_("Working time record")])
    writer.writerow([_("Company"), data.company_name, _("Tax number"), data.company_tax_id])
    writer.writerow(
        [_("Employee"), data.employee_name, _("Staff number"), data.employee_staff_number]
    )
    writer.writerow(
        [_("Period"), f"{data.date_from} — {data.date_to}", _("Time zone"), data.time_zone]
    )
    # Las reglas con las que se calculó: sin ellas, dos versiones del mismo mes
    # con cifras distintas no se pueden explicar.
    writer.writerow(
        [
            # Sin «sí/no»: una cadena de una palabra la traduce cada idioma
            # por su cuenta y acaba prestada de otro contexto ---«no» venía
            # traducido como «nota». La frase entera no tiene ese problema.
            _("Break"),
            _("counts as working time")
            if data.computed_break_counts
            else _("does not count as working time"),
            _("Maximum open day (hours)"),
            data.computed_max_open_hours,
        ]
    )
    writer.writerow([])
    writer.writerow([_("Date"), _("Entry"), _("Exit"), _("Hours"), _("Notes")])

    for row in data.rows:
        if not row.entries and not row.absence:
            continue
        if row.absence and not row.entries:
            writer.writerow([row.day.isoformat(), "", "", "00:00", row.absence])
            continue
        for index, (entry, exit_) in enumerate(row.entries):
            writer.writerow(
                [
                    row.day.isoformat() if index == 0 else "",
                    entry.strftime("%H:%M"),
                    exit_.strftime("%H:%M") if exit_ else "",
                    _format_hours(row.seconds) if index == 0 else "",
                    day_notes(row) if index == 0 else "",
                ]
            )

    writer.writerow([])
    writer.writerow([_("Total"), _format_hours(data.total_seconds)])
    # Aparte del total y no dentro: ver el comentario en `pdf.py`. Los dos
    # formatos lo dicen igual porque el informe es el mismo documento en dos
    # envases, y que uno cuente algo que el otro calla ya pasó una vez.
    if data.total_break_seconds:
        writer.writerow(
            [_("Breaks, not counted as working time"), _format_hours(data.total_break_seconds)]
        )
    if data.total_standby_seconds:
        writer.writerow(
            [
                _("Waiting time, not counted as working time"),
                _format_hours(data.total_standby_seconds),
            ]
        )
    writer.writerow([_("Generated"), data.generated_at.isoformat()])
    writer.writerow([_("Verification hash"), data.fingerprint])

    return buffer.getvalue()
