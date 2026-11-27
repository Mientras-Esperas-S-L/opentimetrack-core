"""Avisos en la aplicación de Android, por Firebase Cloud Messaging.

Como en la web, lo que se comprueba es lo nuestro y no la entrega: que sin
clave no se intenta nada, que una instalación muerta se borra sola, que lo
personal no viaja por el relevo de Google, que el móvil que cambia de manos no
sigue avisando al de antes y que nadie silencia el móvil de otro.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.notifications import fcm
from apps.notifications.models import NativePushDevice
from apps.notifications.push import send_push
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


@pytest.fixture
def colleague(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="luis@example.com", password=PASSWORD, tenant=company, first_name="Luis"
        )


@pytest.fixture
def private_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return key, pem


@pytest.fixture
def credentials(settings, tmp_path, private_key):
    """Una clave de cuenta de servicio de mentira, con la forma de la de verdad."""
    _, pem = private_key
    path = tmp_path / "fcm.json"
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "proyecto-de-prueba",
                "client_email": "envio@proyecto-de-prueba.iam.gserviceaccount.com",
                "private_key": pem,
                "token_uri": "https://oauth2.example/token",
            }
        )
    )
    settings.FCM_CREDENTIALS_FILE = str(path)
    fcm._token.update(value="", expires=0.0)
    yield path
    fcm._token.update(value="", expires=0.0)


def register(company, person, token="token-a"):  # noqa: S107 --- un token de FCM falso
    with tenant_context(company.id):
        return NativePushDevice.objects.create(tenant=company, employee=person, token=token)


def client_for(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://fcm", code, "error", {}, io.BytesIO(body))


# ------------------------------------------------------------------ el envío


@pytest.mark.django_db
def test_without_the_key_file_the_app_gets_nothing(settings, company, worker):
    settings.FCM_CREDENTIALS_FILE = ""
    register(company, worker)
    with patch("apps.notifications.fcm.send_one") as sent, tenant_context(company.id):
        assert send_push(worker, title="t", body="b") == 0
    sent.assert_not_called()


@pytest.mark.django_db
def test_a_notification_reaches_every_install(credentials, settings, company, worker):
    settings.WEBPUSH_PUBLIC_KEY = settings.WEBPUSH_PRIVATE_KEY = ""
    register(company, worker, "token-a")
    register(company, worker, "token-b")
    with (
        patch("apps.notifications.fcm.send_one", return_value="sent") as sent,
        tenant_context(company.id),
    ):
        assert send_push(worker, title="Ficha", body="Te falta la salida", url="/fichar") == 2
        assert all(d.last_sent_at for d in NativePushDevice.objects.all())
    assert {c.args[0] for c in sent.call_args_list} == {"token-a", "token-b"}


@pytest.mark.django_db
def test_an_uninstalled_app_deletes_itself(credentials, company, worker):
    register(company, worker, "muerto")
    register(company, worker, "vivo")
    outcomes = {"muerto": "gone", "vivo": "sent"}
    with (
        patch("apps.notifications.fcm.send_one", side_effect=lambda t, **_: outcomes[t]),
        tenant_context(company.id),
    ):
        send_push(worker, title="t", body="b")
        assert list(NativePushDevice.objects.values_list("token", flat=True)) == ["vivo"]


@pytest.mark.django_db
def test_personal_details_do_not_travel_through_the_relay(credentials, company, worker):
    """El cuerpo de un cambio de turno lleva días y horas: por FCM no va."""
    register(company, worker)
    with (
        patch("apps.notifications.fcm.send_one", return_value="sent") as sent,
        tenant_context(company.id),
    ):
        send_push(worker, title="Tu turno ha cambiado", body="Lunes 08:00-15:00", personal=True)
    assert "08:00" not in sent.call_args.kwargs["body"]
    assert sent.call_args.kwargs["title"] == "Tu turno ha cambiado"


@pytest.mark.django_db
def test_a_failing_relay_does_not_break_the_caller(credentials, company, worker):
    register(company, worker)
    with (
        patch("apps.notifications.fcm.send_one", side_effect=RuntimeError("boom")),
        tenant_context(company.id),
    ):
        assert send_push(worker, title="t", body="b") == 0


# ------------------------------------------------------------- el protocolo


def test_the_message_goes_with_a_token_signed_by_the_key(credentials, private_key):
    key, _ = private_key
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if "oauth2" in request.full_url:
            return FakeResponse(json.dumps({"access_token": "acceso", "expires_in": 3600}).encode())
        return FakeResponse(b"{}")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert fcm.send_one("token-a", title="t", body="b", url="/fichar", tag="x") == "sent"
        # El acceso se reutiliza: el segundo aviso no vuelve a pedirlo.
        assert fcm.send_one("token-a", title="t", body="b", url="/fichar", tag="x") == "sent"

    oauth, send, again = calls
    assertion = dict(p.split("=", 1) for p in oauth.data.decode().split("&"))["assertion"]
    claims = jwt.decode(
        assertion,
        key.public_key(),
        algorithms=["RS256"],
        audience="https://oauth2.example/token",
    )
    assert claims["scope"] == fcm.SCOPE
    assert send.full_url.endswith("/projects/proyecto-de-prueba/messages:send")
    assert send.headers["Authorization"] == "Bearer acceso"
    message = json.loads(send.data)["message"]
    assert message["token"] == "token-a"
    assert message["data"] == {"url": "/fichar", "tag": "x"}
    assert again.full_url == send.full_url


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (http_error(404, b'{"error":{"status":"NOT_FOUND"}}'), "gone"),
        (http_error(400, b'{"error":{"message":"The registration token is not valid"}}'), "gone"),
        # Un 400 por otra cosa es culpa nuestra, no del móvil: no se borra.
        (
            http_error(400, b'{"error":{"message":"Invalid value at message.android.ttl"}}'),
            "failed",
        ),
        (http_error(503), "failed"),
    ],
)
def test_what_the_relay_answers(credentials, error, outcome):
    fcm._token.update(value="acceso", expires=10**12)
    with patch("urllib.request.urlopen", side_effect=error):
        assert fcm.send_one("t", title="t", body="b", url="/", tag="") == outcome


def test_a_file_that_is_not_a_service_account_key_leaves_it_off(settings, tmp_path):
    path = tmp_path / "otra-cosa.json"
    path.write_text(json.dumps({"project_info": {}}))
    settings.FCM_CREDENTIALS_FILE = str(path)
    assert fcm.fcm_is_configured() is False


# -------------------------------------------------------------------- la API


@pytest.mark.django_db
def test_the_api_says_whether_the_app_can_be_notified(credentials):
    assert client_for().get("/api/push/key/").json()["app_enabled"] is True


@pytest.mark.django_db
def test_registering_twice_from_the_same_install_is_one_row(company, worker):
    c = client_for(worker)
    payload = {"token": "token-a", "device_label": "Android"}
    assert c.post("/api/push/devices/", payload, format="json").status_code == 201
    assert c.post("/api/push/devices/", payload, format="json").status_code == 201
    with tenant_context(company.id):
        assert NativePushDevice.objects.count() == 1


@pytest.mark.django_db
def test_a_phone_that_changes_hands_stops_notifying_the_previous_person(company, worker, colleague):
    register(company, worker, "compartido")
    client_for(colleague).post("/api/push/devices/", {"token": "compartido"}, format="json")
    with tenant_context(company.id):
        device = NativePushDevice.objects.get(token="compartido")
        assert device.employee == colleague


@pytest.mark.django_db
def test_nobody_can_unregister_somebody_elses_phone(company, worker, colleague):
    register(company, worker, "de-ana")
    client_for(colleague).delete("/api/push/devices/", {"token": "de-ana"}, format="json")
    with tenant_context(company.id):
        assert NativePushDevice.objects.filter(token="de-ana").exists()


@pytest.mark.django_db
def test_unregistering_ones_own_phone(company, worker):
    register(company, worker, "de-ana")
    answer = client_for(worker).delete("/api/push/devices/", {"token": "de-ana"}, format="json")
    assert answer.status_code == 204
    with tenant_context(company.id):
        assert not NativePushDevice.objects.exists()


def test_registering_needs_a_session(db):
    answer = client_for().post("/api/push/devices/", {"token": "x"}, format="json")
    assert answer.status_code == 401


# ------------------------------------------------------ el canal que suena


@pytest.mark.django_db
def test_only_the_urgent_ones_go_through_the_channel_that_rings(
    credentials, settings, company, worker
):
    """Un recordatorio de fichar cae sobre la pantalla; un turno que cambia la
    semana que viene no tiene por qué."""
    settings.WEBPUSH_PUBLIC_KEY = settings.WEBPUSH_PRIVATE_KEY = ""
    register(company, worker, "token-a")
    with (
        patch("apps.notifications.fcm.send_one", return_value="sent") as sent,
        tenant_context(company.id),
    ):
        send_push(worker, title="t", body="b", urgent=True)
        send_push(worker, title="t", body="b")

    urgent, calm = sent.call_args_list
    assert urgent.kwargs["channel"] == fcm.URGENT_CHANNEL
    assert calm.kwargs["channel"] == ""


def test_the_channel_travels_in_the_android_part(credentials):
    sends = []

    def fake_urlopen(request, timeout):
        if "oauth2" in request.full_url:
            return FakeResponse(json.dumps({"access_token": "acceso", "expires_in": 3600}).encode())
        sends.append(json.loads(request.data)["message"])
        return FakeResponse(b"{}")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        fcm.send_one("t", title="t", body="b", url="/", tag="x", channel="recordatorios")
        fcm.send_one("t", title="t", body="b", url="/", tag="")

    assert sends[0]["android"]["notification"] == {"tag": "x", "channel_id": "recordatorios"}
    # Sin canal ni tag no se manda nada: un channel_id vacío Google lo rechaza.
    assert sends[1]["android"]["notification"] == {}
