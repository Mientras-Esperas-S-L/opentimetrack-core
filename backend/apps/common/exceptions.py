"""Formato de error uniforme para toda la API.

Cada error sale con la misma forma, de modo que el cliente pueda reaccionar al
`code` sin leer el texto:

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

# Traducción de la excepción de DRF a un código estable y legible por máquina.
CODE_BY_STATUS = {
    400: "validation_error",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    429: "throttled",
    500: "internal_error",
}


class BusinessRuleError(exceptions.APIException):
    """A business rule was broken. Answers 409, not 400.

    A 400 says "what you sent me is malformed"; this says "it is well
    formed but cannot be done", which is a different thing and the client
    handles it differently. Example: clocking in with approved leave for today.
    """

    status_code = 409
    default_code = "business_rule_violated"
    default_detail = "The operation is not possible in the current state."

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(detail=message, code=code)


class IncompleteRequest(exceptions.APIException):
    """Something the request had to carry is not there. Answers 400.

    The other half of the distinction `BusinessRuleError` documents: this one
    *is* malformed. Separate from DRF's field validation because what is missing
    need not be a field --- a required header, for instance --- and because a
    machine on the other end deserves a code it can branch on rather than a
    generic "invalid".
    """

    status_code = 400
    default_code = "incomplete_request"
    default_detail = "The request is missing something it must carry."

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(detail=message, code=code)


class MailNotSent(exceptions.APIException):
    """El servidor de correo no ha aceptado el mensaje. Contesta 502.

    Para las acciones cuyo único efecto es mandar un correo ---reenviar una
    invitación---: si no sale, hay que decirlo en vez de contestar «enviado».
    502 y no 500 porque lo que falla es el servidor de correo, no esta API, y con
    el formato de siempre para que la pantalla enseñe el motivo: un 500 llega sin
    cuerpo y la pantalla decía «No hay conexión con el servidor».
    """

    status_code = 502
    default_code = "mail_not_sent"
    default_detail = "The email could not be sent."

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(detail=message, code=code)


def _mensaje_de_espera(segundos) -> str:
    """Lo que se le dice a quien ha agotado el límite de intentos.

    DRF trae el suyo traducido a máquina: «Solicitud fue regulada (throttled).
    Se espera que esté disponible en 58 segundos.» Sin artículo, con una palabra
    en inglés entre paréntesis, y en el peor momento posible --- lo lee quien
    acaba de fallar cinco veces la contraseña, que ya está molesto y no está
    para descifrar nada.

    En minutos cuando pasa del minuto, porque «en 118 segundos» obliga a dividir
    a quien solo quiere saber si le da tiempo a un café.
    """
    espera = int(segundos or 0)
    if espera <= 0:
        return str(_("Too many attempts. Wait a moment and try again."))
    if espera < 60:
        return str(_("Too many attempts. Try again in %(seconds)s seconds.") % {"seconds": espera})
    minutos = round(espera / 60)
    return str(
        ngettext(
            "Too many attempts. Try again in %(minutes)s minute.",
            "Too many attempts. Try again in %(minutes)s minutes.",
            minutos,
        )
        % {"minutes": minutos}
    )


def _sin_jerga_de_clave(detalle):
    """Cambia el «no existe» de DRF por algo que se entienda.

    Cuando lo elegido en un desplegable ---un departamento, un centro--- se borra
    mientras otra persona tiene la ficha abierta, DRF contesta «Clave primaria
    "…" inválida - objeto no existe.», con el identificador interno dentro. Quien
    lo lee no sabe qué es una clave primaria; lo que necesita saber es que eso ya
    no está y que tiene que volver a elegir.

    Aquí y no campo a campo: el mensaje lo ponen los campos que DRF crea solo para
    cada clave ajena, y hay uno en casi cada serializer.
    """
    if isinstance(detalle, dict):
        return {campo: _sin_jerga_de_clave(v) for campo, v in detalle.items()}
    if isinstance(detalle, list):
        return [_sin_jerga_de_clave(v) for v in detalle]
    if isinstance(detalle, exceptions.ErrorDetail) and detalle.code == "does_not_exist":
        return exceptions.ErrorDetail(
            _(
                "That choice no longer exists: someone may have just deleted it. "
                "Reload and choose again."
            ),
            code="does_not_exist",
        )
    return detalle


def api_exception_handler(exc, context):
    """Envuelve la respuesta de DRF en el formato de error único."""
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        # `full_clean` lanza la de Django, que DRF no traduce: sin esto sale un
        # 500 y el mensaje no llega nunca ---justo el que suele ser bueno,
        # porque las reglas que no se pueden expresar campo a campo viven en el
        # modelo. Pedir «parte de un día» repartida en cuatro contestaba una
        # traza, teniendo escrito «Parte de un día es un día. Para varios días
        # deja las horas vacías y cuentan enteros».
        #
        # Ya había pasado con el tamaño de un justificante, y entonces se tapó
        # replicando los validadores en el serializer. Aquí queda resuelto para
        # todas las reglas del modelo a la vez, que es donde tenía que estar.
        exc = exceptions.ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        )

    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled: let Django log it and pass it on. In production DEBUG is
        # off and the client gets a 500 with no details.
        logger.exception("Unhandled exception in %s", context.get("view"))
        return None

    if isinstance(exc, BusinessRuleError | IncompleteRequest | MailNotSent):
        code, message, details = exc.code, exc.message, exc.details
    elif isinstance(exc, exceptions.Throttled):
        code, message, details = "throttled", _mensaje_de_espera(exc.wait), {}
    else:
        code = getattr(exc, "default_code", None) or CODE_BY_STATUS.get(
            response.status_code, "error"
        )
        detail = response.data
        if isinstance(detail, dict) and "detail" in detail:
            message = str(detail["detail"])
            details = {}
        elif isinstance(detail, dict):
            # Errores de validación por campo.
            message = "Los datos enviados no son válidos."
            details = _sin_jerga_de_clave(detail)
        elif isinstance(detail, list | tuple):
            # Una lista de errores sin campo al que colgarlos: la produce
            # `ValidationError([...])`, y es lo que sale cuando una regla no es
            # de un campo concreto ---por ejemplo, un identificador que no es un
            # UUID llegando a un filtro---.
            #
            # `str()` de una lista usa el `repr` de lo que lleva dentro, así que
            # el cliente recibía esto:
            #
            #     [ErrorDetail(string='“pepe” no es un UUID válido.', code='invalid')]
            #
            # El mensaje bueno estaba ahí dentro, envuelto en el nombre de una
            # clase de DRF. `ErrorDetail` hereda de `str`, así que basta con
            # convertir uno a uno en vez de la lista entera.
            message = " ".join(str(m) for m in detail)
            details = {}
        else:
            message = str(detail)
            details = {}

    return Response(
        {"error": {"code": code, "message": message, "details": details}},
        status=response.status_code,
        headers=getattr(response, "headers", None),
    )
