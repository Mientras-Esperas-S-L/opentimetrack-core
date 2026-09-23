"""Sending mail through a server whose certificate no public authority signed.

A mail relay inside the same network as the application usually has a
certificate of its own, self-signed, and is reached by its internal address. The
stock SMTP backend then refuses to talk to it ---`CERTIFICATE_VERIFY_FAILED`--- and
the usual way out, found in many installations, is to switch verification off.
That turns an encrypted connection into one anybody on the path can intercept.

This backend offers the narrow alternative: **trust that one certificate**. With
`EMAIL_SSL_CAFILE` pointing at it, the connection is verified against it and only
it. And because an internal address rarely matches the name in the certificate,
`EMAIL_SSL_CHECK_HOSTNAME` can be turned off --- which, with a pinned
self-signed certificate, still accepts that certificate and nothing else.

Without either setting it behaves exactly like Django's own.
"""

from __future__ import annotations

import ssl

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property


class SMTPBackend(EmailBackend):
    @cached_property
    def ssl_context(self):
        cafile = getattr(settings, "EMAIL_SSL_CAFILE", "") or None
        if not cafile:
            return super().ssl_context

        contexto = ssl.create_default_context(cafile=cafile)
        contexto.check_hostname = getattr(settings, "EMAIL_SSL_CHECK_HOSTNAME", True)
        if self.ssl_certfile or self.ssl_keyfile:
            contexto.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
        return contexto
