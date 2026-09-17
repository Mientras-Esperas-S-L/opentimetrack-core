"""Who am I, for an application.

A connector holding a credential could not tell which company it pointed at nor
which permissions it carried: it had to call a scoped endpoint and read the 401 or
403 to guess. This is the one door open to every valid application credential, and
it answers exactly that.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsApplication


class ApplicationIdentitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    scopes = serializers.ListField(child=serializers.CharField())


class CompanyIdentitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    time_zone = serializers.CharField()


class WhoAmISerializer(serializers.Serializer):
    application = ApplicationIdentitySerializer()
    company = CompanyIdentitySerializer()


@extend_schema(tags=["applications"])
class ApplicationMeView(APIView):
    permission_classes = [IsApplication]

    @extend_schema(
        summary="Who am I",
        description="The application behind the credential, its permissions and its company.",
        responses={200: WhoAmISerializer},
    )
    def get(self, request):
        application = request.user.application
        company = application.tenant
        return Response(
            {
                "application": {
                    "id": str(application.id),
                    "name": application.name,
                    "scopes": list(application.scopes or []),
                },
                "company": {
                    "id": str(company.id),
                    "name": company.name,
                    "time_zone": company.time_zone,
                },
            }
        )
