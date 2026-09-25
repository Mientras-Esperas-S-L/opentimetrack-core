"""Vistas de operación: comprobación de salud."""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config import __version__


def _check_database() -> tuple[bool, str]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return False, exc.__class__.__name__
    return True, "ok"


#: Los tres guardianes de `audit.0002_append_only_trigger`.
GUARDIANES = ("audit_log_no_update", "audit_log_no_delete", "audit_log_no_truncate")

#: Las dos tablas inmutables y los guardianes de cada una. La de la instalación
#: llegó después: lo que hacen sus cuentas tampoco se puede reescribir.
GUARDIANES_POR_TABLA = {
    "audit_auditlog": GUARDIANES,
    "audit_platformauditentry": (
        "platform_audit_no_update",
        "platform_audit_no_delete",
        "platform_audit_no_truncate",
    ),
}


def _check_audit_is_append_only() -> tuple[bool, str]:
    """Que el rastro siga siendo inmutable **en esta base**, no en la migración.

    «Un rastro de auditoría que puede editar aquel a quien incrimina no es
    prueba», dice la migración que los crea. Y estaban en la migración, con la
    migración marcada como aplicada y su función presente --- pero los tres
    triggers no estaban en la base de desarrollo, así que se podía editar y
    borrar el rastro sin que nada chistara.

    Da igual cómo se perdieron (una tabla recreada, una restauración, un
    `migrate --fake`): lo que importa es que una garantía que solo vive en una
    migración **se puede evaporar sin ruido**, y la única forma de saberlo es
    preguntárselo a la base de datos que está sirviendo.

    Aquí y no en una prueba: las pruebas corren sus migraciones enteras y
    siempre los ven. Es exactamente el sitio donde no estaba el problema.

    **Y estar no basta: hay que estar encendido.** `ALTER TABLE ... DISABLE
    TRIGGER` lo deja en `pg_trigger` con el mismo nombre y sin disparar, que es
    lo que hace `pg_restore --disable-triggers` --- la restauración que este mismo
    comentario ya nombraba entre las formas de perderlos. Medido: con el trigger
    apagado esta comprobación contestaba «ok» y una fila del rastro se dejaba
    reescribir. Un `tgenabled` de `D` (apagado) o `R` (solo en réplica) es tan
    inútil como no tenerlo, y se distingue de faltar porque el arreglo es otro:
    uno se vuelve a encender, el otro hay que recrearlo.
    """
    if connection.vendor != "postgresql":
        return True, "no aplica"
    estado: dict[str, str] = {}
    try:
        with connection.cursor() as cursor:
            for tabla in GUARDIANES_POR_TABLA:
                cursor.execute(
                    "SELECT tgname, tgenabled FROM pg_trigger "
                    "WHERE tgrelid = %s::regclass AND NOT tgisinternal",
                    [tabla],
                )
                estado.update(cursor.fetchall())
    except Exception as exc:
        return False, exc.__class__.__name__

    #: `O` dispara siempre en un servidor normal y `A` también en réplica. `D`
    #: no dispara nunca, y `R` solo cuando la sesión es de replicación, que en
    #: el servidor que atiende no ocurre.
    ENCENDIDOS = {"O", "A"}

    todos = [nombre for nombres in GUARDIANES_POR_TABLA.values() for nombre in nombres]
    faltan = [nombre for nombre in todos if nombre not in estado]
    apagados = [nombre for nombre in todos if nombre in estado and estado[nombre] not in ENCENDIDOS]
    if faltan or apagados:
        partes = []
        if faltan:
            partes.append("faltan: " + ", ".join(faltan))
        if apagados:
            partes.append("apagados: " + ", ".join(apagados))
        return False, "el rastro no es inmutable, " + "; ".join(partes)
    return True, "ok"


def _check_cache() -> tuple[bool, str]:
    try:
        cache.set("healthcheck", "1", timeout=5)
        if cache.get("healthcheck") != "1":
            return False, "lectura distinta de la escritura"
    except Exception as exc:
        return False, exc.__class__.__name__
    return True, "ok"


class HealthView(APIView):
    """Estado del servicio y de sus dependencias.

    Responde 200 si todo está sano y 503 si algo falla, para que un balanceador
    o una sonda externa puedan decidir sin interpretar el cuerpo.
    """

    permission_classes: ClassVar[list] = [AllowAny]
    authentication_classes: ClassVar[list] = []

    @extend_schema(
        summary="Comprobación de salud",
        description="Estado de la base de datos y de la caché. 200 sano, 503 degradado.",
        auth=[],
        responses={200: None, 503: None},
    )
    def get(self, request):
        db_ok, db_detail = _check_database()
        cache_ok, cache_detail = _check_cache()
        audit_ok, audit_detail = _check_audit_is_append_only()
        healthy = db_ok and cache_ok and audit_ok

        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "version": __version__,
                "checks": {
                    "database": {"ok": db_ok, "detail": db_detail},
                    "cache": {"ok": cache_ok, "detail": cache_detail},
                    "audit_append_only": {"ok": audit_ok, "detail": audit_detail},
                },
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class InstanceSerializer(serializers.Serializer):
    product = serializers.CharField(
        help_text="Always «OpenTimeTrack»: what answers at this address."
    )
    name = serializers.CharField(
        help_text="What people see here: «OpenTimeTrack», unless the installation sets its own."
    )
    version = serializers.CharField()
    web_url = serializers.CharField(help_text="Where people use the web app.")
    api_url = serializers.CharField(help_text="Where the API is, ending in /api.")
    sso_callback_url = serializers.CharField(
        help_text="The exact return address to register at an identity provider."
    )


class InstanceView(APIView):
    """What answers at this address, and where each of its parts lives.

    For whoever is about to connect to this installation. Setting up single
    sign-on means registering at the identity provider the exact address people
    come back to, compared character for character; guessing it from where the
    API happens to answer goes wrong behind a proxy, or with the API on a host
    of its own. This is the address this installation will actually send.

    Nothing here is secret: it is what a browser sees on the way in.
    """

    permission_classes: ClassVar[list] = [AllowAny]
    authentication_classes: ClassVar[list] = []

    @extend_schema(
        summary="Qué instalación es y dónde vive", auth=[], responses={200: InstanceSerializer}
    )
    def get(self, request):
        from apps.tenants.sso_views import redirect_uri

        return Response(
            {
                "product": "OpenTimeTrack",
                "name": settings.INSTALLATION_NAME,
                "version": __version__,
                "web_url": settings.SSO_WEB_URL or settings.FRONTEND_URL,
                "api_url": settings.API_URL,
                "sso_callback_url": redirect_uri(request),
            }
        )
