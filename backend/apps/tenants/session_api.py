"""A session for one of the application's people, from a signed assertion.

The door that lets a managing application clock somebody in **as themselves**:
it presents its own credential (so the company knows which application is acting)
together with an assertion signed by an identity provider that company trusts (so
it is not the application's word that the person is who it says).

Both are required on purpose. The credential alone would let any application with
`punch:self` impersonate anybody; the assertion alone would not say which
application is acting, and that is what the record has to show.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasApplicationScope
from apps.tenants.applications import ApplicationScope
from apps.tenants.assertions import person_from_assertion


class AssertionSerializer(serializers.Serializer):
    grant_type = serializers.CharField(
        help_text="`urn:ietf:params:oauth:grant-type:jwt-bearer`, as in RFC 7523.",
    )
    assertion = serializers.CharField(help_text="The JWT the identity provider signed.")

    def validate_grant_type(self, value):
        if value != "urn:ietf:params:oauth:grant-type:jwt-bearer":
            raise serializers.ValidationError("Only urn:ietf:params:oauth:grant-type:jwt-bearer.")
        return value


class IssuedSessionSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="The person's JWT. Goes in `Authorization: Bearer`.")
    refresh = serializers.CharField()
    employee = serializers.UUIDField()
    employee_id = serializers.CharField()
    name = serializers.CharField()


@extend_schema(tags=["applications"])
class ApplicationSessionView(APIView):
    """Exchanges an assertion for a session of the person it names."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.PUNCH_SELF

    @extend_schema(
        summary="A session for one of your people",
        description=(
            "Exchanges a JWT signed by a trusted identity provider for a session of the person "
            "it names, resolved by their external reference. The assertion must carry `iss`, "
            "`aud`, `exp`, `iat` and `jti`, live at most a minute and be used once. Anything "
            "clocked with the session is recorded as `APPLICATION` with this application's "
            "name. Requires `punch:self` and a provider allowed to act for its people."
        ),
        request=AssertionSerializer,
        responses={201: IssuedSessionSerializer},
    )
    def post(self, request):
        from apps.audit.models import AuditAction
        from apps.audit.services import record
        from apps.users.serializers import issue_tokens

        form = AssertionSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        application = request.user.application
        company = application.tenant
        person, provider = person_from_assertion(form.validated_data["assertion"], company)

        tokens = issue_tokens(person, acting_application=application)
        # An application obtaining a session for somebody is exactly the kind of thing
        # that has to be answerable afterwards: who acted, for whom, and on whose word.
        record(
            action=AuditAction.APPLICATION_ACTED_AS,
            actor=None,
            actor_label=f"aplicación · {application.name}",
            company=company,
            target=person,
            target_type="user",
            target_label=person.get_full_name() or person.email,
            changes={"issuer": provider.issuer},
        )
        return Response(
            {
                **tokens,
                "employee": str(person.id),
                "employee_id": person.employee_id,
                "name": person.get_full_name(),
            },
            status=status.HTTP_201_CREATED,
        )
