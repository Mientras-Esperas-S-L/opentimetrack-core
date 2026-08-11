"""Root URLs.

Convention: everything hangs off /api/. The /api/v1/ version prefix is reserved
and omitted while only one version exists.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.common.views import HealthView
from apps.punches.delegated import DelegatedPunchView
from apps.punches.views import PunchViewSet
from apps.reports.views import ReportView
from apps.users.views import (
    DepartmentViewSet,
    MeView,
    PasswordResetRequestView,
    PasswordSetView,
    SignInView,
    SignOutView,
    SignUpView,
    UserViewSet,
)

router = DefaultRouter()
router.register("employees", UserViewSet, basename="employee")
router.register("departments", DepartmentViewSet, basename="department")
router.register("punches", PunchViewSet, basename="punch")

auth_patterns = [
    path("register/", SignUpView.as_view(), name="register"),
    path("token/", SignInView.as_view(), name="token"),
    path("logout/", SignOutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("set-password/", PasswordSetView.as_view(), name="set-password"),
]

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/auth/", include((auth_patterns, "auth"))),
    path("api/reports/working-time/", ReportView.as_view(), name="working-time-report"),
    path(
        "api/punches/delegated/",
        DelegatedPunchView.as_view(),
        name="punch-delegated",
    ),
    path("api/", include(router.urls)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += [path("admin/", admin.site.urls)]
