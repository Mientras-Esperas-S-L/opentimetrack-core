"""Todos los errores de la API salen con la misma forma."""

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.views import APIView

from apps.common.exceptions import BusinessRuleError, api_exception_handler


def _manejar(exc):
    return api_exception_handler(exc, {"view": APIView()})


def test_el_error_lleva_siempre_codigo_mensaje_y_detalles():
    respuesta = _manejar(NotFound())

    assert respuesta.status_code == 404
    assert set(respuesta.data["error"]) == {"code", "message", "details"}


def test_una_regla_de_negocio_responde_409_y_no_400():
    """400 es «lo has escrito mal»; 409 es «no se puede hacer». No es lo mismo."""
    exc = BusinessRuleError(
        code="punch_blocked_by_absence",
        message="No puedes fichar: tienes una ausencia aprobada para hoy.",
        details={"date": "2026-05-26"},
    )

    respuesta = _manejar(exc)

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "punch_blocked_by_absence"
    assert respuesta.data["error"]["details"]["date"] == "2026-05-26"


def test_los_errores_de_validacion_conservan_el_campo_que_falla():
    respuesta = _manejar(ValidationError({"email": ["Este campo es obligatorio."]}))

    assert respuesta.status_code == 400
    assert "email" in respuesta.data["error"]["details"]
