"""Fields whose contents must not be readable in a database dump.

Only for secrets the system has to **read back**: the client secret of an identity
provider, for instance, which is needed to exchange an authorisation code. Anything
that only has to be *checked* is hashed instead, never encrypted -- that is what
application credentials do, and it is the stronger answer when it applies.

The key lives in `FIELD_ENCRYPTION_KEY`, outside the database and outside the code. It
is required only when something is actually stored encrypted: a self-hoster who does
not use federated sign-in never meets it. And it is deliberately **not** derived from
`SECRET_KEY`: rotating that one is the ordinary answer to an incident, and it would
silently make every stored secret unreadable.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.translation import gettext_lazy as _

#: What an encrypted value looks like, so a plain one can be told apart. Values written
#: before encryption existed stay readable rather than turning into rubbish.
PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is needed to store this secret. Generate one with:\n"
            "  python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key())'"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is not a valid Fernet key (32 url-safe base64 bytes)."
        ) from exc


class EncryptedTextField(models.TextField):
    """Text that is stored encrypted and comes back in clear.

    It cannot be filtered, ordered or searched on in the database, and that is the
    point: the database never sees the value. Anything that has to be looked up goes
    in a separate column (a hint, a fingerprint), never here.
    """

    description = _("Text stored encrypted at rest")

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        if isinstance(value, str) and value.startswith(PREFIX):
            return value  # already encrypted: saving twice must not double-wrap
        token = _fernet().encrypt(str(value).encode("utf-8")).decode("ascii")
        return f"{PREFIX}{token}"

    def from_db_value(self, value, expression, connection):
        return self._decrypt(value)

    def to_python(self, value):
        return self._decrypt(value)

    @staticmethod
    def _decrypt(value):
        if not value or not isinstance(value, str) or not value.startswith(PREFIX):
            return value
        try:
            return _fernet().decrypt(value[len(PREFIX) :].encode("ascii")).decode("utf-8")
        except InvalidToken, ImproperlyConfigured:
            # A key that no longer opens this value: better an empty secret, which
            # fails loudly at the next exchange, than a crash on every read of the row.
            return ""
