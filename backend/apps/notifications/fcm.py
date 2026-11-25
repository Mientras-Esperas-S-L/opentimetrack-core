"""Sending to the Android app, through Firebase Cloud Messaging.

Web Push is what browsers speak; an app installed from an APK is not a browser,
and on Android the only way to wake it with a notification is Google's own relay,
FCM. Unlike Web Push it needs an account: a Firebase project, and a service
account of that project allowed to send (`roles/firebasecloudmessaging.admin`,
nothing else). Its JSON key goes on the server, in the file `FCM_CREDENTIALS_FILE`
points to, and never in the repository.

Without that file this channel is simply off, as Web Push is without its keys.

No Google library on purpose: the protocol is two HTTPS calls --- trade a signed
JWT for an access token (RFC 7523, the same grant the identity provider code
already verifies) and post the message --- and `PyJWT` and `cryptography` are
already here. Pulling `firebase-admin` would bring a few dozen packages to audit
for those two calls.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TIMEOUT_SECONDS = 10

_token_lock = threading.Lock()
_token: dict = {"value": "", "expires": 0.0}


def fcm_is_configured() -> bool:
    return _credentials() is not None


@lru_cache(maxsize=1)
def _credentials_for(path: str) -> dict | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text())
    except OSError, ValueError:
        log.warning("FCM_CREDENTIALS_FILE no se puede leer: %s", path)
        return None
    needed = {"client_email", "private_key", "project_id", "token_uri"}
    if not needed <= data.keys():
        log.warning("FCM_CREDENTIALS_FILE no es la clave de una cuenta de servicio: %s", path)
        return None
    # La dirección a la que se manda la firma sale del fichero: solo por HTTPS, para
    # que un fichero cambiado no pueda hacer leer al servidor un `file:` local.
    if not str(data["token_uri"]).startswith("https://"):
        log.warning("FCM_CREDENTIALS_FILE trae un token_uri que no es HTTPS: %s", path)
        return None
    return data


def _credentials() -> dict | None:
    return _credentials_for(settings.FCM_CREDENTIALS_FILE)


def _access_token(creds: dict) -> str:
    """A token for the FCM API, reused until a minute before it expires."""
    import jwt

    with _token_lock:
        if _token["value"] and _token["expires"] - 60 > time.time():
            return _token["value"]
        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": creds["client_email"],
                "scope": SCOPE,
                "aud": creds["token_uri"],
                "iat": now,
                "exp": now + 3600,
            },
            creds["private_key"],
            algorithm="RS256",
        )
        body = urllib.parse.urlencode(
            {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
        ).encode()
        # token_uri es HTTPS por fuerza: ver _credentials_for.
        request = urllib.request.Request(creds["token_uri"], data=body, method="POST")  # noqa: S310
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            answer = json.load(response)
        _token["value"] = answer["access_token"]
        _token["expires"] = time.time() + int(answer.get("expires_in", 3600))
        return _token["value"]


def send_one(token: str, *, title: str, body: str, url: str, tag: str) -> str:
    """`sent`, `gone` (the app was uninstalled: delete the row) or `failed`."""
    creds = _credentials()
    if creds is None:
        return "failed"

    message = {
        "token": token,
        "notification": {"title": title, "body": body},
        # Lo lee la aplicación al pulsar el aviso, para abrir la pantalla que toca.
        "data": {"url": url, "tag": tag},
        "android": {
            # Un recordatorio de fichar que llega a la hora siguiente no sirve.
            "priority": "high",
            "ttl": f"{settings.WEBPUSH_TTL_SECONDS}s",
            # El mismo tag sustituye al aviso anterior en vez de apilarlos, como en la web.
            "notification": {"tag": tag} if tag else {},
        },
    }
    try:
        request = urllib.request.Request(
            f"https://fcm.googleapis.com/v1/projects/{creds['project_id']}/messages:send",
            data=json.dumps({"message": message}).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {_access_token(creds)}",
                "Content-Type": "application/json",
            },
        )
        # Dirección fija de Google, siempre HTTPS.
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):  # noqa: S310
            return "sent"
    except urllib.error.HTTPError as exc:
        # 404 UNREGISTERED: la aplicación se desinstaló o el token caducó para siempre.
        # 400 con INVALID_ARGUMENT puede ser el token mal formado, pero también un
        # mensaje nuestro mal hecho: solo se borra si el error lo dice del token.
        detail = exc.read().decode(errors="replace")
        if exc.code == 404 or (exc.code == 400 and "registration token" in detail.lower()):
            return "gone"
        log.warning("FCM rechazó el aviso (%s): %s", exc.code, detail[:300])
        return "failed"
    except Exception:
        log.exception("no se pudo enviar el aviso por FCM")
        return "failed"
