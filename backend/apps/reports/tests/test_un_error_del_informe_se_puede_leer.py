"""Los rechazos del informe llegaban como cinco bytes que decían «error».

`PDFRenderer` y `CSVRenderer` entregan los bytes del documento tal cual, que es lo
correcto para una respuesta buena. Pero al ser los únicos declarados, también
renderizaban los cuerpos de error --- y pasarle un diccionario a `HttpResponse`
hace que Django recorra sus claves. La única clave era `error`, así que **eso**
era el cuerpo: cinco bytes, etiquetados `application/pdf`.

De modo que ninguno de estos mensajes llegó nunca a nadie:

- «201 personas pasan de las 200 que se pueden generar de una vez. Acota por
  departamento», que es el que explica qué hacer con una plantilla grande.
- «La fecha final no puede ir antes que la inicial».
- «Nadie trabajó en ese periodo».
- «Las fechas se escriben como AAAA-MM-DD».

Todos escritos con cuidado, todos invisibles. Se vieron al tropezar con otra cosa
---pedir el periodo con el nombre del endpoint vecino--- y no encontrar la
explicación en ninguna parte.
"""

from __future__ import annotations

import json

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def jefa(db):
    empresa = Tenant.objects.create(
        name="Legibles", tax_id="B90400001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )


def pedir(quien, consulta):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente.get(f"/api/reports/working-time/?{consulta}")


@pytest.mark.parametrize("formato", ["pdf", "csv"])
@pytest.mark.django_db
def test_un_rango_al_reves_dice_por_que(jefa, formato):
    respuesta = pedir(jefa, f"date_from=2026-08-31&date_to=2026-08-01&format={formato}")

    assert respuesta.status_code == 400
    # Y se puede leer: antes eran cinco bytes con la palabra «error».
    assert len(respuesta.content) > 20, respuesta.content
    cuerpo = json.loads(respuesta.content)
    assert cuerpo["error"]["message"], "el 400 llegaba sin mensaje"


@pytest.mark.parametrize("formato", ["pdf", "csv"])
@pytest.mark.django_db
def test_y_el_tipo_de_contenido_dice_que_es_json(jefa, formato):
    """Un cliente que pidió un PDF y recibe un fallo necesita poder leerlo.

    Devolverle `application/pdf` con JSON dentro es peor que no contestar.
    """
    respuesta = pedir(jefa, f"date_from=ayer&format={formato}")

    assert respuesta.status_code == 400
    assert respuesta.headers["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_un_informe_de_verdad_sigue_saliendo_en_su_formato(jefa):
    """Lo que no se puede romper: el documento bueno son bytes, no JSON."""
    respuesta = pedir(jefa, "date_from=2026-08-01&date_to=2026-08-31&format=pdf")

    assert respuesta.status_code == 200
    assert respuesta.headers["Content-Type"] == "application/pdf"
    assert respuesta.content.startswith(b"%PDF-")

    en_csv = pedir(jefa, "date_from=2026-08-01&date_to=2026-08-31&format=csv")
    assert en_csv.status_code == 200
    assert "text/csv" in en_csv.headers["Content-Type"]
    assert b"Registro de jornada" in en_csv.content
