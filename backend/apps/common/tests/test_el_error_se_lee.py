"""Lo que el cliente recibe cuando algo va mal tiene que ser una frase.

`api_exception_handler` mete el mensaje en `error.message`. Cuando el error venía
como **lista** --- que es lo que produce `ValidationError([...])`, y lo que sale
cuando la regla no es de un campo concreto --- hacía `str()` de la lista entera, y
`str()` de una lista usa el `repr` de lo que lleva dentro:

    [ErrorDetail(string='“pepe” no es un UUID válido.', code='invalid')]

El mensaje bueno estaba ahí, envuelto en el nombre de una clase de DRF. Lo ve
quien integra contra la API, que es justo a quien menos le sirve.

Se comprueba por los dos lados: contra el manejador, que es donde vive la
decisión, y contra un endpoint real, para que no sea solo teoría.
"""

from __future__ import annotations

import pytest
from rest_framework import exceptions
from rest_framework.test import APIClient, APIRequestFactory

from apps.common.exceptions import api_exception_handler
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


def _manejar(exc):
    contexto = {"view": None, "request": APIRequestFactory().get("/")}
    return api_exception_handler(exc, contexto).data["error"]


def test_una_lista_de_errores_sale_como_frase():
    error = _manejar(exceptions.ValidationError(["No vale.", "Ni esto tampoco."]))

    assert "ErrorDetail" not in error["message"], error["message"]
    assert "No vale." in error["message"] and "Ni esto tampoco." in error["message"]


def test_un_solo_error_en_lista_no_lleva_corchetes():
    error = _manejar(exceptions.ValidationError(["“pepe” no es un UUID válido."]))

    assert error["message"] == "“pepe” no es un UUID válido.", error["message"]


def test_los_errores_por_campo_siguen_yendo_en_details():
    """El contraste. Un diccionario ya se serializaba bien y no puede pasar a
    aplanarse en una frase: quien integra necesita saber **qué campo** falla."""
    error = _manejar(exceptions.ValidationError({"date_to": ["Va antes que la inicial."]}))

    assert error["details"], error
    assert "date_to" in error["details"]


def test_un_detalle_suelto_se_queda_como_estaba():
    """El otro contraste: `NotFound` trae un `detail` de texto, no una lista."""
    error = _manejar(exceptions.NotFound())

    assert "ErrorDetail" not in error["message"]
    assert error["details"] == {}


@pytest.mark.django_db
def test_y_por_la_api_de_verdad():
    """El camino real: un identificador que no es un UUID llegando al filtro del
    informe. Es lo que destapó esto."""
    empresa = Tenant.objects.create(
        name="Mensaje SL", tax_id="B31313131", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="mensaje@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Men",
            last_name="Saje",
            is_staff=True,
        )
        api = APIClient()
        api.force_authenticate(user=quien)
        r = api.get(
            "/api/reports/working-time/",
            {"employee": "pepe", "date_from": "2026-08-01", "date_to": "2026-08-02"},
        )

    assert r.status_code == 400
    assert "ErrorDetail" not in str(r.json()), r.json()
