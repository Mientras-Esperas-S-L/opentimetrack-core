"""The company's own settings.

Everything here was already a field on the model and reachable only through the
Django admin, which is not somewhere a customer should be sent. Several of them
have legal weight --- the reference period, the retention windows --- so they
belong in the product with their reasons written next to them, not in a
superuser tool.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.permissions import IsAdmin, IsAuthenticatedInTenant, ReadForAllWriteForAdmin
from apps.common.scope import unassigned_managers
from apps.tenants.holidays import HolidayScope, PublicHoliday
from apps.tenants.models import Tenant, validate_time_zone


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "tax_id",
            "country",
            "time_zone",
            "language",
            "annual_leave_days",
            "leave_days_are_working_days",
            "leave_year_start_month",
            "managers_see_whole_company",
            "record_retention_years",
            "security_metadata_retention_days",
        ]
        # The tax number identifies the company in the record and in every
        # report already issued. Changing it is not a settings change.
        read_only_fields = ["id", "tax_id"]

    def validate_time_zone(self, value):
        validate_time_zone(value)
        return value

    def validate_record_retention_years(self, value):
        # Art. 34.9 ET is a floor, not a preference. Below it the company is not
        # keeping what the law says it must, and the product would be helping.
        if value < 4:
            raise serializers.ValidationError(
                "Art. 34.9 ET requires the record to be kept for four years. "
                "A longer period is allowed if there is a basis for it."
            )
        return value


class PublicHolidaySerializer(serializers.ModelSerializer):
    workplace_name = serializers.CharField(source="workplace.name", read_only=True, default=None)
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)

    class Meta:
        model = PublicHoliday
        fields = [
            "id",
            "day",
            "name",
            "scope",
            "scope_display",
            "workplace",
            "workplace_name",
            "note",
        ]
        read_only_fields = ["id", "scope_display", "workplace_name"]

    def validate_workplace(self, value):
        if value is not None and value.tenant_id != self.context["request"].user.tenant_id:
            raise serializers.ValidationError(_("That workplace belongs to another company."))
        return value


@extend_schema(tags=["organisation"])
class PublicHolidayViewSet(viewsets.ModelViewSet):
    """The calendar. Anyone reads; an administrator writes.

    Read for everybody because a person is entitled to know which days they are
    not expected to work --- and because their holiday balance depends on it.
    """

    queryset = PublicHoliday.objects.none()
    serializer_class = PublicHolidaySerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["scope", "workplace"]
    ordering = ["day"]

    def get_queryset(self):
        qs = PublicHoliday.objects.select_related("workplace")
        year = self.request.query_params.get("year")
        if year and year.isdigit():
            qs = qs.filter(day__year=int(year))
        return qs

    def perform_create(self, serializer):
        # Anything typed in here is the company's own. The two national and
        # regional scopes belong to the import, which replaces them wholesale;
        # letting the form claim one would put a row in the way of the next
        # import and then lose it without saying so.
        scope = (
            HolidayScope.LOCAL
            if serializer.validated_data.get("workplace")
            else HolidayScope.COMPANY
        )
        serializer.save(tenant=self.request.user.tenant, scope=scope)


@extend_schema(tags=["tenants"])
class CompanyView(APIView):
    """Read for anyone in the company, write for an administrator."""

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "PATCH" else [IsAuthenticatedInTenant()]

    @extend_schema(responses={200: dict})
    def get(self, request):
        # Alongside the settings, the one consequence of them that nobody would
        # otherwise see. Scoping managers by department only bites once somebody
        # is put in charge of one; until then every manager reads the whole
        # company, and a trade nobody can see is not a trade, it is a hole.
        loose = unassigned_managers(request.user.tenant)
        return Response(
            {
                **CompanySerializer(request.user.tenant).data,
                "managers_without_department": [
                    {"id": str(person.id), "name": person.get_full_name()} for person in loose
                ],
            }
        )

    @extend_schema(request=CompanySerializer, responses={200: CompanySerializer})
    def patch(self, request):
        company = request.user.tenant
        before = CompanySerializer(company).data
        serializer = CompanySerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Only what actually moved. A diff of everything would bury the one
        # field that changed --- and several of these decide how the record is
        # measured, so they are worth finding later.
        changed = {
            field: [before[field], value]
            for field, value in serializer.data.items()
            if before.get(field) != value
        }
        if changed:
            record(
                action=AuditAction.SETTINGS_CHANGED,
                actor=request.user,
                target=company,
                target_type="company",
                target_label=company.name,
                changes=changed,
                request=request,
            )
        return Response(serializer.data)
