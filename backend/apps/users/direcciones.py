"""Cuándo un correo no puede repetirse entre una cuenta de la instalación y una empresa.

Entre empresas distintas el mismo correo es normal ---alguien que trabaja para
dos--- y lo resuelve el identificador fiscal en la pantalla de entrada. Lo que no
puede pasar es que una cuenta de la instalación y una persona de una empresa
estén **activas** con la misma dirección: la de la instalación no tiene
identificador fiscal que dar, así que si las dos aceptan la contraseña no hay
forma de decir a cuál se entra.

Por eso la regla vive aquí y no en cada puerta: antes solo la miraba el alta de
cuentas de la instalación, y todas las demás ---el alta de una empresa, el alta o
el cambio de correo de una persona, las reactivaciones, el empuje de una
aplicación--- dejaban crear el choque por el otro lado.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _


def correo_ocupado(correo: str, *, de_la_instalacion: bool, salvo=None) -> str | None:
    """Por qué no vale ese correo para una cuenta que va a quedar activa, o nada.

    - `de_la_instalacion=True`: la cuenta es de la instalación. No vale si ya lo
      tiene otra de la instalación ---activa o no: entre ellas no hay identificador
      fiscal que las separe nunca--- ni si lo tiene alguien activo de una empresa.
    - `de_la_instalacion=False`: la cuenta es de una empresa. No vale si lo tiene
      una cuenta activa de la instalación. Las de otras empresas no cuentan: eso lo
      resuelve el identificador fiscal.

    Las personas de una empresa desactivada **sí** cuentan. No pueden entrar hoy,
    pero la empresa se puede reactivar y el choque volvería sin pasar por ninguna
    de estas comprobaciones.

    `salvo` es la propia cuenta, cuando se está cambiando una que ya existe.
    """
    User = get_user_model()
    correo = (correo or "").strip()
    if not correo:
        return None
    mismo = User.objects.filter(email__iexact=correo)
    if salvo is not None and salvo.pk is not None:
        mismo = mismo.exclude(pk=salvo.pk)

    if de_la_instalacion:
        if mismo.filter(tenant__isnull=True).exists():
            return _("There is already an installation account with that address.")
        de_una_empresa = (
            mismo.filter(tenant__isnull=False, is_active=True).select_related("tenant").first()
        )
        if de_una_empresa is not None:
            return _(
                "That address already belongs to somebody in %(company)s. An "
                "installation account with a repeated address could not sign in, "
                "because the sign-in screen would ask which company it is, and this "
                "one has none. Use a different address."
            ) % {"company": de_una_empresa.tenant.name}
        return None

    if mismo.filter(tenant__isnull=True, is_active=True).exists():
        return _(
            "That address belongs to an account that administers this installation. "
            "Use a different address."
        )
    return None
