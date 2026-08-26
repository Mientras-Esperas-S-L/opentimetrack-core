"""El PDF es la tercera pieza de lo que sale del sistema, y la que se lee en papel.

Aquí no basta con preguntar si el texto está: un extractor lee el flujo de
contenido del fichero, no lo que cae dentro de los márgenes. Una celda de tabla
sin ajuste de línea dibuja la cadena entera seguida, se sale de la hoja por la
derecha, y el extractor la devuelve completa igual. Estaba, y no se leía.

Por eso estas pruebas miden **dónde** cae el texto. Y la primera de todas
comprueba que la medición sabe detectar el fallo, porque una comprobación que
solo ha visto casos buenos no ha demostrado nada.

Lo que se protege es el art. 4.b: el registro lleva la versión de la persona
junto a la de la empresa, y quien lo lee tiene que poder comparar las dos. Mil
caracteres, que es lo que admite el formulario de discrepancia.
"""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table

from apps.common.clock import local_today
from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.reports.pdf import render_pdf
from apps.reports.services import build_report
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: El máximo que acepta el formulario de discrepancia (`DissentSerializer`).
LARGO = ("No estoy de acuerdo: ese dia entre a las siete y no a las nueve. " * 16)[:1000]


def hasta_donde_llega(pdf: bytes) -> tuple[float, float]:
    """Ancho de la hoja y punto más a la derecha que alcanza el texto, en puntos.

    Se estima a partir de la posición donde arranca cada trozo de texto y de su
    longitud a media anchura de cuerpo. Es aproximado a propósito: sirve para
    distinguir «cabe» de «se sale nueve veces la hoja», que es la diferencia que
    importa, y no depende de las métricas exactas de la fuente.
    """
    pagina = PdfReader(io.BytesIO(pdf)).pages[0]
    tope = [0.0]

    def visitante(texto, cm, tm, fuente, tamano):
        if texto.strip():
            tope[0] = max(tope[0], tm[4] + len(texto) * (tamano or 8) * 0.5)

    pagina.extract_text(visitor_text=visitante)
    return float(pagina.mediabox.width), tope[0]


def test_la_medicion_sabe_ver_el_desbordamiento():
    """Primero, contra un caso que se sabe malo.

    Una tabla con la cadena suelta en la celda ---exactamente lo que hacía el
    informe--- tiene que dar «se sale». Sin esta prueba, las de abajo podrían
    estar pasando porque el medidor no mide, no porque el PDF esté bien.
    """
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm)
    documento.build([Table([[LARGO]], colWidths=[100 * mm])])

    ancho, tope = hasta_donde_llega(buffer.getvalue())
    assert tope > ancho, f"el medidor no ve salirse un texto que se sale: {tope:.0f} de {ancho:.0f}"


def texto_seguido(pdf: bytes) -> str:
    """El texto de la primera hoja, con los saltos de línea colapsados.

    Hace falta porque ahora las celdas **parten en líneas**, que es el arreglo:
    una frase corta puede salir cortada por la mitad entre dos renglones. Buscar
    la cadena literal fallaría por el motivo contrario al que se vigila.
    """
    crudo = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    return " ".join(crudo.split())


@pytest.fixture
def informe(db):
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B44444444", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="discrepa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            last_name="Discrepa",
        )
        register_punch(employee=quien, company=empresa)
        # El hoy de la empresa, no el del contenedor. `register_punch` guarda el
        # fichaje en la hora de Madrid, y `date.today()` da la fecha UTC: entre
        # medianoche y las dos de la madrugada en verano son días distintos, el
        # informe pedía un día sin fichajes y la fila que estas pruebas marcan
        # como discrepada no llegaba a la hoja. Es la trampa que `common/clock.py`
        # documenta y que el producto ya barrió de su propio código.
        hoy = local_today(empresa)
        yield build_report(employee=quien, company=empresa, date_from=hoy, date_to=hoy)


def test_la_discrepasion_entera_cabe_en_la_hoja(informe):
    """Los mil caracteres del art. 4.b, dentro de los márgenes."""
    informe.rows[0].disputed = True
    informe.rows[0].dissent = [LARGO]

    ancho, tope = hasta_donde_llega(render_pdf(informe))
    assert tope <= ancho, f"la discrepancia se sale de la hoja: {tope:.0f} de {ancho:.0f}"


def test_un_nombre_largo_no_se_sale(informe):
    """`first_name` y `last_name` admiten cien caracteres cada uno."""
    informe.employee_name = "Maria" + "n" * 95 + " " + "Fernandez" + "z" * 91
    informe.company_name = "Sociedad " + "Anonima " * 11

    ancho, tope = hasta_donde_llega(render_pdf(informe))
    assert tope <= ancho, f"el nombre se sale de la hoja: {tope:.0f} de {ancho:.0f}"


def test_el_marcado_no_se_interpreta(informe):
    """`Paragraph` lee marcado, así que el texto de fuera se escapa.

    Sin escapar, `<font color=white>` escondería texto dentro de una prueba
    legal, y quien lo lee en pantalla no vería que falta algo.
    """
    informe.rows[0].disputed = True
    informe.rows[0].dissent = ['Entre <b>antes</b> <font color="white">y esto no se ve</font>']

    texto = texto_seguido(render_pdf(informe))
    assert "<b>antes</b>" in texto, "el marcado se ha interpretado en vez de mostrarse"
    assert "y esto no se ve" in texto, "el texto oculto no llega al documento"


def test_un_menor_que_no_rompe_el_documento(informe):
    """Un apellido con `<` es raro, pero no puede tumbar el informe entero."""
    informe.employee_name = "Ana <Discrepa & Cia>"
    informe.rows[0].disputed = True
    informe.rows[0].dissent = ["Entre a las 7 < 9, no a las 9"]

    pdf = render_pdf(informe)
    assert pdf.startswith(b"%PDF-"), "el PDF no es un PDF"
    assert "Ana <Discrepa & Cia>" in texto_seguido(pdf)
