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
from django.utils import translation
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


def revoke_sessions(user) -> int:
    """Cierra todas las sesiones abiertas de esa persona. Devuelve cuántas.

    Un testigo de acceso vive quince minutos y uno de refresco **siete días**, y
    rota: mientras alguien lo use, se renueva solo. Así que una sesión abierta no
    caduca por sí sola en ningún plazo útil.

    Los dos momentos en que eso importa se comprobaron y fallaban los dos:

    - **Cambiar la contraseña.** Es lo que hace quien cree que le han visto la
      clave o ha perdido el móvil, y era exactamente lo que no servía: medido, el
      dispositivo perdido seguía renovando la sesión y leyendo datos después del
      cambio. Recuperar la cuenta no echaba a nadie.
    - **Dar de baja a una persona.** El acceso deja de valer al instante ---la
      autenticación mira `is_active`--- pero el refresco sobrevivía. Y la baja es
      reversible: al reincorporarla, la sesión de antes volvía a funcionar sin que
      hubiera vuelto a escribir su contraseña.

    Se ponen en la lista negra los refrescos vivos, que es lo que ya hace la
    rotación con el testigo usado --- el mecanismo estaba puesto y no se llamaba
    desde aquí. Los accesos ya emitidos siguen valiendo hasta quince minutos: son
    de vida corta a propósito y no hay dónde revocarlos sin consultar la base en
    cada petición.
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    cerradas = 0
    for vivo in OutstandingToken.objects.filter(user=user):
        _, creada = BlacklistedToken.objects.get_or_create(token=vivo)
        cerradas += 1 if creada else 0
    return cerradas


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
    """Sends the link to set a password, in the language of whoever receives it.

    El idioma va explícito y no heredado del contexto, que es lo que hacía
    antes, y estaba mal por los dos caminos que llegan aquí:

    - **La invitación** la manda quien administra, así que el idioma activo era
      **el suyo**. Una empresa castellana invitando a alguien que eligió catalán
      le mandaba el correo en castellano.
    - **El restablecimiento** llega sin sesión, así que no había ningún idioma
      activo y caía a `LANGUAGE_CODE`. Da igual lo que hubiera elegido esa
      persona.

    Los recordatorios de fichaje ya lo hacían así y su comentario explica por
    qué: «para que no llegue en inglés a alguien que trabaja en castellano solo
    porque lo mandó el cron». Aquí faltaba, y el asunto y el cuerpo van los dos
    dentro del `override` porque los dos se traducen.
    """
    uid, token = build_token(user)
    link = f"{base_url.rstrip('/')}/set-password/{uid}/{token}/"

    idioma = user.locale or (user.tenant.language if user.tenant else "")
    with translation.override(idioma or None):
        _enviar_enlace(user, link=link, invitation=invitation)


def _enviar_enlace(user, *, link: str, invitation: bool) -> None:
    company = user.tenant.name if user.tenant else _("the platform")
    subject = (
        _("Your account at %(company)s") % {"company": company}
        if invitation
        else _("Reset your password at %(company)s") % {"company": company}
    )

    body = render_to_string(
        "emails/account_link.txt",
        {
            # El nombre suelto y no `user.first_name` dentro de la plantilla:
            # `{% blocktranslate %}` **no resuelve accesos a atributos**, así que
            # el hueco quedaba vacío y el correo saludaba «Hola :». Es el primero
            # que recibe cualquier empleado nuevo, y llevaba así desde siempre
            # porque nada renderiza estas plantillas en las pruebas.
            #
            # Las otras tres plantillas ya pasaban el nombre así. Esta era la
            # única con la forma que no funciona.
            "first_name": user.first_name,
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
