"""The company's own settings.

Everything here was already a field on the model and reachable only through the
Django admin, which is not somewhere a customer should be sent. Several of them
have legal weight --- the reference period, the retention windows --- so they
belong in the product with their reasons written next to them, not in a
superuser tool.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.permissions import IsAdmin, IsAuthenticatedInTenant
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
            "leave_year_start_month",
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


@extend_schema(tags=["organisation"])
class CompanyView(APIView):
    """Read for anyone in the company, write for an administrator."""

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "PATCH" else [IsAuthenticatedInTenant()]

    @extend_schema(responses={200: CompanySerializer})
    def get(self, request):
        return Response(CompanySerializer(request.user.tenant).data)

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
