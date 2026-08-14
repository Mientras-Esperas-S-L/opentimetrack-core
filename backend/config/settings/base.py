"""Configuración común a todos los entornos.

Todo valor sensible o dependiente del entorno se lee del entorno con
django-environ; nada se escribe aquí en duro.
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
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
    # Registra el `unaccent` que usa la búsqueda: sin esto el lookup no
    # existe y `last_name__unaccent__icontains` revienta en tiempo de
    # consulta, no al arrancar.
    "django.contrib.postgres",
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
    "apps.notifications",
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

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
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
    # The three of them. Only DjangoFilterBackend was enabled, so every
    # `search_fields` and `ordering_fields` declared on a viewset was decoration:
    # the search box on Personas answered `?search=cualquiercosa` with the whole
    # workforce, and its empty state --- "Nadie coincide con esa búsqueda" --- could
    # never appear. Neither filter does anything to a viewset that declares no
    # fields for it, so turning them on affects only the ones already asking.
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        # La nuestra, que ignora los acentos en los dos lados: `garcia`
        # encontraba a nadie, y con una plantilla española eso es la mitad
        # de los apellidos. Ver apps/common/filters.py.
        "apps.common.filters.BusquedaSinAcentos",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    # Without these three, the rates below are decoration. DRF only reads
    # `throttle_scope` when ScopedRateThrottle is among the classes, and only
    # applies the anon/user rates when those classes are listed --- so the four
    # limits were declared and nothing enforced them: unlimited password
    # guessing against /api/auth/token/, and unlimited recovery mail to any
    # address somebody cared to name.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
        # Not DRF's UserRateThrottle: it keys on `request.user.pk`, and an
        # application authenticates as a stand-in with no primary key. See
        # apps/common/throttling.py.
        "apps.common.throttling.PersonRateThrottle",
        "apps.common.throttling.ApplicationRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        # Era «1000/hour», el valor de ejemplo de DRF, y la única tasa de este
        # diccionario sin un motivo escrito al lado --- señal de que nadie la
        # había elegido.
        #
        # Medido el 13/08/2026: una pantalla de gestión cuesta unas cinco
        # peticiones, así que mil a la hora son doscientas pantallas, una cada
        # dieciocho segundos sostenidos. Un cierre de mes las gasta, y el
        # buscador de personas multiplica ---consulta mientras se teclea---.
        # Cincuenta por minuto no lo alcanza nadie a mano y sigue siendo un
        # techo firme contra el vaciado automático de la plantilla.
        #
        # Lo que hacía que esto doliera de verdad ya está arreglado aparte:
        # agotar la cubeta cerraba la sesión, porque la pantalla trataba
        # cualquier fallo de `/auth/me/` como un token inválido.
        "user": "3000/hour",
        # Password guessing and recovery mail. Per address for anonymous
        # callers, which is what an attacker varies last.
        "login": "5/min",
        # Renovar la sesión NO puede compartir cubeta con el login, y el motivo
        # solo se ve detrás de un NAT: la llamada es anónima, así que la cubeta
        # va por IP, y una oficina entera abriendo la aplicación a las nueve
        # agotaría cinco por minuto entre todos --- devolviendo al login a quien
        # tenía la sesión perfectamente viva. Y al reintentar entrar gastarían
        # la misma cubeta, así que la cosa se realimenta.
        #
        # Aflojarlo no abre nada: el token de refresco es un JWT firmado de un
        # solo uso (rota y se invalida el anterior), así que probar a ciegas no
        # es un ataque realista. El límite está para que nadie martillee.
        "session_renewal": "60/min",
        "punch": "10/min",
        # An integration polls, so it gets more room than a person --- and its
        # own bucket, so a loop in one client cannot starve the staff.
        "application": "6000/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_LIFETIME_MIN", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Si /api/schema/ y /api/docs/ responden sin sesión. El producto es AGPL, así
# que el esquema no es un secreto ---está en el código---, pero es la instancia
# del cliente la que lo publica y en un despliegue cerrado no hay razón para
# anunciar la superficie completa de la API a quien pase por delante.
#
# Por defecto sí: es lo que hace utilizable una API, y quien autoaloja se
# beneficia de tenerlo a mano.
PUBLISH_API_SCHEMA = env.bool("PUBLISH_API_SCHEMA", default=True)

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
    # El esquema declaraba solo el camino feliz: ni un 400, ni un 403, ni un 409
    # en ciento diecinueve operaciones, y ningún componente que dijera qué forma
    # tiene un error. Para un producto que vende su API como funcionalidad, eso
    # es justo la mitad que hace falta. El porqué y el cómo, en el módulo.
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.common.schema.documentar_los_errores",
    ],
    "ENUM_NAME_OVERRIDES": {
        "PunchTypeEnum": "apps.punches.models.PunchType.choices",
        # Punch.work_mode and User.default_work_mode hold the same two values.
        # They cannot share a TextChoices class --- punches depends on users, so
        # importing the other way would close a cycle --- and without this the
        # generator names one set of choices twice.
        "WorkModeEnum": "apps.punches.models.WorkMode.choices",
        # Igual: cómo se salda una hora extra sale en la propuesta y en el
        # intervalo ya saldado, y son el mismo juego de valores.
        "OvertimeSettlementEnum": "apps.punches.models.OvertimeSettlement.choices",
    },
}

# --------------------------------------------------------------- almacenamiento

# Donde van los justificantes. Dos opciones, y la eleccion es del despliegue:
#
#   STORAGE_BACKEND=filesystem  un volumen en disco. Suficiente para una empresa
#                               en un solo servidor, que es la mayoria de quien
#                               autoaloja. No hace falta levantar nada mas.
#   STORAGE_BACKEND=s3          cualquier almacen compatible con S3. Necesario
#                               en cuanto haya mas de un proceso sirviendo la
#                               API: con disco, cada uno veria sus propios
#                               ficheros y la mitad de las descargas fallaria.
#
# En los dos casos los ficheros se descargan por /api/absences/<id>/justification/,
# que comprueba permisos. MEDIA_URL no se sirve nunca: publicarlo dejaria los
# justificantes al alcance de cualquiera con el enlace.
STORAGE_BACKEND = env("STORAGE_BACKEND", default="filesystem")

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

# Los que tienen catálogo, y solo esos.
#
# Estaban los ocho de siempre con traducción de uno. Un idioma sin catálogo no
# falla: cae al castellano en silencio, porque `LANGUAGE_CODE` es `es` y Django
# encadena por ahí. O sea que ofrecerlo era prometer algo que no pasaba, y quien
# lo elegía se quedaba pensando que algo iba mal.
#
# El euskera llegó a tener catálogo y se retiró: iba incompleto ---los párrafos
# largos de derecho laboral quedaron sin traducir--- y medio idioma en un
# producto que explica obligaciones legales no es medio bueno, es confuso.
# El fichero está en el historial, listo para que lo termine quien sepa.
LANGUAGES = [
    ("es", _("Spanish")),
    ("ca", _("Catalan")),
    ("gl", _("Galician")),
    ("en", _("English")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# ---------------------------------------------------------- convenios colectivos

# Donde estan las fichas de convenio. Configurable porque el caso mas probable
# no es usar las nuestras: una empresa tiene asesoria laboral, y su asesoria
# sabe que convenio le aplica mejor que nosotros. Apuntar aqui a un directorio
# propio permite que escriban su ficha, la revisen y la mantengan ellos, sin
# depender de que publiquemos la suya.
#
# Las que vienen en el repositorio son las que hemos podido comprobar contra el
# boletin oficial. Ver agreements/README.md.
AGREEMENTS_DIR = Path(env("AGREEMENTS_DIR", default=str(BASE_DIR.parent / "agreements")))

# Los calendarios laborales, por el mismo motivo y con la misma disciplina: se
# transcriben de la resolucion anual del BOE y se publican por ano. Un
# despliegue puede apuntar a los suyos --- los que mantenga su asesoria, o unos
# ya verificados --- sin esperar a que publiquemos el ano siguiente.
#
# Lo que NUNCA va a estar aqui son los dos festivos locales de cada municipio:
# no existe registro nacional legible por maquina, y se meten a mano en cada
# centro de trabajo. Ver holidays/README.md.
HOLIDAYS_DIR = Path(env("HOLIDAYS_DIR", default=str(BASE_DIR.parent / "holidays")))

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

# La cabecera `Date` de cada respuesta, visible para el navegador.
#
# No está en la lista blanca de CORS —solo lo están Cache-Control,
# Content-Language, Content-Length, Content-Type, Expires, Last-Modified y
# Pragma— así que sin esto el navegador la recibe y la esconde del JavaScript.
#
# La necesita el reloj de la pantalla de fichar: enseña la hora del servidor,
# que es la que se va a guardar, en vez de la del dispositivo, que puede ir
# cinco minutos adelantada y sembrar justo la duda que el diseño quiere cerrar.
CORS_EXPOSE_HEADERS = [
    "Date",
    # Sin esto el navegador **oculta** la cabecera al JavaScript de la
    # aplicación, aunque el servidor la mande. Y con ella se va el nombre del
    # fichero, así que la descarga caía en un apaño: «informe» más la extensión
    # que se había pedido.
    #
    # Eso rompía la entrega de toda la empresa, que no es un PDF sino un **zip**
    # con un PDF por persona. Se guardaba como `informe.pdf`, y un zip con
    # nombre de PDF no lo abre nada. Reportado el 13/08/2026 con esa frase
    # exacta: «genera un pdf que no se puede abrir».
    #
    # De paso vuelven los nombres buenos que el servidor ya construía
    # ---`working-time_B00000001_2026-06-29_2026-08-13.zip`--- en vez de un
    # «informe.pdf» que no dice de quién ni de cuándo.
    "Content-Disposition",
]

# ---------------------------------------------------------- trabajos periódicos

# Quién repite los trabajos que se repiten: `cron` o `celery`.
#
# Por defecto cron, y es una postura, no una pereza: el despliegue típico de
# esto es una empresa con veinte personas en un servidor, y ahí cron ya está
# instalado, no se cae, no hay que vigilarlo y una línea en la crontab es toda
# la configuración. Pedirle un broker y dos procesos más para ejecutar un
# comando cada cinco minutos es cobrarle infraestructura que no necesita.
#
# Quien ya tiene varias máquinas, quiere ver los trabajos y reintentarlos, o no
# quiere depender de la crontab de un servidor concreto, pone `celery` y levanta
# el worker y el beat. La lógica es la misma: las tareas de Celery llaman al
# mismo comando de gestión que llamaría cron.
SCHEDULER = env("SCHEDULER", default="cron")
if SCHEDULER not in ("cron", "celery"):
    raise ImproperlyConfigured(f"SCHEDULER debe ser 'cron' o 'celery', no {SCHEDULER!r}")

# Cada cuánto se miran los recordatorios pendientes. Vale para las dos vías: es
# el intervalo que se documenta para la crontab y el que programa celery-beat.
REMINDER_EVERY_MINUTES = env.int("REMINDER_EVERY_MINUTES", default=5)

# El mismo Redis que la caché salvo que se diga otra cosa: quien separa los
# dos ya sabe por qué lo hace, y quien no, no tiene que montar dos.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TIMEZONE = TIME_ZONE
# Un recordatorio de fichar que se entrega media hora tarde no recuerda nada.
# Mejor perderlo que confundir a quien lo reciba fuera de su momento.
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=300)

# ------------------------------------------------------ avisos en el navegador

# Web Push necesita un par de claves propio del despliegue (VAPID). Se genera
# una vez con `python manage.py vapid_keys` y vive en el entorno. Sin claves, el
# push está apagado y todo sigue funcionando por correo: es una vía más, no un
# requisito, y el producto tiene que poder instalarse sin ella.
WEBPUSH_PUBLIC_KEY = env("WEBPUSH_PUBLIC_KEY", default="")
WEBPUSH_PRIVATE_KEY = env("WEBPUSH_PRIVATE_KEY", default="")
# Contacto al que el servicio de push del navegador escribiría si algo va mal.
# Lo exige el estándar VAPID; ha de ser un mailto: o una URL.
WEBPUSH_SUBJECT = env("WEBPUSH_SUBJECT", default=f"mailto:{DEFAULT_FROM_EMAIL}")
# Cuánto guarda el servicio del navegador un aviso que no se pudo entregar.
# Seis horas: un recordatorio de fichar que llega al día siguiente no recuerda
# nada, confunde.
WEBPUSH_TTL_SECONDS = env.int("WEBPUSH_TTL_SECONDS", default=6 * 60 * 60)

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
