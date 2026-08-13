"""Root URLs.

Convention: everything hangs off /api/. The /api/v1/ version prefix is reserved
and omitted while only one version exists.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.absences.recovery_views import HolidayRecoveryView
from apps.absences.views import AbsenceViewSet, LeaveTypeViewSet
from apps.audit.views import AuditLogViewSet
from apps.common.views import HealthView
from apps.notifications.views import PushKeyView, PushSubscriptionView
from apps.punches.correction_views import CorrectionViewSet
from apps.punches.delegated import DelegatedPunchView
from apps.punches.overtime_views import OvertimeView
from apps.punches.views import PunchViewSet
from apps.reports.overview import OverviewView
from apps.reports.views import PayrollSummaryView, ReportView
from apps.shifts.views import ShiftPatternViewSet, ShiftViewSet, WorkingTimeRulesView
from apps.tenants.application_views import ApplicationViewSet
from apps.tenants.attendance_api import ApplicationAttendanceView
from apps.tenants.people_api import ApplicationPeopleView, ApplicationPersonView
from apps.tenants.views import CompanyView, PublicHolidayViewSet, RecordArrangementView
from apps.users.views import (
    DepartmentViewSet,
    MeView,
    PasswordResetRequestView,
    PasswordSetView,
    RefreshView,
    SignInView,
    SignOutView,
    SignUpView,
    UserViewSet,
    WorkplaceViewSet,
)

router = DefaultRouter()
router.register("employees", UserViewSet, basename="employee")
router.register("departments", DepartmentViewSet, basename="department")
router.register("punches", PunchViewSet, basename="punch")
router.register("corrections", CorrectionViewSet, basename="correction")
router.register("absences", AbsenceViewSet, basename="absence")
router.register("shift-patterns", ShiftPatternViewSet, basename="shift-pattern")
router.register("shifts", ShiftViewSet, basename="shift")
router.register("workplaces", WorkplaceViewSet, basename="workplace")
router.register("holidays", PublicHolidayViewSet, basename="holiday")
router.register("leave-types", LeaveTypeViewSet, basename="leave-type")
router.register("audit", AuditLogViewSet, basename="audit")
router.register("applications", ApplicationViewSet, basename="application")

auth_patterns = [
    path("register/", SignUpView.as_view(), name="register"),
    path("token/", SignInView.as_view(), name="token"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", SignOutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("set-password/", PasswordSetView.as_view(), name="set-password"),
]

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/auth/", include((auth_patterns, "auth"))),
    path("api/reports/working-time/", ReportView.as_view(), name="working-time-report"),
    path("api/reports/payroll-summary/", PayrollSummaryView.as_view(), name="payroll-summary"),
    path("api/overview/", OverviewView.as_view(), name="overview"),
    path("api/company/", CompanyView.as_view(), name="company"),
    # Art. 34.9, párrafo segundo: cómo se organizó el registro. Cuelga de
    # `company/` porque es de la empresa, no de una persona ni de un periodo.
    path(
        "api/company/record-arrangement/",
        RecordArrangementView.as_view(),
        name="record-arrangement",
    ),
    path("api/working-time-rules/", WorkingTimeRulesView.as_view(), name="working-time-rules"),
    path(
        "api/punches/delegated/",
        DelegatedPunchView.as_view(),
        name="punch-delegated",
    ),
    # Para aplicaciones que se integran, con credencial propia y su permiso.
    # Aparte del resto a propósito: quien llama aquí no es una persona, y la
    # forma de las respuestas la marca lo que un conector necesita, no lo que
    # una pantalla pinta.
    path("api/app/people/", ApplicationPeopleView.as_view(), name="app-people"),
    path(
        "api/app/people/<str:reference>/",
        ApplicationPersonView.as_view(),
        name="app-person",
    ),
    path("api/app/attendance/", ApplicationAttendanceView.as_view(), name="app-attendance"),
    path("api/overtime/", OvertimeView.as_view(), name="overtime"),
    path(
        "api/holiday-recoveries/",
        HolidayRecoveryView.as_view(),
        name="holiday-recoveries",
    ),
    path("api/push/key/", PushKeyView.as_view(), name="push-key"),
    path("api/push/subscriptions/", PushSubscriptionView.as_view(), name="push-subscriptions"),
    path("api/", include(router.urls)),
]

# El esquema y su visor. Configurable porque quien decide no somos nosotros:
# el producto es AGPL, así que el esquema no es un secreto --- está en el
# código --- pero es la instancia del cliente la que lo publica, y en un
# despliegue cerrado no hay razón para anunciar la superficie completa de la
# API a quien pase por delante.
#
# Por defecto se publica: es lo que hace utilizable una API, y quien
# autoaloja se beneficia de tenerlo a mano.
if settings.PUBLISH_API_SCHEMA:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    ]

if settings.DEBUG:
    urlpatterns += [path("admin/", admin.site.urls)]
