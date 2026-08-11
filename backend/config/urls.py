"""Rutas raíz.

Convención: todo cuelga de /api/. El prefijo de versión /api/v1/ queda
reservado y hoy se omite mientras solo existe una versión.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from apps.common.views import HealthView

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += [path("admin/", admin.site.urls)]
