"""Entorno de producción: cabeceras, TLS obligatorio y nada de DEBUG."""

from .base import *
from .base import env

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

# TLS obligatorio (convención de la API: HTTPS con HSTS).
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Los justificantes van a S3/MinIO, nunca al disco del contenedor.
STORAGES["default"] = {
    "BACKEND": "storages.backends.s3.S3Storage",
    "OPTIONS": {
        "endpoint_url": env("STORAGE_ENDPOINT"),
        "access_key": env("STORAGE_ACCESS_KEY"),
        "secret_key": env("STORAGE_SECRET_KEY"),
        "bucket_name": env("STORAGE_BUCKET"),
        "file_overwrite": False,
        "default_acl": "private",
        "querystring_auth": True,
        "querystring_expire": 300,
    },
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
