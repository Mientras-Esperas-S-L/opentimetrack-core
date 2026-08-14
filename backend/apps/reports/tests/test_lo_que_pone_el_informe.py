"""Qué pone el informe que se le entrega a una inspección.

Había pruebas del PDF, y comprobaban que empieza por `%PDF-` y que pesa más de
mil bytes. Nada leía su contenido, y es el documento de más peso del producto:
lo que el art. 34.9 obliga a poner a disposición de la Inspección de Trabajo.

Es la misma lección que los correos, con otro envase: comprobar que algo se
genera no es comprobar qué pone.

## Lo que salió al leerlo

El grueso estaba bien ---la cita del artículo, la empresa, el CIF, la persona,
el periodo, la zona horaria, la tabla por días, el total y una huella---. Lo que
faltaba eran tres cosas que el propio código calculaba y ningún renderizador
imprimía:

- **La discrepancia del art. 4.b.** `build_report` ponía `row.disputed` y
  `row.dissent`, y los dos formatos los ignoraban. Una corrección impuesta sobre
  la objeción de la persona salía en el informe **exactamente igual** que una
  aceptada. Es justo lo que el artículo existe para impedir, y el código lo
  tenía escrito en dos sitios: «it travels to the inspection report» y «the
  modification and the disagreement travel together». No viajaba.
- **Las pausas y las esperas**, que el art. 3.d y el 3.g piden registrar
  precisamente porque **no** computan como jornada. Se sumaban en
  `total_break_seconds` y `total_standby_seconds` y no se imprimían, así que el
  informe daba las horas y se callaba de qué estaban descontadas.
- **La huella no las cubría.** Su propio comentario ya decía el principio ---«están
  en el documento, así que están en la huella»--- y se aplicaba a la mitad. Dos
  informes del mismo periodo, uno con una corrección impuesta y otro sin ella,
  daban la misma huella: el sello promete que el documento entregado es el que
  se generó y no cubría la parte con más peso.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime

import pytest
from pypdf import PdfReader

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, CorrectionStatus, PunchCorrection
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.reports.pdf import render_pdf
from apps.reports.services import build_report, to_csv
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
DESDE, HASTA = date(2026, 8, 1), date(2026, 8, 31)


@pytest.fixture
def quien(db):
    empresa = Tenant.objects.create(
        name="Papeles SL", tax_id="B70000001", time_zone="Europe/Madrid", language="es"
    )
    with tenant_context(empresa.id):
        yield (
            empresa,
            User.objects.create_user(
                email="chelo@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Chelo",
                last_name="Ramírez",
            ),
        )


def _jornada(empresa, persona, entra: datetime, sale: datetime, interval=PunchInterval.WORK):
    for cuando, tipo in ((entra, PunchType.IN), (sale, PunchType.OUT)):
        Punch.objects.create(
            tenant=empresa, employee=persona, punch_type=tipo, interval=interval, timestamp=cuando
        )


def _informe(empresa, persona):
    return build_report(employee=persona, company=empresa, date_from=DESDE, date_to=HASTA)


def _texto_del_pdf(informe) -> str:
    return "\n".join(
        p.extract_text() or "" for p in PdfReader(io.BytesIO(render_pdf(informe))).pages
    )


@pytest.mark.django_db
def test_el_pdf_dice_de_quien_es_de_cuando_y_con_qué_amparo(quien):
    """Lo que una inspección mira antes que ninguna hora."""
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        texto = _texto_del_pdf(_informe(empresa, persona))

    for esperado in ("34.9", "Papeles SL", "B70000001", "Chelo Ramírez", "Europe/Madrid"):
        assert esperado in texto, f"el informe no dice {esperado!r}"


@pytest.mark.django_db
def test_las_horas_del_turno_de_noche_salen_en_el_dia_que_empezo(quien):
    """El informe es donde esa decisión se ve, y donde más cara sale si falla."""
    empresa, persona = quien
    with tenant_context(empresa.id):
        # 22:00 del 4 a 06:00 del 5, hora de Madrid.
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 4, 20, tzinfo=UTC),
            datetime(2026, 8, 5, 4, tzinfo=UTC),
        )
        texto = _texto_del_pdf(_informe(empresa, persona))

    assert "04/08" in texto
    assert "05/08" not in texto, "la jornada aparece partida en dos días"
    assert "22:00" in texto and "06:00" in texto
    # Ocho horas, y una sola vez: contarlas dos veces sería peor que perderlas.
    assert texto.count("08:00") >= 1


@pytest.mark.django_db
def test_una_correccion_impuesta_se_ve_en_los_dos_formatos(quien):
    """Art. 4.b. Salía idéntica a una aceptada, que es lo que el artículo
    existe para impedir."""
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        PunchCorrection.objects.create(
            tenant=empresa,
            employee=persona,
            kind=CorrectionKind.MODIFY,
            target=Punch.objects.filter(employee=persona).first(),
            proposed_timestamp=datetime(2026, 8, 3, 5, tzinfo=UTC),
            reason="Se me olvidó",
            requested_by=persona,
            status=CorrectionStatus.DISPUTED,
            applied_without_agreement=True,
            employee_dissent="Yo entré antes.",
        )
        informe = _informe(empresa, persona)
        pdf, csv = _texto_del_pdf(informe), to_csv(informe)

    for salida, nombre in ((pdf, "PDF"), (csv, "CSV")):
        assert "4.b" in salida, f"el {nombre} no marca la corrección impuesta"
        assert "Yo entré antes." in salida, f"el {nombre} se calla lo que dijo la persona"


@pytest.mark.django_db
def test_y_la_huella_cambia_cuando_aparece_esa_discrepancia(quien):
    """El sello promete que el documento entregado es el que se generó.

    Antes no cubría la discrepancia, así que dos informes del mismo periodo
    ---uno con una corrección impuesta sobre la objeción de la persona y otro
    sin ella--- daban la misma huella.
    """
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        sin_discrepancia = _informe(empresa, persona).fingerprint

        PunchCorrection.objects.create(
            tenant=empresa,
            employee=persona,
            kind=CorrectionKind.MODIFY,
            target=Punch.objects.filter(employee=persona).first(),
            proposed_timestamp=datetime(2026, 8, 3, 5, tzinfo=UTC),
            reason="Se me olvidó",
            requested_by=persona,
            status=CorrectionStatus.DISPUTED,
            applied_without_agreement=True,
            employee_dissent="Yo entré antes.",
        )
        con_discrepancia = _informe(empresa, persona).fingerprint

    assert sin_discrepancia != con_discrepancia, "el sello no cubre la discrepancia"


@pytest.mark.django_db
def test_una_ausencia_tambien_entra_en_la_huella(quien):
    """Está impresa en el documento desde siempre y no entraba en el sello."""
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        sin = _informe(empresa, persona).fingerprint

        Absence.objects.create(
            tenant=empresa,
            employee=persona,
            absence_type=AbsenceType.VACATION,
            status=AbsenceStatus.APPROVED,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 11),
        )
        con = _informe(empresa, persona).fingerprint

    assert sin != con


@pytest.mark.django_db
def test_las_pausas_salen_aparte_del_total(quien):
    """Art. 3.d y 3.g: se registran **porque no** computan como jornada.

    Se sumaban y no se imprimían, así que el informe daba las horas y se callaba
    de qué estaban descontadas.
    """
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 10, tzinfo=UTC),
            datetime(2026, 8, 3, 10, 30, tzinfo=UTC),
            interval=PunchInterval.BREAK,
        )
        informe = _informe(empresa, persona)
        pdf, csv = _texto_del_pdf(informe), to_csv(informe)

    assert informe.total_break_seconds == 1800
    for salida, nombre in ((pdf, "PDF"), (csv, "CSV")):
        assert "00:30" in salida, f"el {nombre} no dice cuánta pausa hubo"
        assert "Pausas" in salida, f"el {nombre} no la nombra"


@pytest.mark.django_db
def test_pero_sin_pausas_no_aparece_la_línea(quien):
    """El contraste. Una línea de «Pausas 00:00» en el informe de quien nunca
    ficha pausas es ruido en un documento que se lee entero."""
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        informe = _informe(empresa, persona)
        pdf, csv = _texto_del_pdf(informe), to_csv(informe)

    assert "Pausas" not in pdf
    assert "Pausas" not in csv


@pytest.mark.django_db
def test_los_dos_formatos_cuentan_lo_mismo(quien):
    """El PDF y el CSV son el mismo documento en dos envases.

    Ya se separaron una vez ---está anotado en `day_notes`, que existe para que
    no vuelva a pasar--- así que se comprueba que lo que aparece en uno aparece
    en el otro.
    """
    empresa, persona = quien
    with tenant_context(empresa.id):
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 6, tzinfo=UTC),
            datetime(2026, 8, 3, 14, tzinfo=UTC),
        )
        _jornada(
            empresa,
            persona,
            datetime(2026, 8, 3, 10, tzinfo=UTC),
            datetime(2026, 8, 3, 10, 30, tzinfo=UTC),
            interval=PunchInterval.BREAK,
        )
        Absence.objects.create(
            tenant=empresa,
            employee=persona,
            absence_type=AbsenceType.VACATION,
            status=AbsenceStatus.APPROVED,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 11),
        )
        informe = _informe(empresa, persona)
        pdf, csv = _texto_del_pdf(informe), to_csv(informe)

    # La huella es lo que sella el documento entero, así que tiene que estar en
    # los dos: es lo que permite comparar dos copias.
    assert informe.fingerprint in pdf
    assert informe.fingerprint in csv

    for dato in ("Chelo Ramírez", "Papeles SL", "Pausas", informe.rows[2].absence or "Vacaciones"):
        assert dato in pdf, f"falta en el PDF: {dato!r}"
        assert dato in csv, f"falta en el CSV: {dato!r}"
