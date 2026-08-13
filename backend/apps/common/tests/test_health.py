"""La comprobación de salud es la primera evidencia de que la pila funciona."""

from io import StringIO

import pytest
from django.core.management import call_command
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


@pytest.mark.django_db
def test_la_salud_mira_que_el_rastro_siga_siendo_inmutable(client):
    """La garantía que se había evaporado sin ruido.

    `audit.0002_append_only_trigger` crea tres triggers que rechazan UPDATE,
    DELETE y TRUNCATE sobre el rastro, y su propia cabecera dice por qué: «un
    rastro de auditoría que puede editar aquel a quien incrimina no es prueba».

    Pues no estaban. La migración figuraba aplicada, su función existía, y los
    tres triggers **no** estaban en la base de desarrollo: se podía editar y
    borrar el rastro sin que nada chistara. Da igual cómo se perdieron ---una
    tabla recreada, una restauración, un `migrate --fake`---; lo que importa es
    que una garantía que solo vive en una migración se puede perder en silencio.

    Por eso se pregunta a **la base que está sirviendo**, y por eso vive en la
    salud y no solo en una prueba: las pruebas corren sus migraciones enteras y
    siempre los ven. Es exactamente el sitio donde no estaba el problema.
    """
    respuesta = client.get("/api/health/")

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["checks"]["audit_append_only"]["ok"] is True


@pytest.mark.django_db
def test_sin_los_triggers_la_salud_lo_dice_y_responde_503(client):
    """El contraste, que es lo único que convierte el verde de arriba en algo.

    Se quitan de verdad y se vuelven a poner: comprobar esto con un `mock` diría
    que la función sabe leer un conjunto vacío, no que sepa mirar la base.
    """
    from django.db import connection

    quitar = """
        DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_auditlog;
        DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_auditlog;
        DROP TRIGGER IF EXISTS audit_log_no_update ON audit_auditlog;
    """
    with connection.cursor() as cursor:
        cursor.execute(quitar)
    try:
        respuesta = client.get("/api/health/")
    finally:
        call_command("ensure_append_only", stdout=StringIO())

    assert respuesta.status_code == 503
    detalle = respuesta.json()["checks"]["audit_append_only"]
    assert detalle["ok"] is False
    assert "audit_log_no_update" in detalle["detail"]

    # Y repuestos, vuelve a estar sano: el comando de reparación hace su trabajo.
    assert client.get("/api/health/").status_code == 200
