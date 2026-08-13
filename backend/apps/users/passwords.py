"""Password recovery and invitations.

Both flows are the same mechanism seen from two sides: somebody who cannot sign
in gets a single-use link to set a password. The difference is only who started
it -- the person, or the administrator who created their account.

Two things shape the design here:

- **Nothing is revealed.** Asking to recover an address that does not exist gets
  the same answer as one that does. Otherwise the endpoint becomes a way to find
  out who works where.
- **The same address may exist in several companies.** Rather than asking which
  one, a link is sent for each account. The person recognises their own company
  in the message, and nobody has to type a tax number to get back in.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class AccountTokenGenerator(PasswordResetTokenGenerator):
    """Single-use token, without a table of its own.

    Django derives it from the current password hash and the last sign-in, so
    using the link invalidates it: the hash changes. It works for an account that
    has never had a usable password, which is what makes it serve invitations
    too.
    """

    def _make_hash_value(self, user, timestamp: int) -> str:
        last = user.last_login
        login = "" if last is None else last.replace(microsecond=0, tzinfo=None)
        return f"{user.pk}{user.password}{login}{timestamp}{user.is_active}"


token_generator = AccountTokenGenerator()


def build_token(user) -> tuple[str, str]:
    """Returns the pair (identifier, token) that travels in the link."""
    return urlsafe_base64_encode(force_bytes(user.pk)), token_generator.make_token(user)


def resolve_token(uid: str, token: str):
    """The user behind a link, or None if it is not valid."""
    from django.contrib.auth import get_user_model

    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = get_user_model().objects.get(pk=pk, is_active=True)
    except Exception:
        # A malformed link is simply an invalid link; there is nothing to
        # distinguish for the caller.
        return None

    if not token_generator.check_token(user, token):
        return None
    return user


def send_account_email(user, *, base_url: str, invitation: bool = False) -> None:
    """Sends the link to set a password."""
    uid, token = build_token(user)
    link = f"{base_url.rstrip('/')}/set-password/{uid}/{token}/"

    company = user.tenant.name if user.tenant else _("the platform")
    subject = (
        _("Your account at %(company)s") % {"company": company}
        if invitation
        else _("Reset your password at %(company)s") % {"company": company}
    )

    body = render_to_string(
        "emails/account_link.txt",
        {
            "user": user,
            "company": company,
            "link": link,
            "invitation": invitation,
            # Del ajuste, no escrito a mano. Estaba puesto a 24 en las dos
            # partes y coincidían, pero `PASSWORD_RESET_TIMEOUT` se puede
            # cambiar por entorno: bajarlo a cuatro horas habría dejado un
            # correo prometiendo veinticuatro, y quien lo creyera se
            # encontraría el enlace muerto sin entender por qué.
            "hours": round(settings.PASSWORD_RESET_TIMEOUT / 3600),
        },
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info(
        "Account link sent to %s (%s)", user.email, "invitation" if invitation else "recovery"
    )
