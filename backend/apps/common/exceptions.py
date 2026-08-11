"""Formato de error uniforme para toda la API.

Cada error sale con la misma forma, de modo que el cliente pueda reaccionar al
`code` sin leer el texto:

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
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
    """Regla de negocio incumplida. Responde 409, no 400.

    Un 400 dice «lo que me has mandado está mal escrito»; esto dice «está bien
    escrito pero no se puede hacer», que es distinto y el cliente lo trata de
    otra forma. Ejemplo: fichar con una ausencia aprobada para hoy.
    """

    status_code = 409
    default_code = "business_rule_violated"
    default_detail = "La operación no es posible en el estado actual."

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(detail=message, code=code)


def api_exception_handler(exc, context):
    """Envuelve la respuesta de DRF en el formato de error único."""
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled: let Django log it and pass it on. In production DEBUG is
        # off and the client gets a 500 with no details.
        logger.exception("Unhandled exception in %s", context.get("view"))
        return None

    if isinstance(exc, BusinessRuleError):
        code, message, details = exc.code, exc.message, exc.details
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
            details = detail
        else:
            message = str(detail)
            details = {}

    return Response(
        {"error": {"code": code, "message": message, "details": details}},
        status=response.status_code,
        headers=getattr(response, "headers", None),
    )
