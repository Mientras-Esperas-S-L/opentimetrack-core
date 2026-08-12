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


validate_extension = FileExtensionValidator(
    allowed_extensions=ALLOWED_EXTENSIONS,
    message=_("Only a PDF or an image: %(allowed_extensions)s."),
)


def validate_size(uploaded) -> None:
    if uploaded.size > MAX_BYTES:
        raise ValidationError(
            _("The file is %(size).1f MB and the limit is %(limit)s MB.")
            % {"size": uploaded.size / 1024 / 1024, "limit": MAX_BYTES // 1024 // 1024},
        )
