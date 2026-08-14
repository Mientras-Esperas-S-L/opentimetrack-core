"""PDF rendering of the working-time report.

Plain on purpose. This document may end up in an inspection file, so it is built
to be read and checked, not to look like a brochure: every figure visible, the
verification hash on the page, and nothing that could be mistaken for decoration.
"""

from __future__ import annotations

import io

from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.reports.services import ReportData, _format_hours, day_notes

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5f6b66")
RULE = colors.HexColor("#c8d0cc")
BAND = colors.HexColor("#f0f3f1")


def render_pdf(data: ReportData) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{_('Working time record')} — {data.employee_name}",
        author=data.company_name,
    )

    sheet = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1",
        parent=sheet["Title"],
        fontSize=15,
        leading=19,
        alignment=0,
        textColor=INK,
        spaceAfter=2,
    )
    small = ParagraphStyle("small", parent=sheet["Normal"], fontSize=8, leading=11, textColor=MUTED)

    story = [
        Paragraph(_("Working time record"), h1),
        Paragraph(
            _("Article 34.9 of the Spanish Workers' Statute (Royal Decree-Law 8/2019)"), small
        ),
        Spacer(1, 8 * mm),
    ]

    header = Table(
        [
            [_("Company"), data.company_name, _("Tax number"), data.company_tax_id],
            [
                _("Employee"),
                data.employee_name,
                _("Staff number"),
                data.employee_staff_number or "—",
            ],
            [
                _("Period"),
                f"{data.date_from:%d/%m/%Y} — {data.date_to:%d/%m/%Y}",
                _("Time zone"),
                data.time_zone,
            ],
        ],
        colWidths=[24 * mm, 68 * mm, 26 * mm, 56 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8),
                ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8),
                ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                ("FONT", (3, 0), (3, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
            ]
        )
    )
    story += [header, Spacer(1, 6 * mm)]

    rows = [[_("Date"), _("Entry"), _("Exit"), _("Hours"), _("Notes")]]
    for row in data.rows:
        if not row.entries and not row.absence:
            continue

        notes = day_notes(row)

        if row.absence and not row.entries:
            rows.append([f"{row.day:%d/%m}", "—", "—", "00:00", row.absence])
            continue

        for index, (entry, exit_) in enumerate(row.entries):
            rows.append(
                [
                    f"{row.day:%d/%m}" if index == 0 else "",
                    entry.strftime("%H:%M"),
                    exit_.strftime("%H:%M") if exit_ else "—",
                    _format_hours(row.seconds) if index == 0 else "",
                    notes if index == 0 else "",
                ]
            )

    if len(rows) == 1:
        rows.append([_("No records in this period"), "", "", "", ""])

    table = Table(rows, colWidths=[22 * mm, 22 * mm, 22 * mm, 22 * mm, 86 * mm], repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("ALIGN", (1, 0), (3, -1), "CENTER"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for index in range(1, len(rows)):
        if index % 2 == 0:
            style.append(("BACKGROUND", (0, index), (-1, index), BAND))
    table.setStyle(TableStyle(style))
    story += [table, Spacer(1, 5 * mm)]

    # Las pausas y las esperas van **aparte** del total y no dentro, que es la
    # razón entera de registrarlas: el art. 3.d pide las interrupciones que no
    # son tiempo efectivo y el 3.g las esperas, precisamente porque no cuentan
    # como jornada. Se calculaban desde el principio y no se imprimían en
    # ninguno de los dos formatos, así que el informe decía las horas y se
    # callaba de qué estaban descontadas.
    #
    # Solo se enseñan cuando las hay: una línea de «Pausas 00:00» en el informe
    # de quien nunca ficha pausas es ruido en un documento que se lee entero.
    lineas = [[_("Total for the period"), _format_hours(data.total_seconds)]]
    if data.total_break_seconds:
        lineas.append(
            [_("Breaks, not counted as working time"), _format_hours(data.total_break_seconds)]
        )
    if data.total_standby_seconds:
        lineas.append(
            [
                _("Waiting time, not counted as working time"),
                _format_hours(data.total_standby_seconds),
            ]
        )

    total = Table(lineas, colWidths=[132 * mm, 42 * mm])
    total.setStyle(
        TableStyle(
            [
                # En negrita solo el total; lo que se descuenta va debajo y en
                # normal, porque es subordinado y competir en peso con la cifra
                # principal es lo que hace que un documento no se lea.
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                # Todas las filas, no solo la primera: el rango iba fijo a
                # `(1, 0)` porque antes solo había una.
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [total, Spacer(1, 8 * mm)]

    story += [
        Paragraph(
            _(
                "Times are recorded by the server, never by the device that requested them, "
                "and are shown in the time zone stated above."
            ),
            small,
        ),
        Spacer(1, 2 * mm),
        Paragraph(f"{_('Generated')}: {data.generated_at:%d/%m/%Y %H:%M} UTC", small),
        Paragraph(f"{_('Verification hash')}: {data.fingerprint}", small),
    ]

    document.build(story)
    return buffer.getvalue()
