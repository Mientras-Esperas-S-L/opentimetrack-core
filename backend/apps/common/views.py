"""Vistas de operación: comprobación de salud."""

from __future__ import annotations

from typing import ClassVar

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
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
    """
    if connection.vendor != "postgresql":
        return True, "no aplica"
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgrelid = 'audit_auditlog'::regclass AND NOT tgisinternal"
            )
            puestos = {fila[0] for fila in cursor.fetchall()}
    except Exception as exc:
        return False, exc.__class__.__name__

    faltan = [nombre for nombre in GUARDIANES if nombre not in puestos]
    if faltan:
        return False, "el rastro no es inmutable, faltan: " + ", ".join(faltan)
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
