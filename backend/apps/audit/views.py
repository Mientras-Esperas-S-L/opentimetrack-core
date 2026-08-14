"""Reading the audit trail.

Read-only, and not because writes are inconvenient: ADR-0003 says the API
exposes no PUT, PATCH or DELETE for this table. A `ReadOnlyModelViewSet` makes
that structural rather than a rule somebody has to remember.

Who gets to read it is the interesting part, and there are two answers.
"""

from __future__ import annotations

import csv
import io
import json

from django.db.models import Q
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action

from apps.audit.models import AuditAction, AuditLog
from apps.audit.services import record
from apps.common.filters import LocalDayRangeFilter
from apps.common.permissions import IsAuthenticatedInTenant


class AuditLogFilter(LocalDayRangeFilter):
    """A range of days, because an inspection asks for a period and not for
    "the most recent fifty"."""

    day_field = "at"

    class Meta:
        model = AuditLog
        fields = ["action", "actor", "target_id"]


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
        ]
        read_only_fields = fields


@extend_schema(tags=["audit"])
# Both GETs came out as `audit_retrieve` and the generator resolved it by
# numbering them, so a client built from the schema got `audit_retrieve` and
# `audit_retrieve_2` with no way to tell which one returned the list.
@extend_schema_view(
    list=extend_schema(operation_id="audit_list", summary="List the trail"),
    retrieve=extend_schema(operation_id="audit_read", summary="Read one entry"),
)
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
    filterset_class = AuditLogFilter
    ordering = ["-at"]

    @extend_schema(
        summary="The trail as a CSV",
        description=(
            "The same entries the list returns, with the same filters, as a file. "
            "What gets handed over when somebody asks for the history of a period."
        ),
        responses={200: None},
    )
    @action(detail=False, methods=["get"])
    def export(self, request):
        """The trail as a file.

        Exporting it is itself a read of other people's activity, so it goes
        into the trail --- the alternative being a register whose most complete
        disclosure is the one thing it does not record.

        Deliberately not paginated: a page of fifty would be a truncated
        history handed over as if it were the whole thing, which is the failure
        this screen already had once.
        """
        rows = self.filter_queryset(self.get_queryset())

        buffer = io.StringIO()
        # `lineterminator` explícito: `csv.writer` pone «\r\n» por defecto ---lo que
        # dice la RFC 4180--- y eso llena el fichero de «^M» en cualquier editor de
        # Unix. Molesto a la vista, pero lo que de verdad importa es que el «\r» se
        # queda **pegado a la última columna** de cada línea: un `awk -F";"` o un
        # `split(";")` de andar por casa devuelve «05:00\r» donde esperaba «05:00»,
        # y eso no se ve hasta que alguien compara horas y no le cuadran.
        #
        # Excel y LibreOffice abren las dos formas igual de bien, así que no se
        # pierde nada. Reportado el 13/08/2026.
        writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
        # Sin columna de dirección: el rastro ya no guarda IP. Ver el comentario
        # del modelo --- chocaba con la inmutabilidad de la tabla, que hacía
        # imposible borrarla ni para atender una solicitud del art. 17.
        writer.writerow([_("When"), _("Who"), _("What"), _("About"), _("Detail"), _("Note")])
        for entry in rows.iterator(chunk_size=500):
            writer.writerow(
                [
                    entry.at.isoformat(),
                    entry.actor.get_full_name() if entry.actor else _("system"),
                    entry.get_action_display(),
                    entry.target_label,
                    json.dumps(entry.changes, ensure_ascii=False) if entry.changes else "",
                    entry.note,
                ]
            )

        record(
            action=AuditAction.REPORT_EXPORTED,
            actor=request.user,
            target_type="audit",
            target_label=str(_("Activity trail")),
            changes={
                "from": request.query_params.get("date_from", ""),
                "to": request.query_params.get("date_to", ""),
                "rows": rows.count(),
            },
        )

        response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="actividad.csv"'
        return response

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
