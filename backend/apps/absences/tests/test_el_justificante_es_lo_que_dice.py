"""Un justificante que dice `.pdf` y no lo es.

La extensión la elige quien sube el fichero, así que comprobarla no dice nada
del contenido. Medido contra el endpoint real antes de tocar nada: un HTML con
un `<script>` dentro entraba entero llamándose `foto.png`, y un zip entraba
llamándose `parte.pdf`.

Dos consecuencias, y la segunda se ve menos.

La defensa en profundidad que `uploads.py` creía tener no existía. Su docstring
dice que son dos ---la lista de extensiones y el `Content-Disposition:
attachment` del lado del almacenamiento--- y que «el par es lo que sobrevive a
que alguien cambie la otra más tarde». Contra este caso solo había una: una
lista de extensiones no filtra a quien elige la extensión.

Y sin nadie atacando: un justificante que dice `.pdf` y es otra cosa llega a la
gestoría o a la Inspección y no se abre. El registro se queda con un documento
inservible y no se sabe hasta el día en que hace falta.

Lo que **no** se hace aquí es validar el formato entero. Un PDF roto por la
mitad sigue pasando, y así debe ser: se trata de que nadie cuele un tipo
distinto, no de rechazar el escaneo de una fotocopiadora vieja.
"""

from __future__ import annotations

import io
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import AbsenceType
from apps.absences.uploads import validate_content
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

PDF_DE_VERDAD = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="Con partes", tax_id="B88888888", time_zone="Europe/Madrid")


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="sube@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Sube",
            last_name="Cosas",
        )


@pytest.fixture
def cliente(quien):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(quien).access_token)
    )
    return client


def pide_un_dia(cliente, nombre, datos, *, dentro_de):
    """Una ausencia por día distinto: pedirlas el mismo se rechaza por solaparse.

    Ese 409 no dice nada del fichero, y confundirlo con una validación de
    contenido fue lo que estuvo a punto de dar por bueno el defecto.
    """
    dia = (timezone.now().date() + timedelta(days=dentro_de)).isoformat()
    return cliente.post(
        "/api/absences/",
        {
            "absence_type": AbsenceType.PAID_LEAVE,
            "start_date": dia,
            "end_date": dia,
            "justification": SimpleUploadedFile(nombre, datos),
        },
        format="multipart",
    )


@pytest.mark.django_db
def test_un_zip_con_nombre_de_pdf_no_entra(cliente):
    assert (
        pide_un_dia(cliente, "parte.pdf", b"PK\x03\x04" + b"\x00" * 40, dentro_de=10).status_code
        == 400
    )


@pytest.mark.django_db
def test_un_html_con_nombre_de_imagen_tampoco(cliente):
    """El que más importa: `.png` está en la lista de permitidas."""
    respuesta = pide_un_dia(
        cliente, "foto.png", b"<html><script>alert(1)</script></html>", dentro_de=20
    )
    assert respuesta.status_code == 400


@pytest.mark.django_db
def test_y_un_parte_de_verdad_sigue_entrando(cliente):
    """El control. Sin esto, un validador que rechazara todo pasaría las de arriba."""
    respuesta = pide_un_dia(cliente, "bueno.pdf", PDF_DE_VERDAD, dentro_de=30)
    assert respuesta.status_code == 201, respuesta.data


@pytest.mark.django_db
def test_ninguna_foto_de_movil_se_queda_fuera():
    """Rechazar un justificante legítimo sería peor que el defecto de partida.

    Un parte se fotografía con el móvil, y de ahí salen los cuatro formatos.
    """
    from PIL import Image

    for formato, extension in (("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")):
        buffer = io.BytesIO()
        Image.new("RGB", (4, 4), (200, 30, 30)).save(buffer, format=formato)
        validate_content(SimpleUploadedFile(f"parte.{extension}", buffer.getvalue()))

    # HEIC es lo que sale de un iPhone. La firma va dentro de la caja `ftyp`,
    # unos bytes más adentro, que es el caso que obliga al desplazamiento.
    validate_content(SimpleUploadedFile("parte.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16))


@pytest.mark.django_db
def test_el_fichero_queda_listo_para_quien_lo_guarde():
    """El validador lee la cabecera, así que tiene que devolver el puntero.

    Sin esto se guardarían justificantes a los que les faltan los primeros
    bytes, y el fallo aparecería al abrirlos y no al subirlos.
    """
    fichero = SimpleUploadedFile("parte.pdf", PDF_DE_VERDAD)
    validate_content(fichero)

    assert fichero.read() == PDF_DE_VERDAD


@pytest.mark.django_db
def test_un_pdf_roto_por_la_mitad_sigue_valiendo():
    """No se valida el formato: se descarta lo que evidentemente es otra cosa."""
    validate_content(SimpleUploadedFile("parte.pdf", b"%PDF-1.4 y aqui se corta"))


@pytest.mark.django_db
def test_una_extension_que_no_se_admite_la_rechaza_el_otro_validador():
    """`validate_content` calla ahí a propósito: dos errores por lo mismo confunden."""
    with pytest.raises(ValidationError):
        from apps.absences.uploads import validate_extension

        validate_extension(SimpleUploadedFile("parte.exe", b"MZ\x90\x00"))

    validate_content(SimpleUploadedFile("parte.exe", b"MZ\x90\x00"))
