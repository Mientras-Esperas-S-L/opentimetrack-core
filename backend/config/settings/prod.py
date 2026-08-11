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

# Supporting documents go to S3/MinIO, never to the container's disk.
#
# Encryption at rest is OFF unless asked for. It is not a default because
# SSE-S3 needs a key manager on the storage side, and turning it on without one
# makes every upload fail. Where the storage supports it --- and a sick-leave
# note is health data, so it should --- set STORAGE_ENCRYPTION=AES256.
#
# Do not describe this bucket as encrypted anywhere unless that variable is set:
# a private ACL and short-lived signed URLs are access control, which is a
# different thing.
_storage_options = {
    "endpoint_url": env("STORAGE_ENDPOINT"),
    "access_key": env("STORAGE_ACCESS_KEY"),
    "secret_key": env("STORAGE_SECRET_KEY"),
    "bucket_name": env("STORAGE_BUCKET"),
    "file_overwrite": False,
    "default_acl": "private",
    "querystring_auth": True,
    "querystring_expire": 300,
}

STORAGE_ENCRYPTION = env("STORAGE_ENCRYPTION", default="")
if STORAGE_ENCRYPTION:
    _storage_options["object_parameters"] = {"ServerSideEncryption": STORAGE_ENCRYPTION}

STORAGES["default"] = {
    "BACKEND": "storages.backends.s3.S3Storage",
    "OPTIONS": _storage_options,
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
