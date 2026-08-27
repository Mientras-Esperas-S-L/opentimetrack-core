"""Un día con ausencia aprobada en el que además se fichó.

Pasa, y no es raro: a alguien de vacaciones lo llaman y viene. El sistema lo
sabía --- `build_report` rellena `row.absence` --- y el documento salía **idéntico
a un día ordinario**: las horas, y la casilla de observaciones vacía.

El documento ya había decidido que las ausencias constan en él: un día de
vacaciones sin fichajes sale con «Vacaciones» en su columna. Dejaba de decirlo
justo cuando coincide con trabajo, que es el caso que hay que poder ver --- el que
explica por qué se trabajó un día dado por libre, y el que la persona necesita
para reclamar si le descuentan el día y además vino.

Es el mismo patrón que este fichero ya arregló una vez con la discrepancia del
art. 4.b: un dato que `build_report` calculaba y que los dos renderizadores
ignoraban.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime

import pytest
from pypdf import PdfReader

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.reports.pdf import render_pdf
from apps.reports.services import build_report, to_csv
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
DIA = date(2026, 8, 12)


def _texto_pdf(crudo: bytes) -> str:
    return " ".join(p.extract_text() for p in PdfReader(io.BytesIO(crudo)).pages).replace("\n", " ")


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Choque SL", tax_id="B45454545", time_zone="Europe/Madrid")


def _persona(empresa, correo):
    return User.objects.create_user(
        email=correo, password=PASSWORD, tenant=empresa, first_name="Cho", last_name="Que"
    )


def _ficha(empresa, quien):
    for hora, tipo in ((8, PunchType.IN), (13, PunchType.OUT)):
        Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type=tipo,
            interval=PunchInterval.WORK,
            timestamp=datetime(2026, 8, 12, hora - 2, tzinfo=UTC),
        )


def _vacaciones(empresa, quien):
    Absence.objects.create(
        tenant=empresa,
        employee=quien,
        absence_type=AbsenceType.VACATION,
        start_date=DIA,
        end_date=DIA,
        status=AbsenceStatus.APPROVED,
    )


def _informe(empresa, quien):
    return build_report(employee=quien, company=empresa, date_from=DIA, date_to=DIA)


@pytest.mark.django_db
def test_el_documento_dice_que_ese_dia_habia_una_ausencia(empresa):
    with tenant_context(empresa.id):
        quien = _persona(empresa, "ambos@example.com")
        _vacaciones(empresa, quien)
        _ficha(empresa, quien)
        informe = _informe(empresa, quien)
        csv = to_csv(informe)
        pdf = _texto_pdf(render_pdf(informe))

    fila = informe.rows[0]
    assert fila.absence and fila.entries, "la prueba no está midiendo lo que cree"
    assert fila.seconds == 5 * 3600, "las horas trabajadas son las horas trabajadas"

    assert "Vacaciones" in csv, (
        "el día sale igual que uno ordinario: se trabajó teniendo una ausencia "
        "aprobada y el documento no lo dice"
    )
    assert "Vacaciones" in pdf, "y el PDF tampoco"


@pytest.mark.django_db
def test_un_dia_de_vacaciones_sin_fichar_no_lo_dice_dos_veces(empresa):
    """El contraste de la duplicación: esa fila ya llevaba «Vacaciones» en su
    propia columna, y añadir la nota otra vez sería ruido."""
    with tenant_context(empresa.id):
        quien = _persona(empresa, "solovacas@example.com")
        _vacaciones(empresa, quien)
        csv = to_csv(_informe(empresa, quien))

    fila = [linea for linea in csv.splitlines() if linea.startswith("2026-08-12")]
    assert len(fila) == 1, csv
    assert fila[0].count("Vacaciones") == 1, f"lo dice dos veces: {fila[0]}"


@pytest.mark.django_db
def test_un_dia_normal_no_lleva_ninguna_nota(empresa):
    """El contraste que impide que la nota salga siempre y deje de leerse."""
    with tenant_context(empresa.id):
        quien = _persona(empresa, "normal@example.com")
        _ficha(empresa, quien)
        csv = to_csv(_informe(empresa, quien))

    fila = next(linea for linea in csv.splitlines() if linea.startswith("2026-08-12"))
    assert fila.endswith(";"), f"un día corriente lleva observaciones: {fila}"


@pytest.mark.django_db
def test_la_ausencia_ya_viajaba_a_la_huella(empresa):
    """Lo que confirma que esto es parte del registro y no un adorno: dos días
    iguales en horas, uno con ausencia detrás y otro sin ella, no pueden tener
    la misma huella de verificación."""
    with tenant_context(empresa.id):
        con = _persona(empresa, "con@example.com")
        _vacaciones(empresa, con)
        _ficha(empresa, con)
        sin = _persona(empresa, "sin@example.com")
        _ficha(empresa, sin)

        assert _informe(empresa, con).fingerprint != _informe(empresa, sin).fingerprint
