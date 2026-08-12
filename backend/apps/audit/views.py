"""Reading the audit trail.

Read-only, and not because writes are inconvenient: ADR-0003 says the API
exposes no PUT, PATCH or DELETE for this table. A `ReadOnlyModelViewSet` makes
that structural rather than a rule somebody has to remember.

Who gets to read it is the interesting part, and there are two answers.
"""

from __future__ import annotations

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets

from apps.audit.models import AuditAction, AuditLog
from apps.common.permissions import IsAuthenticatedInTenant


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "at",
            "actor",
            "actor_label",
            "action",
            "action_display",
            "target_type",
            "target_id",
            "target_label",
            "changes",
            "note",
            "ip_address",
        ]
        read_only_fields = fields


@extend_schema(tags=["audit"])
class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The trail. Nobody writes to it through the API, by construction.

    **A worker sees the entries about themselves.** Not a courtesy: if the
    point of the trail is knowing who has been reading your record, the person
    whose record it is has to be able to look. Art. 34.9 ET already grants
    access to the record itself; who consulted it belongs to the same question.

    **An administrator sees the company's.** Including their own entries, which
    they cannot remove --- that is what the database trigger is for.

    A manager is deliberately *not* given the company-wide view. They are the
    ones the trail most often has something to say about, and letting the
    watched pick what the watching shows is how an audit trail stops meaning
    anything.
    """

    queryset = AuditLog.objects.none()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["action", "actor", "target_id"]
    ordering = ["-at"]

    def get_queryset(self):
        user = self.request.user
        # Explicitly scoped: this model is not a TenantOwnedModel, so nothing
        # filters by company on its behalf.
        qs = AuditLog.objects.filter(tenant=user.tenant).select_related("actor")

        if user.is_admin:
            return qs

        # Yours: what you did, and what was done to you.
        return qs.filter(Q(actor=user) | Q(target_id=user.id))

    @extend_schema(responses={200: dict})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


AUDIT_ACTIONS = AuditAction  # re-exported for the schema
