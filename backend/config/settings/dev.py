"""Entorno de desarrollo: cómodo, verboso y sin secretos reales."""

import sys

from .base import *
from .base import env

DEBUG = True

# Any host will do in development; the container provides the isolation.
ALLOWED_HOSTS = ["*"]

# The Vite SPA runs outside the API container.
#
# El puerto sale de `OTT_PORT_WEB`, el mismo que publica el compose. Estaba
# escrito a mano, y eso convertía una opción documentada en una trampa: quien
# mueve el puerto ---para levantar esto junto a otro proyecto, que es justo por
# lo que existe la variable--- se encuentra con que no puede entrar, y la
# pantalla le dice «No hay conexión con el servidor», que apunta a cualquier
# sitio menos a CORS. Un valor por defecto que se contradice con otro valor por
# defecto del mismo repositorio es peor que no tenerlo.
_PUERTO_WEB = env.int("OTT_PORT_WEB", default=3000)
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[f"http://localhost:{_PUERTO_WEB}", f"http://127.0.0.1:{_PUERTO_WEB}"],
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += ["django_extensions"]

# Short passwords in development, so the sample data is not a fight.
AUTH_PASSWORD_VALIDATORS = []

# Throttling counts in the cache, and the cache is Redis: shared between runs
# and between the suite and whoever is using the app. Under test that turns
# "five sign-ins a minute" into a limit the *suite* hits, and the failure looks
# like a broken login rather than a full bucket. A local cache per process
# keeps the throttles real and the counters private.
if env.bool("PYTEST_RUNNING", default=False) or "pytest" in sys.argv[0]:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Y lo mismo para la suite de navegador, que no pasa por pytest.
#
# Playwright habla con **este** servidor, así que su cubeta es la de Redis y la
# comparte entre tandas: doscientas pruebas a cinco peticiones cada una agotan
# las tres mil por hora de la cuenta que usan todas. Lo que se ve entonces no es
# un límite, es la pantalla de entrar en mitad de una prueba de Ajustes --- y se
# tarda media hora en descubrir que no hay ninguna regresión.
#
# Solo `user`, que es la que estorba. `login` se queda en cinco por minuto a
# propósito: hay una prueba que la agota para comprobar el aviso, y subirla aquí
# dejaría esa prueba comprobando otra cosa.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "user": env("DEV_USER_THROTTLE", default="100000/hour"),
    },
}
