"""One public address, and production refusing to start on one that cannot work.

Each case loads the production settings in a process of its own, with only the
environment it names: settings are read once, at import, so the only honest way
to see what an installation gets from its environment is to start one.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

BACKEND = Path(__file__).resolve().parents[3]

#: What any production installation has to have anyway, and nothing about addresses.
BASE_ENV = {
    "SECRET_KEY": "not-a-real-one",
    "DATABASE_URL": "postgresql://ott:ott@db.invalid:5432/ott",
    "STORAGE_BACKEND": "filesystem",
}

READ = [
    "FRONTEND_URL",
    "API_URL",
    "SSO_WEB_URL",
    "SSO_REDIRECT_URI",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "SECURE_SSL_REDIRECT",
    "SESSION_COOKIE_SECURE",
    "SECURE_HSTS_SECONDS",
]


def start(
    env: dict, module: str = "import config.settings.prod as s"
) -> subprocess.CompletedProcess:
    script = f"import json\n{module}\nprint(json.dumps({{k: getattr(s, k) for k in {READ!r}}}))"
    return subprocess.run(  # noqa: S603 --- our own interpreter, our own script
        [sys.executable, "-c", script],
        cwd=BACKEND,
        env={"PATH": os.environ.get("PATH", ""), **BASE_ENV, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


def settings_for(env: dict) -> dict:
    result = start(env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def refusal_for(env: dict) -> str:
    result = start(env)
    assert result.returncode != 0, f"started with {env}"
    return result.stderr


def test_one_address_is_enough():
    s = settings_for({"PUBLIC_URL": "https://time.example.test/"})

    assert s["FRONTEND_URL"] == "https://time.example.test"
    assert s["SSO_WEB_URL"] == "https://time.example.test"
    assert s["API_URL"] == "https://time.example.test/api"
    assert s["SSO_REDIRECT_URI"] == "https://time.example.test/api/auth/sso/callback/"
    assert s["ALLOWED_HOSTS"] == ["time.example.test"]
    assert s["CORS_ALLOWED_ORIGINS"] == ["https://time.example.test"]
    assert s["SECURE_SSL_REDIRECT"] is True
    assert s["SESSION_COOKIE_SECURE"] is True


def test_an_api_on_its_own_host():
    s = settings_for(
        {
            "PUBLIC_URL": "https://time.example.test",
            "PUBLIC_API_URL": "https://api.time.example.test/api",
        }
    )

    assert s["SSO_REDIRECT_URI"] == "https://api.time.example.test/api/auth/sso/callback/"
    assert s["ALLOWED_HOSTS"] == ["api.time.example.test", "time.example.test"]
    assert s["CORS_ALLOWED_ORIGINS"] == ["https://time.example.test"]


def test_an_installation_set_up_the_old_way_keeps_working():
    """Before PUBLIC_URL, every setting was written by hand. They still win."""
    s = settings_for(
        {
            "FRONTEND_URL": "https://time.example.test",
            "ALLOWED_HOSTS": "time.example.test,localhost,127.0.0.1",
            "CORS_ALLOWED_ORIGINS": "https://time.example.test",
            "SSO_WEB_URL": "https://time.example.test",
            "SSO_REDIRECT_URI": "https://time.example.test/api/auth/sso/callback/",
        }
    )

    assert s["ALLOWED_HOSTS"] == ["time.example.test", "localhost", "127.0.0.1"]
    assert s["SSO_REDIRECT_URI"] == "https://time.example.test/api/auth/sso/callback/"
    assert s["API_URL"] == "https://time.example.test/api"


def test_without_the_web_address_the_provider_never_answers_in_json():
    """The old default: the session tokens, as JSON, in the browser of whoever signs in."""
    s = settings_for({"FRONTEND_URL": "https://time.example.test", "SSO_WEB_URL": ""})

    assert s["SSO_WEB_URL"] == "https://time.example.test"


def test_with_no_address_it_does_not_start():
    assert "PUBLIC_URL is required" in refusal_for({})


@pytest.mark.parametrize(
    "env, says",
    [
        ({"PUBLIC_URL": "time.example.test"}, "full address"),
        ({"PUBLIC_URL": "https://time.example.test/fichaje"}, "path prefix"),
        ({"PUBLIC_URL": "https://time.example.test?x=1"}, "query"),
        (
            {
                "PUBLIC_URL": "https://time.example.test",
                "PUBLIC_API_URL": "https://api.time.example.test",
            },
            "end in /api",
        ),
        ({"PUBLIC_URL": "http://time.example.test"}, "in the clear"),
        (
            {
                "PUBLIC_URL": "https://time.example.test",
                "PUBLIC_API_URL": "http://api.time.example.test/api",
            },
            "in the clear",
        ),
    ],
)
def test_an_address_that_cannot_work_is_refused(env, says):
    assert says in refusal_for(env)


def test_http_inside_a_private_network_when_asked_for():
    s = settings_for({"PUBLIC_URL": "http://fichaje.lan:8080", "ALLOW_INSECURE_HTTP": "true"})

    assert s["SECURE_SSL_REDIRECT"] is False
    assert s["SESSION_COOKIE_SECURE"] is False
    assert s["SECURE_HSTS_SECONDS"] == 0
    assert s["SSO_REDIRECT_URI"] == "http://fichaje.lan:8080/api/auth/sso/callback/"


def test_gunicorn_starts_on_production_settings_unless_told():
    """It used to fall back to development: DEBUG on, any host, mail to the console."""
    result = start({}, module="import config.wsgi\nfrom django.conf import settings as s")

    assert result.returncode != 0
    assert "PUBLIC_URL is required in production" in result.stderr


# ------------------------------------------------------------ /api/instance/


@pytest.mark.django_db
@override_settings(
    SSO_REDIRECT_URI="https://time.example.test/api/auth/sso/callback/",
    SSO_WEB_URL="https://time.example.test",
    API_URL="https://time.example.test/api",
)
def test_the_installation_says_which_return_address_to_register():
    """What an integration registers at its provider, as this installation will send it.

    The request arrives as the proxy passes it on --- plain http, the internal
    host --- and the answer is still the public address."""
    response = APIClient().get("/api/instance/", HTTP_HOST="localhost", secure=False)

    assert response.status_code == 200
    assert response.data == {
        "product": "OpenTimeTrack",
        "name": "OpenTimeTrack",
        "version": response.data["version"],
        "web_url": "https://time.example.test",
        "api_url": "https://time.example.test/api",
        "sso_callback_url": "https://time.example.test/api/auth/sso/callback/",
    }


@pytest.mark.django_db
@override_settings(SSO_REDIRECT_URI="")
def test_in_development_the_return_address_is_the_one_the_start_sends():
    """Without PUBLIC_URL it comes from the request, and it is the same one the
    sign-in sends to the provider --- the two must never disagree."""
    from django.test import RequestFactory

    from apps.tenants.sso_views import redirect_uri

    published = APIClient().get("/api/instance/").data["sso_callback_url"]

    assert published == redirect_uri(RequestFactory().get("/"))
