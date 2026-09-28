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
    sign_in_url = serializers.CharField(
        help_text="Where this company's people sign in: the web app with their identity "
        "provider already chosen, when it has one that can sign people in."
    )


class WhoAmISerializer(serializers.Serializer):
    application = ApplicationIdentitySerializer()
    company = CompanyIdentitySerializer()


def sign_in_url(company) -> str:
    """The web app, with the company's provider chosen if it can sign people in.

    For the integration's «open OpenTimeTrack» link. Choosing the provider by the
    email domain, which is what the sign-in screen does, fails for anybody whose
    address is not on one of the provider's domains ---a person of another contractor
    working for this company--- and asking by person would tell anyone which
    addresses exist here. The integration already knows which company it is.
    """
    from urllib.parse import quote

    from django.conf import settings

    from apps.tenants.identity import SsoProvider

    web = (settings.SSO_WEB_URL or settings.FRONTEND_URL).rstrip("/")
    proveedor = next(
        (p for p in SsoProvider.objects_all_tenants.filter(tenant=company) if p.can_sign_people_in),
        None,
    )
    return f"{web}/?sso={quote(proveedor.slug)}" if proveedor else web


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
                    "sign_in_url": sign_in_url(company),
                },
            }
        )
