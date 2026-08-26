"""Endpoints for record corrections."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsAuthenticatedInTenant, IsManagerOrAdmin
from apps.common.scope import visible_people
from apps.common.texto import validate_texto_legible
from apps.punches.corrections import (
    CorrectionKind,
    PunchCorrection,
    accept_correction,
    apply_without_agreement,
    approve_correction,
    dispute_correction,
    propose_correction,
    reject_correction,
    request_correction,
)
from apps.punches.models import Punch, PunchType
from apps.punches.serializers import PunchSerializer


class CorrectionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    #: El huso de la persona a la que afecta. `target_detail` y `result_detail`
    #: lo traen por su cuenta ---son fichajes---, pero `proposed_timestamp` va
    #: suelto y sin esto se pintaba en el de la empresa: para una delegación en
    #: otro huso, la hora que se propone poner se leía con una hora de más.
    time_zone = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    result_detail = PunchSerializer(source="result", read_only=True)
    # **El fichaje que se va a tocar.** Faltaba, y con él faltaba lo único que
    # hace que el consentimiento del art. 4.b signifique algo: si la propuesta
    # es anular un fichaje, `proposed_timestamp` va vacío por diseño, así que la
    # persona veía «Anular un fichaje · Pedida el 12/08» y dos botones. Se le
    # pedía autorizar un cambio sin decirle cuál. En un cambio de hora tampoco
    # veía la que se sustituye, solo la nueva.
    #
    # La pantalla de quien propone sí lo enseñaba. La de quien tiene que
    # consentir, no, que es justo al revés de como debería estar.
    target_detail = PunchSerializer(source="target", read_only=True)

    class Meta:
        model = PunchCorrection
        fields = [
            "id",
            "employee",
            "employee_name",
            "time_zone",
            "kind",
            "kind_display",
            "target",
            "target_detail",
            "proposed_type",
            "proposed_timestamp",
            "reason",
            "status",
            "status_display",
            "requested_by",
            "resolved_by",
            "resolved_at",
            "resolution_note",
            "result",
            "result_detail",
            # Art. 4.b. Whether both parties agreed, and if not, what the person
            # said. Never one without the other.
            "employee_agreed",
            "employee_responded_at",
            "employee_dissent",
            "applied_without_agreement",
            "representatives_notified_at",
            "representatives_notice",
            "created_at",
        ]
        read_only_fields = fields

    def get_time_zone(self, obj) -> str:
        return str(obj.employee.tzinfo)


class CorrectionRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=CorrectionKind.choices)
    # Only a manager may name somebody else; anyone else corrects their own.
    employee = serializers.UUIDField(required=False, allow_null=True)
    target = serializers.UUIDField(required=False, allow_null=True)
    # Choices, not free text: an unknown value used to reach the record and be
    # understood by no reader. The service checks it too --- this is here so a
    # client gets a field error instead of a generic refusal.
    proposed_type = serializers.ChoiceField(
        choices=PunchType.choices, required=False, allow_blank=True
    )
    proposed_timestamp = serializers.DateTimeField(required=False, allow_null=True)

    # Mandatory, and not merely required by the form: a correction with no
    # stated reason is indistinguishable from tampering.
    #
    # El validador se declara aquí además de en el modelo porque el servicio
    # crea con `objects.create()`, que no pasa por `full_clean()`. La regla vive
    # en `apps.common.texto`; lo que se repite es la declaración, no la lógica.
    reason = serializers.CharField(
        min_length=5, max_length=500, validators=[validate_texto_legible]
    )


class DissentSerializer(serializers.Serializer):
    # Mandatory: a disagreement with no content is not something a reader can
    # weigh against the change it sits beside.
    account = serializers.CharField(min_length=5, max_length=1000)


class ResolutionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


@extend_schema(tags=["corrections"])
class CorrectionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Requests to put the record right.

    A worker may raise one about their own record and see how it ends. Managers
    and administrators see the whole company's and decide.
    """

    queryset = PunchCorrection.objects.none()
    serializer_class = CorrectionSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["status", "kind", "employee"]

    def get_queryset(self):
        # Los saltos hasta el huso de cada persona, por el suyo y por el de los
        # dos fichajes que cuelgan: sin ellos se pregunta una vez por fila.
        qs = PunchCorrection.objects.select_related(
            "employee",
            "employee__workplace",
            "employee__tenant",
            "target",
            "target__employee",
            "target__employee__workplace",
            "target__employee__tenant",
            "result",
            "result__employee",
            "result__employee__workplace",
            "result__employee__tenant",
        ).all()
        # Their own if they are not a manager; the departments they answer for
        # if they are. `visible_people` returns None for "no restriction", so an
        # administrator adds no join.
        scope = visible_people(self.request.user)
        if scope is not None:
            qs = qs.filter(employee__in=scope)
        return qs

    @extend_schema(
        summary="Request a correction",
        description=(
            "Records what the person says actually happened. Changes nothing until "
            "somebody approves it. The reason is mandatory."
        ),
        request=CorrectionRequestSerializer,
        responses={201: CorrectionSerializer},
    )
    def create(self, request):
        form = CorrectionRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        target = None
        if data.get("target"):
            target = Punch.objects.filter(pk=data["target"]).first()
            if target is None:
                raise BusinessRuleError(
                    code="event_not_found",
                    message=_("That event does not exist."),
                )

        employee = self._subject(request, data.get("employee"))

        # Art. 4.b decides which path this takes. Asking about your own record
        # and having the company approve it means both have authorised. The
        # company proposing about somebody else is missing one authorisation,
        # so it waits for them instead of applying.
        maker = propose_correction if employee.id != request.user.id else request_correction
        correction = maker(
            employee=employee,
            company=request.user.tenant,
            **(
                {"proposed_by": request.user}
                if employee.id != request.user.id
                else {"requested_by": request.user}
            ),
            kind=data["kind"],
            reason=data["reason"],
            target=target,
            proposed_type=data.get("proposed_type", ""),
            proposed_timestamp=data.get("proposed_timestamp"),
        )
        record(
            action=AuditAction.CORRECTION_REQUESTED,
            actor=request.user,
            target=employee,
            target_type="user",
            target_label=employee.get_full_name(),
            changes={"kind": correction.kind},
            note=correction.reason[:300],
        )
        return Response(CorrectionSerializer(correction).data, status=status.HTTP_201_CREATED)

    def _subject(self, request, employee_id):
        """Whose record the correction is about.

        ADR-0014: a manager may correct without a prior request, but through the
        same procedure and with the same mandatory reason. Nobody touches a time
        without leaving why --- and the request records both the person it
        concerns and the person who filed it, which are not the same field.
        """
        if not employee_id or str(employee_id) == str(request.user.id):
            return request.user

        if not request.user.can_manage:
            raise BusinessRuleError(
                code="not_your_record",
                message=_("You can only ask for corrections to your own record."),
            )

        from apps.users.models import User

        # Scoped to the company: an id from elsewhere is simply not found.
        employee = User.objects.filter(tenant=request.user.tenant, pk=employee_id).first()
        if employee is None:
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("That person is not in this company."),
            )
        return employee

    @extend_schema(request=None, responses={200: CorrectionSerializer})
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """The person agrees with a change their employer proposed (art. 4.b)."""
        correction = self.get_object()
        accept_correction(correction, employee=request.user)
        correction.refresh_from_db()
        # Recorded here and not only in `approve`: this path applies the change
        # without ever touching that endpoint, and a correction that lands with
        # no trail is the gap the audit log exists to close.
        record(
            action=AuditAction.CORRECTION_APPROVED,
            actor=request.user,
            target=correction.employee,
            target_type="user",
            target_label=correction.employee.get_full_name(),
            changes={"correction": str(correction.pk), "agreed": True},
            note=correction.reason[:300],
        )
        return Response(CorrectionSerializer(correction).data)

    @extend_schema(request=DissentSerializer, responses={200: CorrectionSerializer})
    @action(detail=True, methods=["post"])
    def dispute(self, request, pk=None):
        """The person disagrees, and says what they think happened.

        Nothing is applied. Their account is stored, the representatives are
        informed, and the company decides whether to go ahead.
        """
        form = DissentSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        correction = dispute_correction(
            self.get_object(), employee=request.user, account=form.validated_data["account"]
        )
        record(
            action=AuditAction.CORRECTION_DISPUTED,
            actor=request.user,
            target=correction.employee,
            target_type="user",
            target_label=correction.employee.get_full_name(),
            changes={"correction": str(correction.pk)},
            note=correction.employee_dissent[:300],
        )
        return Response(CorrectionSerializer(correction).data)

    @extend_schema(request=None, responses={200: CorrectionSerializer})
    @action(
        detail=True,
        methods=["post"],
        url_path="apply-anyway",
        permission_classes=[IsManagerOrAdmin],
    )
    def apply_anyway(self, request, pk=None):
        """The company applies a change the person did not agree to.

        Art. 4.b allows it and requires the disagreement to be recorded beside
        it. Both travel to the inspection report.
        """
        correction = self.get_object()
        apply_without_agreement(correction, resolved_by=request.user)
        correction.refresh_from_db()
        record(
            action=AuditAction.CORRECTION_IMPOSED,
            actor=request.user,
            target=correction.employee,
            target_type="user",
            target_label=correction.employee.get_full_name(),
            changes={"correction": str(correction.pk)},
            note=correction.employee_dissent[:300],
        )
        return Response(CorrectionSerializer(correction).data)

    @extend_schema(
        summary="Approve a correction",
        description="Applies it. The previous version stays readable and points to the new one.",
        request=ResolutionSerializer,
        responses={200: CorrectionSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        correction = self.get_object()
        form = ResolutionSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        approve_correction(
            correction, resolved_by=request.user, note=form.validated_data.get("note", "")
        )
        correction.refresh_from_db()
        record(
            action=AuditAction.CORRECTION_APPROVED,
            actor=request.user,
            target=correction.employee,
            target_type="user",
            target_label=correction.employee.get_full_name(),
            changes={"kind": correction.kind, "correction": str(correction.pk)},
            note=correction.reason[:300],
        )
        return Response(CorrectionSerializer(correction).data)

    @extend_schema(
        summary="Reject a correction",
        description="Turns it down. The request stays: a refused claim is history too.",
        request=ResolutionSerializer,
        responses={200: CorrectionSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def reject(self, request, pk=None):
        correction = self.get_object()
        form = ResolutionSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        reject_correction(
            correction, resolved_by=request.user, note=form.validated_data.get("note", "")
        )
        correction.refresh_from_db()
        record(
            action=AuditAction.CORRECTION_REJECTED,
            actor=request.user,
            target=correction.employee,
            target_type="user",
            target_label=correction.employee.get_full_name(),
            changes={"correction": str(correction.pk)},
            note=form.validated_data.get("note", "")[:300],
        )
        return Response(CorrectionSerializer(correction).data)
