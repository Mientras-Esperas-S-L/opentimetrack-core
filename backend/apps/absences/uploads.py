"""What may be attached to an absence, and how big.

The field had no validation of any kind: no size, no type, no check on what
was inside. Two things follow from that, and the second is the less obvious.

**Size.** Anybody with a session could upload a file of any size, as many times
as they liked. On a filesystem deployment that is the disk; on object storage
it is the bill.

**Type.** The download endpoint serves with `as_attachment=True`, so a
filesystem deployment is safe from anything rendering. Object storage is not:
that path redirects to a signed URL, and the file comes back from the storage
domain with the content type it was uploaded with and no
`Content-Disposition`. An `.html` uploaded as a supporting document would
render there --- somebody else's document, on a domain the company trusts.

So both ends: the extensions here, and `ContentDisposition: attachment` on the
S3 side in settings. Either alone would do for the known case; the pair is what
survives somebody changing the other later.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

#: A supporting document is a scan or a photo. Anything else is easier to send
#: as a PDF than to argue about, and every format left out is one fewer thing
#: that can be made to execute somewhere.
ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "webp", "heic", "heif"]

#: Ten megabytes. A phone photo of a document is two or three; a scan is less.
MAX_BYTES = 10 * 1024 * 1024

#: Con qué empieza de verdad cada uno de los formatos que se admiten.
#:
#: La extensión la elige quien sube el fichero, así que comprobarla no dice
#: nada del contenido: un HTML con un `<script>` dentro pasaba entero llamándose
#: `foto.png`, y un zip llamándose `parte.pdf`. Medido, no supuesto.
#:
#: Las dos consecuencias, y la segunda es la que se ve menos:
#:
#: - La defensa en profundidad que el módulo creía tener no existía. Contra
#:   este caso solo quedaba el `Content-Disposition: attachment`, porque la
#:   lista de extensiones no filtra a quien elige la extensión.
#: - Y sin nadie atacando: un justificante que dice `.pdf` y es otra cosa llega
#:   a la gestoría o a la Inspección y no se abre. El registro queda con un
#:   documento inservible y no se sabe hasta el día en que hace falta.
#:
#: HEIC y WEBP van dentro de un contenedor, así que la marca no está al
#: principio sino unos bytes más adentro; de ahí el desplazamiento.
FIRMAS: dict[str, tuple[tuple[int, bytes], ...]] = {
    "pdf": ((0, b"%PDF-"),),
    "png": ((0, b"\x89PNG\r\n\x1a\n"),),
    "jpg": ((0, b"\xff\xd8\xff"),),
    "jpeg": ((0, b"\xff\xd8\xff"),),
    "webp": ((0, b"RIFF"), (8, b"WEBP")),
    "heic": ((4, b"ftyp"),),
    "heif": ((4, b"ftyp"),),
}

#: Lo que hay que leer para ver la marca más lejana. Doce bytes hoy; se calcula
#: para que añadir un formato con un desplazamiento mayor no lo deje corto.
CABECERA = max(
    desplazamiento + len(marca) for marcas in FIRMAS.values() for desplazamiento, marca in marcas
)


validate_extension = FileExtensionValidator(
    allowed_extensions=ALLOWED_EXTENSIONS,
    message=_("Only a PDF or an image: %(allowed_extensions)s."),
)


def validate_content(uploaded) -> None:
    """Que el fichero sea lo que su nombre dice.

    Solo mira la cabecera: no valida el formato entero ---eso es trabajo de
    quien lo abra--- sino que descarta lo que evidentemente no es. Un PDF roto
    por la mitad sigue pasando, y así debe ser: el objetivo es que nadie cuele
    un tipo distinto, no rechazar un escaneo regular.
    """
    nombre = getattr(uploaded, "name", "") or ""
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    marcas = FIRMAS.get(extension)
    if not marcas:
        # La extensión ya la mira `validate_extension`, que corre en la misma
        # lista de validadores. Duplicar aquí el mensaje daría dos errores por
        # el mismo motivo.
        return

    inicio = uploaded.read(CABECERA)
    uploaded.seek(0)

    if not all(inicio[sitio : sitio + len(marca)] == marca for sitio, marca in marcas):
        raise ValidationError(
            _("The file does not look like a %(kind)s inside, whatever its name says.")
            % {"kind": extension.upper()},
        )


def validate_size(uploaded) -> None:
    if uploaded.size > MAX_BYTES:
        raise ValidationError(
            _("The file is %(size).1f MB and the limit is %(limit)s MB.")
            % {"size": uploaded.size / 1024 / 1024, "limit": MAX_BYTES // 1024 // 1024},
        )
