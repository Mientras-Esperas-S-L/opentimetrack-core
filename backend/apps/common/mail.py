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

Also here: `send_without_failing`, for the notices that must not undo what
triggered them but must not vanish without a trace either.
"""

from __future__ import annotations

import logging
import ssl

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property

log = logging.getLogger(__name__)


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


def mask_address(address: str) -> str:
    """`a***@ejemplo.es`: lo justo para saber a quién iba sin dejar el correo en el log.

    El dominio se queda entero porque es lo que explica la mayoría de los fallos
    ---un servidor que rechaza, un dominio mal escrito--- y no identifica a nadie.
    """
    usuario, arroba, dominio = (address or "").partition("@")
    if not arroba:
        return "***"
    return f"{usuario[:1]}***@{dominio}"


def send_without_failing(*, subject: str, message: str, to: str, what: str) -> bool:
    """Envía un aviso que no puede tumbar la operación que lo dispara, y avisa si falla.

    Sustituye a `fail_silently=True`, que hacía las dos cosas mal a la vez: no
    tumbaba la operación, pero **tampoco dejaba rastro**. Con el servidor de correo
    caído, la persona no recibía que le habían cambiado el registro ---lo que el
    art. 4.b quiere que sepa--- y nadie en la instalación podía enterarse, porque
    los `try/except` que rodeaban cada envío no veían nunca la excepción: se la
    tragaba Django antes.

    Devuelve si salió. `what` dice qué era, para que la línea del log se entienda
    sola.
    """
    from django.core.mail import send_mail

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
        )
    except Exception:
        log.exception("Could not send %s to %s", what, mask_address(to))
        return False
    return True
