"""Authorising an external application, from the panel.

The models, the scopes, the authentication backend and the delegated punch
endpoint were all built and there was no way to reach any of it: creating an
application and issuing it a credential could only be done from a Django shell.
So a terminal at the gate, an NFC reader or a tablet on site --- the whole reason
delegated clocking exists --- needed somebody with database access to set up.

Two rules shape what follows.

**The token is shown once.** It is stored hashed, so it cannot be shown again;
losing it means issuing another. That is deliberate and the interface says so
rather than letting somebody discover it.

**Nothing is deleted.** An application that acted is part of the history of the
register: what it recorded is attributable to it, and removing it would leave
those clock events pointing at nobody. Revoking is what stops it.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsAdmin
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope


class CredentialSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = ApplicationCredential
        fields = [
            "id",
            "label",
            # The last characters, which is all there is. Enough to tell two
            # credentials apart in a list and useless to anybody who reads it.
            "token_hint",
            "expires_at",
            "revoked_at",
            "last_used_at",
            "is_valid",
            "created_at",
        ]
        read_only_fields = fields


class ApplicationSerializer(serializers.ModelSerializer):
    credentials = CredentialSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = Application
        fields = [
            "id",
            "name",
            "description",
            "scopes",
            "is_active",
            "created_by_name",
            "created_at",
            "credentials",
        ]
        read_only_fields = ["id", "created_by_name", "created_at", "credentials"]

    def validate_scopes(self, value):
        """Only scopes that exist, and at least one.

        An application with none can do nothing, which is not a state anybody
        means to create: it is a form somebody submitted before finishing.
        """
        allowed = set(ApplicationScope.values)
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise serializers.ValidationError(
                _("Unknown permissions: %(list)s.") % {"list": ", ".join(unknown)}
            )
        if not value:
            raise serializers.ValidationError(
                _("Grant at least one permission, or the application can do nothing.")
            )
        return value


class IssueSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


@extend_schema(tags=["organisation"])
@extend_schema_view(
    list=extend_schema(summary="Authorised applications"),
    create=extend_schema(summary="Authorise an application"),
)
class ApplicationViewSet(viewsets.ModelViewSet):
    """Applications a company has authorised. Administrators only.

    Authorising one hands out a way into the company's records, so it belongs
    with the other things only an administrator does --- not with the screens a
    manager can reach.
    """

    queryset = Application.objects.none()  # see the note in UserViewSet
    serializer_class = ApplicationSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]

    def get_queryset(self):
        # Lo vivo antes que lo revocado, y dentro de cada grupo lo más reciente
        # arriba. Por nombre ---que era el orden--- una aplicación recién
        # autorizada caía en cualquier sitio: con más de cincuenta, en la
        # segunda página, y quien acababa de autorizarla no la encontraba para
        # emitirle el testigo. Lo revocado baja porque ya no da acceso a nada,
        # pero se queda: los fichajes que registró siguen siendo suyos.
        return Application.objects.prefetch_related("credentials").order_by(
            "-is_active", "-created_at"
        )

    def perform_create(self, serializer):
        application = serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)
        record(
            action=AuditAction.APPLICATION_CREATED,
            actor=self.request.user,
            target=application,
            target_label=application.name,
            changes={"scopes": application.scopes},
        )

    def perform_update(self, serializer):
        before = list(serializer.instance.scopes)
        application = serializer.save()
        if application.scopes != before:
            # What an application may do is the only thing about it worth
            # recording separately: the rest is a name and a description.
            record(
                action=AuditAction.APPLICATION_CREATED,
                actor=self.request.user,
                target=application,
                target_label=application.name,
                changes={"scopes": [before, application.scopes]},
                note=str(_("Permissions changed")),
            )

    def perform_destroy(self, instance):
        """Deactivates rather than deletes, and revokes everything it had.

        What the application recorded stays attributable to it. Deleting the row
        would leave those clock events pointing at nobody, which is worse than
        keeping a name that no longer works.
        """
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        for credential in instance.credentials.filter(revoked_at__isnull=True):
            credential.revoke()

        record(
            action=AuditAction.APPLICATION_REVOKED,
            actor=self.request.user,
            target=instance,
            target_label=instance.name,
        )

    @extend_schema(request=IssueSerializer, responses={201: dict})
    @action(detail=True, methods=["post"])
    def credentials(self, request, pk=None):
        """Issues a token. Returned once, in clear, and never again.

        Several may coexist on purpose: that is what makes rotation possible
        without downtime --- issue the new one, swap it over, revoke the old.
        """
        application = self.get_object()
        if not application.is_active:
            raise BusinessRuleError(
                code="application_revoked",
                message=_("Reactivate the application before issuing a credential."),
            )

        form = IssueSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        credential, raw = ApplicationCredential.issue(
            application,
            label=form.validated_data["label"],
            expires_at=form.validated_data.get("expires_at"),
        )
        record(
            action=AuditAction.APPLICATION_CREATED,
            actor=request.user,
            target=application,
            target_label=application.name,
            note=str(_("Credential issued: …%(hint)s")) % {"hint": credential.token_hint},
        )

        return Response(
            {
                **CredentialSerializer(credential).data,
                # The only time it exists outside the client's own keeping.
                "token": raw,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={204: None},
        # `credential` is not a field of Application, so the generator cannot
        # infer its type from the model and defaults to a bare string.
        parameters=[
            OpenApiParameter(
                "credential",
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description="Credential to revoke.",
            )
        ],
    )
    @action(detail=True, methods=["post"], url_path="credentials/(?P<credential>[^/.]+)/revoke")
    def revoke_credential(self, request, pk=None, credential=None):
        """Stops one token without touching the others or the application."""
        application = self.get_object()
        found = application.credentials.filter(pk=credential, revoked_at__isnull=True).first()
        if found is None:
            raise BusinessRuleError(
                code="credential_not_found",
                message=_("That credential does not exist or is already revoked."),
            )

        found.revoke()
        record(
            action=AuditAction.APPLICATION_REVOKED,
            actor=request.user,
            target=application,
            target_label=application.name,
            note=str(_("Credential revoked: …%(hint)s")) % {"hint": found.token_hint},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"])
    def scopes(self, request):
        """The permissions that can be granted, with their wording.

        From the server so the interface cannot drift from what the API
        actually accepts --- a list copied into the frontend goes stale the first
        time somebody adds a scope.
        """
        return Response(
            [{"value": value, "label": str(label)} for value, label in ApplicationScope.choices]
        )
