"""Entorno de desarrollo: cómodo, verboso y sin secretos reales."""

import sys

from .base import *
from .base import env

DEBUG = True

# Any host will do in development; the container provides the isolation.
ALLOWED_HOSTS = ["*"]

# The Vite SPA runs outside the API container.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
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
