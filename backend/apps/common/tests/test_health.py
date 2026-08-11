"""La comprobación de salud es la primera evidencia de que la pila funciona."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_salud_responde_200_con_las_dependencias_sanas(client):
    respuesta = client.get(reverse("health"))

    assert respuesta.status_code == 200
    assert respuesta.data["status"] == "ok"
    assert respuesta.data["checks"]["database"]["ok"] is True


@pytest.mark.django_db
def test_salud_no_exige_autenticacion(client):
    """Una sonda externa no lleva credenciales."""
    assert client.get(reverse("health")).status_code == 200


@pytest.mark.django_db
def test_el_esquema_openapi_se_genera(client):
    """Si el esquema no compila, la CI debe caer aquí y no en despliegue."""
    respuesta = client.get(reverse("schema"))

    assert respuesta.status_code == 200
    assert b"openapi" in respuesta.content[:200].lower()
