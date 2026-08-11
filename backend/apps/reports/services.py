"""Working-time reports.

This is the output the law actually asks for. Article 34.9 requires the daily
record to be kept for four years and to be available to the labour inspectorate,
the workforce and their representatives, so what matters here is not that the
document looks nice: it is that it says who worked, when, for how long, and that
it can be shown not to have been altered afterwards.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.utils.translation import gettext as _

from apps.absences.models import Absence, AbsenceStatus
from apps.punches.models import Punch, PunchType


@dataclass
class DayRow:
    day: date
    entries: list[tuple[datetime, datetime | None]] = field(default_factory=list)
    seconds: int = 0
    incidents: list[str] = field(default_factory=list)
    absence: str | None = None
    delegated: bool = False


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


def _format_hours(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def build_report(*, employee, company, date_from: date, date_to: date) -> ReportData:
    """Collect the working days of one person over a period."""
    from django.utils import timezone

    zone = company.tzinfo

    punches = list(
        Punch.objects.filter(
            employee=employee,
            is_active=True,
            timestamp__date__gte=date_from - timedelta(days=1),
            timestamp__date__lte=date_to + timedelta(days=1),
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

    # Group by *local* day: the boundary of a working day is a local matter, and
    # grouping by UTC would file a night shift under the wrong date.
    by_day: dict[date, list[Punch]] = {}
    for punch in punches:
        local_day = punch.timestamp.astimezone(zone).date()
        if date_from <= local_day <= date_to:
            by_day.setdefault(local_day, []).append(punch)

    rows: list[DayRow] = []
    total = 0

    current = date_from
    while current <= date_to:
        row = DayRow(day=current)

        for absence in absences:
            if absence.start_date <= current <= absence.end_date:
                row.absence = absence.get_absence_type_display()
                break

        events = by_day.get(current, [])
        open_entry: datetime | None = None

        for event in events:
            if event.was_delegated:
                row.delegated = True
            local = event.timestamp.astimezone(zone)
            if event.punch_type == PunchType.IN:
                if open_entry is not None:
                    row.incidents.append(_("two entries with no exit in between"))
                open_entry = local
            else:
                if open_entry is None:
                    row.incidents.append(_("exit with no matching entry"))
                    continue
                row.entries.append((open_entry, local))
                row.seconds += int((local - open_entry).total_seconds())
                open_entry = None

        if open_entry is not None:
            row.entries.append((open_entry, None))
            row.incidents.append(_("entry with no exit"))

        total += row.seconds
        rows.append(row)
        current += timedelta(days=1)

    data = ReportData(
        company_name=company.name,
        company_tax_id=company.tax_id,
        time_zone=company.time_zone,
        employee_name=employee.get_full_name(),
        employee_staff_number=employee.employee_id or "",
        date_from=date_from,
        date_to=date_to,
        rows=rows,
        total_seconds=total,
        generated_at=timezone.now(),
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
        parts.append(f"{row.day}|{row.seconds}")
    parts.append(str(data.total_seconds))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------- CSV


def to_csv(data: ReportData) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")

    writer.writerow([_("Working time record")])
    writer.writerow([_("Company"), data.company_name, _("Tax number"), data.company_tax_id])
    writer.writerow(
        [_("Employee"), data.employee_name, _("Staff number"), data.employee_staff_number]
    )
    writer.writerow(
        [_("Period"), f"{data.date_from} — {data.date_to}", _("Time zone"), data.time_zone]
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
                    "; ".join(row.incidents) if index == 0 else "",
                ]
            )

    writer.writerow([])
    writer.writerow([_("Total"), _format_hours(data.total_seconds)])
    writer.writerow([_("Generated"), data.generated_at.isoformat()])
    writer.writerow([_("Verification hash"), data.fingerprint])

    return buffer.getvalue()
