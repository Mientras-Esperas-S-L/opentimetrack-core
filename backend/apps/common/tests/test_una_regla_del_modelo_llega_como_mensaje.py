"""Una regla escrita en el modelo tiene que salir como 400, no como traza.

Las reglas que no se pueden expresar campo a campo viven en `full_clean`, y
`full_clean` lanza la `ValidationError` de Django. DRF solo entiende la suya, así
que sin traducción la petición terminaba en **500** y el mensaje ---el bueno,
porque es el que sabe por qué--- no llegaba nunca.

Ya había ocurrido con el tamaño de un justificante, y entonces se tapó
replicando los validadores en el serializer. Eso arregla uno y deja los demás:
aquí se traduce en el manejador, que es donde ya se traducen `Http404` y
`PermissionDenied`.

Se comprueba sobre una regla de verdad ---parte de un día no se reparte entre
varios--- y no sobre un modelo de mentira, porque lo que puede volver a romperse
es la traducción, no la regla.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def quien(db):
    empresa = Tenant.objects.create(
        name="ACME", tax_id="B87878787", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Pide",
        )


@pytest.mark.django_db
def test_parte_de_un_dia_repartida_en_varios_contesta_400_y_dice_por_que(quien):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)

    respuesta = cliente.post(
        "/api/absences/",
        {
            "absence_type": "PAID_LEAVE",
            "start_date": "2027-03-10",
            "end_date": "2027-03-13",
            "start_time": "10:00",
            "end_time": "14:00",
        },
        format="json",
    )

    assert respuesta.status_code == 400, "una regla del modelo salía como 500"
    cuerpo = respuesta.json()["error"]
    # Sobre el campo y no sobre el texto: el mensaje está traducido y cambia con
    # el idioma de la petición.
    assert "end_date" in cuerpo["details"]
    assert cuerpo["details"]["end_date"], "el 400 llegaba sin decir nada"


@pytest.mark.django_db
def test_y_lo_que_ya_estaba_bien_sigue_igual(quien):
    """La traducción nueva no puede tragarse los 400 que ya funcionaban."""
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)

    respuesta = cliente.post(
        "/api/absences/",
        {"absence_type": "PAID_LEAVE", "start_date": "2027-03-10", "end_time": "14:00"},
        format="json",
    )

    assert respuesta.status_code == 400
    detalles = respuesta.json()["error"]["details"]
    # Falta `end_date` (lo pide el serializer) y falta la pareja de `end_time`.
    assert "end_date" in detalles
