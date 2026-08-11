"""Configuración común a todos los entornos.

Todo valor sensible o dependiente del entorno se lee del entorno con
django-environ; nada se escribe aquí en duro.
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------- aplicaciones

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
]

# Order matters: `common` and `tenants` are the base and depend on nobody. No
# domain app imports another except through that hierarchy, and `audit` learns
# what happened through signals.
LOCAL_APPS = [
    "apps.common",
    "apps.tenants",
    "apps.users",
    "apps.punches",
    "apps.absences",
    "apps.shifts",
    "apps.audit",
    "apps.reports",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Resolves the active language from the Accept-Language header.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # After authentication: both need to know who is calling.
    "apps.common.middleware.TenantMiddleware",
    "apps.common.middleware.LocaleAndTimeZoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ------------------------------------------------------------------ persistencia

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------- autenticación

AUTH_USER_MODEL = "users.User"

# Email is unique per company rather than globally, so authentication has to
# resolve the company first. See apps/users/backends.py.
# Exactly one, on purpose. Leaving ModelBackend behind as a fallback would undo
# our security rejections: it only looks at the address and is_active, so it
# would accept an email that is ambiguous across companies, or someone from a
# deactivated company. TenantEmailBackend inherits from ModelBackend, so the
# Django admin's permission resolution is preserved.
AUTHENTICATION_BACKENDS = [
    "apps.users.backends.TenantEmailBackend",
]

# RF-01.6: strong hashing. Argon2 first; the rest stay as fallbacks so legacy
# passwords can still be verified if any are ever imported.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------------- API

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Applications first: their token carries a prefix, so it is cheap to
        # recognise and it hands over to JWT when it is not one of theirs.
        "apps.common.authentication.ApplicationAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "1000/hour",
        "login": "5/min",
        "punch": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_LIFETIME_MIN", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "OpenTimeTrack Core",
    "DESCRIPTION": (
        "Registro horario conforme al artículo 34.9 del Estatuto de los Trabajadores. "
        "La marca temporal de un fichaje la fija siempre el servidor."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    # PunchType appears both on the clock event and on a correction request.
    # Without this the generator invents two names for one set of choices, and a
    # client generated from the schema ends up with duplicate types.
    "ENUM_NAME_OVERRIDES": {
        "PunchTypeEnum": "apps.punches.models.PunchType.choices",
    },
}

# --------------------------------------------------------------- almacenamiento

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ------------------------------------------------------------ internationalisation

# Spanish is the reference translation because the first legal framework covered
# is the Spanish one, but nothing in the domain is tied to a country: every
# user-facing string goes through gettext and every tenant carries its own time
# zone. Adding a locale is dropping a .po file in locale/.
LANGUAGE_CODE = env("LANGUAGE_CODE", default="es")

LANGUAGES = [
    ("es", _("Spanish")),
    ("en", _("English")),
    ("ca", _("Catalan")),
    ("gl", _("Galician")),
    ("eu", _("Basque")),
    ("fr", _("French")),
    ("pt", _("Portuguese")),
    ("de", _("German")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# Storage is always UTC. Each tenant renders in its own zone, which is a field of
# the tenant, not a global setting: a single deployment can serve a company in
# Madrid and another one in the Canary Islands -- two zones inside Spain alone --
# or anywhere else.
TIME_ZONE = "UTC"
DEFAULT_TENANT_TIME_ZONE = env("DEFAULT_TENANT_TIME_ZONE", default="Europe/Madrid")

USE_I18N = True
USE_L10N = True
USE_TZ = True

# ------------------------------------------------------------------------ correo

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@opentimetrack.local")

# Where the password links point. The panel lives apart from the API, so it
# cannot be derived from the request.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# How long an account link lasts, in seconds.
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=60 * 60 * 24)

# ------------------------------------------------------------------------ registro

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        # Dedicated channel for security-relevant events.
        "security": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
