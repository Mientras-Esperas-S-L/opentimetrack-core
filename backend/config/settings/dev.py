"""Entorno de desarrollo: cómodo, verboso y sin secretos reales."""

from .base import *
from .base import env

DEBUG = True

# En desarrollo cualquier host vale; el aislamiento lo da el contenedor.
ALLOWED_HOSTS = ["*"]

# El SPA de Vite corre fuera del contenedor de la API.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += ["django_extensions"]

# Contraseñas cortas en desarrollo, para no pelearse con los datos de ejemplo.
AUTH_PASSWORD_VALIDATORS = []
