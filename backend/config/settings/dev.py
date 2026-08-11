"""Entorno de desarrollo: cómodo, verboso y sin secretos reales."""

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
