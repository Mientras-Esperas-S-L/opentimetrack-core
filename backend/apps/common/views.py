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
        healthy = db_ok and cache_ok

        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "version": __version__,
                "checks": {
                    "database": {"ok": db_ok, "detail": db_detail},
                    "cache": {"ok": cache_ok, "detail": cache_detail},
                },
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
