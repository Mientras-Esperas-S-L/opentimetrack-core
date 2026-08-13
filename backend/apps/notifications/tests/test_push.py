"""Avisos en el navegador.

Lo que se comprueba no es que llegue un aviso —eso depende de Google y de
Mozilla— sino lo que sí es nuestro: que sin claves no se intenta nada, que una
dirección muerta se borra sola, que nadie puede silenciar el dispositivo de otro
y que un fallo de envío no rompe el recordatorio ni toca el registro.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.notifications.models import PushSubscription
from apps.notifications.push import push_is_configured, send_push
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
KEYS = {"WEBPUSH_PUBLIC_KEY": "clave-publica", "WEBPUSH_PRIVATE_KEY": "clave-privada"}


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


def subscribe(company, person, endpoint="https://push.example/abc"):
    with tenant_context(company.id):
        return PushSubscription.objects.create(
            tenant=company, employee=person, endpoint=endpoint, p256dh="pk", auth="secreto"
        )


def client_for(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


# ------------------------------------------------------------------ el envío


@pytest.mark.django_db
def test_without_keys_nothing_is_sent(settings, company, worker):
    """Un despliegue sin claves no intenta nada, y no falla por ello."""
    settings.WEBPUSH_PUBLIC_KEY = ""
    settings.WEBPUSH_PRIVATE_KEY = ""
    subscribe(company, worker)

    with tenant_context(company.id):
        assert push_is_configured() is False
        assert send_push(worker, title="hola", body="qué tal") == 0


@pytest.mark.django_db
def test_a_notification_reaches_every_registered_browser(settings, company, worker):
    for key, value in KEYS.items():
        setattr(settings, key, value)
    subscribe(company, worker, "https://push.example/movil")
    subscribe(company, worker, "https://push.example/portatil")

    with patch("pywebpush.webpush") as sent, tenant_context(company.id):
        delivered = send_push(worker, title="Recuerda fichar", body="Tu turno ha empezado")

    assert delivered == 2
    assert sent.call_count == 2
    # El contenido viaja como JSON, que es lo que el service worker lee.
    payload = sent.call_args.kwargs["data"]
    assert "Recuerda fichar" in payload


@pytest.mark.django_db
def test_a_dead_address_deletes_itself(settings, company, worker):
    """410 Gone: el navegador ya no existe. Guardar la fila es guardar basura
    que fallará en cada envío para siempre."""
    for key, value in KEYS.items():
        setattr(settings, key, value)
    subscribe(company, worker, "https://push.example/desinstalado")

    from pywebpush import WebPushException

    class Gone:
        status_code = 410

    error = WebPushException("gone")
    error.response = Gone()

    with patch("pywebpush.webpush", side_effect=error), tenant_context(company.id):
        assert send_push(worker, title="hola", body="qué tal") == 0
        assert PushSubscription.objects.count() == 0


@pytest.mark.django_db
def test_a_temporary_failure_keeps_the_subscription(settings, company, worker):
    """Un 503 del servicio de push es de ellos, no del navegador de la persona."""
    for key, value in KEYS.items():
        setattr(settings, key, value)
    subscribe(company, worker)

    from pywebpush import WebPushException

    class Busy:
        status_code = 503

    error = WebPushException("busy")
    error.response = Busy()

    with patch("pywebpush.webpush", side_effect=error), tenant_context(company.id):
        assert send_push(worker, title="hola", body="qué tal") == 0
        assert PushSubscription.objects.count() == 1


@pytest.mark.django_db
def test_a_reminder_survives_push_failing(settings, company, worker):
    """El recordatorio es una cortesía sobre el registro: si el aviso revienta,
    el correo sale igual y no se pierde nada del registro."""
    for key, value in KEYS.items():
        setattr(settings, key, value)
    subscribe(company, worker)

    from apps.punches.models import PunchReminder
    from apps.punches.reminders import DueReminder, _deliver

    with (
        patch("pywebpush.webpush", side_effect=RuntimeError("boom")),
        patch("django.core.mail.send_mail") as mail,
        tenant_context(company.id),
    ):
        _deliver(
            DueReminder(
                worker, __import__("datetime").date(2026, 9, 1), PunchReminder.Kind.CLOCK_IN
            )
        )

    assert mail.called


# --------------------------------------------------------------------- la API


@pytest.mark.django_db
def test_the_public_key_is_public(settings, company):
    settings.WEBPUSH_PUBLIC_KEY = "clave-publica"
    settings.WEBPUSH_PRIVATE_KEY = "clave-privada"
    body = client_for().get("/api/push/key/").json()
    assert body == {"enabled": True, "public_key": "clave-publica"}


@pytest.mark.django_db
def test_without_keys_the_api_says_so_instead_of_offering_it(settings):
    settings.WEBPUSH_PUBLIC_KEY = ""
    settings.WEBPUSH_PRIVATE_KEY = ""
    body = client_for().get("/api/push/key/").json()
    assert body == {"enabled": False, "public_key": ""}


@pytest.mark.django_db
def test_subscribing_twice_from_the_same_browser_is_one_row(company, worker):
    payload = {
        "endpoint": "https://push.example/abc",
        "p256dh": "pk",
        "auth": "secreto",
        "device_label": "Firefox · Linux",
    }
    c = client_for(worker)
    assert c.post("/api/push/subscriptions/", payload, format="json").status_code == 201
    # El navegador rota las claves de vez en cuando y vuelve a suscribirse.
    assert (
        c.post("/api/push/subscriptions/", {**payload, "p256dh": "pk2"}, format="json").status_code
        == 201
    )

    with tenant_context(company.id):
        assert PushSubscription.objects.count() == 1
        assert PushSubscription.objects.get().p256dh == "pk2"


@pytest.mark.django_db
def test_nobody_can_unsubscribe_somebody_elses_device(company, worker):
    with tenant_context(company.id):
        other = User.objects.create_user(
            email="otro@example.com", password=PASSWORD, tenant=company, first_name="Otro"
        )
    theirs = subscribe(company, other, "https://push.example/suyo")

    client_for(worker).delete(
        "/api/push/subscriptions/", {"endpoint": theirs.endpoint}, format="json"
    )

    with tenant_context(company.id):
        assert PushSubscription.objects.filter(pk=theirs.pk).exists()


@pytest.mark.django_db
def test_subscribing_needs_a_session():
    answer = client_for().post(
        "/api/push/subscriptions/",
        {"endpoint": "https://push.example/abc", "p256dh": "pk", "auth": "s"},
        format="json",
    )
    assert answer.status_code == 401
