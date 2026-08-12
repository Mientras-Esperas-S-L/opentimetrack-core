"""Endpoints for leave.

Who sees what follows the same rule as clock events: a person is entitled to
their own history and not to a colleague's; managers and administrators see the
company.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import Absence, AbsenceStatus, AbsenceType, LeaveType
from apps.absences.services import (
    approve_absence,
    cancel_absence,
    leave_over_the_limit,
    reject_absence,
    request_absence,
    vacation_balance,
)
from apps.absences.uploads import validate_extension, validate_size
from apps.absences.usage import usage_summary
from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import (
    IsAdmin,
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.common.scope import person_in_scope, visible_people


class AbsenceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    type_display = serializers.CharField(source="get_absence_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    resolved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True, default=""
    )
    days = serializers.IntegerField(read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True, default=None)
    #: Served with the absence rather than looked up: a list of leave has to be
    #: able to say "art. 37.3.b" beside a row without a second request per row.
    basis = serializers.CharField(source="leave_type.basis", read_only=True, default="")
    hours = serializers.FloatField(read_only=True)
    #: Lo que queda del permiso, cuando lo pedido se pasa. Va con la solicitud
    #: porque quien decide lo necesita **al decidir**, y buscarlo aparte
    #: significa que nadie lo mira.
    over_the_limit = serializers.SerializerMethodField()

    def get_over_the_limit(self, obj) -> dict | None:
        if obj.status != AbsenceStatus.PENDING:
            return None
        return leave_over_the_limit(obj)

    # Whether there is one, not where it lives. The raw URL would be a bearer
    # secret sitting in every list response; the file comes from the
    # `justification` action, which checks who is asking.
    has_justification = serializers.SerializerMethodField()

    def get_has_justification(self, obj) -> bool:
        return bool(obj.justification)

    class Meta:
        model = Absence
        fields = [
            "id",
            "employee",
            "employee_name",
            "absence_type",
            "type_display",
            "leave_type",
            "leave_type_name",
            "basis",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "hours",
            "days",
            "over_the_limit",
            "reason",
            "status",
            "status_display",
            "approved_by",
            "resolved_by_name",
            "resolved_at",
            "has_justification",
            "created_at",
        ]
        read_only_fields = fields


class LeaveTypeSerializer(serializers.ModelSerializer):
    #: How much it grants, said the way a person reads it: "15 días naturales
    #: cada vez", "4 días laborables al año". Three fields that only mean
    #: something together, so the screen does not have to reassemble them and
    #: get the plural wrong.
    allowance = serializers.SerializerMethodField()
    measured_in_hours = serializers.BooleanField(read_only=True)

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "code",
            "name",
            "family",
            "basis",
            "amount",
            "unit",
            "period",
            "extra_when_travelling",
            "allowance",
            "measured_in_hours",
            "paid",
            "needs_justification",
            "note",
            "is_active",
        ]
        read_only_fields = ["id", "allowance", "measured_in_hours"]

    def get_allowance(self, obj) -> str:
        if obj.amount is None:
            return str(_("the time it takes"))
        amount = f"{obj.amount.normalize():f}".rstrip(".")
        return f"{amount} {obj.get_unit_display()} · {obj.get_period_display()}"


@extend_schema(tags=["absences"])
class LeaveTypeViewSet(viewsets.ModelViewSet):
    """The company's catalogue. Anyone reads; an administrator writes.

    Read for everybody because a person cannot ask for leave they cannot see,
    and because the entitlement and its article are exactly what they need to
    know before asking.
    """

    queryset = LeaveType.objects.none()
    serializer_class = LeaveTypeSerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["family", "is_active"]

    def get_queryset(self):
        return LeaveType.objects.all()

    def perform_create(self, serializer):
        # No code: a code is how the seed recognises one of its own, and a row
        # the company invented has no counterpart to recognise.
        serializer.save(tenant=self.request.user.tenant, code="")

    def perform_destroy(self, instance):
        used = instance.absences.count()
        if used:
            raise BusinessRuleError(
                code="leave_type_in_use",
                message=_(
                    "%(count)s absences use it. Deactivate it instead: deleting would "
                    "take the reason off records that have to survive four years."
                )
                % {"count": used},
            )
        instance.delete()

    @extend_schema(
        parameters=[OpenApiParameter("employee", str, description="UUID; defaults to the caller")],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def usage(self, request):
        """What is left of each leave that has a limit.

        The question the catalogue could not answer: it says art. 37.9 grants
        four days a year, and this says two of them are gone.
        """
        employee = request.user
        wanted = request.query_params.get("employee")
        if wanted and wanted != str(request.user.id):
            person = person_in_scope(request.user, wanted)
            if person is None:
                raise BusinessRuleError(
                    code="unknown_employee",
                    message=_("That person is not in this company."),
                )
            employee = person

        return Response(usage_summary(employee, request.user.tenant))

    @extend_schema(request=None, responses={200: dict})
    @action(detail=False, methods=["post"], permission_classes=[IsAdmin])
    def seed(self, request):
        """Brings in the country's catalogue. Adds what is missing, touches nothing."""
        result = seed_leave_types(request.user.tenant)
        return Response(result)


class AbsenceRequestSerializer(serializers.Serializer):
    absence_type = serializers.ChoiceField(choices=AbsenceType.choices, required=False)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    # The same two validators the model carries. Without them here the model's
    # `full_clean` still refuses --- but as a Django ValidationError, which DRF
    # does not translate, so a file that was too big came back as a 500 instead
    # of a message saying how big the limit is.
    justification = serializers.FileField(
        required=False,
        allow_null=True,
        validators=[validate_extension, validate_size],
    )
    # Managers may file leave on somebody's behalf; an employee may not.
    employee = serializers.UUIDField(required=False, allow_null=True)

    #: The specific kind. Optional so older clients keep working with just the
    #: family, which is all there was before the catalogue.
    leave_type = serializers.UUIDField(required=False, allow_null=True)
    #: Part of a day. Both or neither.
    start_time = serializers.TimeField(required=False, allow_null=True)
    end_time = serializers.TimeField(required=False, allow_null=True)

    def validate(self, attrs):
        if bool(attrs.get("start_time")) != bool(attrs.get("end_time")):
            raise serializers.ValidationError(
                {"end_time": _("Give both times, or neither: half of a range is not one.")}
            )
        return attrs


class AbsenceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    # Declared only so the schema generator can infer the model without running
    # get_queryset, which needs an authenticated caller. Same idiom as the other
    # viewsets; never used at runtime.
    queryset = Absence.objects.none()
    serializer_class = AbsenceSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["status", "absence_type", "employee"]
    ordering_fields = ["start_date", "created_at"]
    ordering = ["-start_date"]

    def get_queryset(self):
        qs = Absence.objects.select_related("employee", "approved_by")
        # Their own if they are not a manager; the departments they answer for
        # if they are. `visible_people` returns None for "no restriction", so an
        # administrator adds no join.
        scope = visible_people(self.request.user)
        if scope is not None:
            qs = qs.filter(employee__in=scope)
        return qs

    @extend_schema(request=AbsenceRequestSerializer, responses={201: AbsenceSerializer})
    def create(self, request):
        form = AbsenceRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        employee = request.user
        if data.get("employee") and data["employee"] != request.user.id:
            if not request.user.can_manage:
                raise BusinessRuleError(
                    code="not_your_request",
                    message=_("Leave can only be requested for yourself."),
                )
            employee = self._employee_in_company(data["employee"])

        kind = None
        if data.get("leave_type"):
            kind = LeaveType.objects.filter(pk=data["leave_type"], is_active=True).first()
            if kind is None:
                raise BusinessRuleError(
                    code="unknown_leave_type",
                    message=_("That leave type does not exist or is no longer in use."),
                )

        absence = request_absence(
            employee=employee,
            company=request.user.tenant,
            absence_type=data.get("absence_type") or "",
            leave_type=kind,
            start_date=data["start_date"],
            end_date=data["end_date"],
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            reason=data.get("reason", ""),
            justification=data.get("justification"),
        )
        return Response(AbsenceSerializer(absence).data, status=status.HTTP_201_CREATED)

    def _employee_in_company(self, employee_id):
        """Somebody the caller may read, or nothing.

        Two mistakes have lived on this line, and the second was found the same
        way as the first.

        It started as `User.objects.get(pk=...)`. People are not a
        `TenantOwnedModel` --- sign-in has to find them before the company is
        known --- so that manager spans every company, and an administrator
        could read the holiday balance of somebody in another one by passing
        their id. A `tenant=` filter fixed it.

        Then the scope stopped being the company. `tenant=` was no longer the
        answer, and the balance endpoint went on handing a manager the figures
        of anybody in the building while the list next to it showed them their
        own crew. The check that catches both is the same: ask the scope, not
        the company.
        """
        person = person_in_scope(self.request.user, employee_id)
        if person is None:
            # Indistinguishable from "does not exist", on purpose. Saying the
            # person is real but out of reach is saying who works here.
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("That person is not in this company."),
            )
        return person

    @extend_schema(request=None, responses={200: AbsenceSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        absence = approve_absence(self.get_object(), resolved_by=request.user)
        record(
            action=AuditAction.ABSENCE_APPROVED,
            actor=request.user,
            target=absence.employee,
            target_type="user",
            target_label=absence.employee.get_full_name(),
            changes={
                "type": absence.absence_type,
                "from": absence.start_date.isoformat(),
                "to": absence.end_date.isoformat(),
            },
            request=request,
        )
        return Response(AbsenceSerializer(absence).data)

    @extend_schema(request=None, responses={200: AbsenceSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def reject(self, request, pk=None):
        absence = reject_absence(self.get_object(), resolved_by=request.user)
        record(
            action=AuditAction.ABSENCE_REJECTED,
            actor=request.user,
            target=absence.employee,
            target_type="user",
            target_label=absence.employee.get_full_name(),
            changes={
                "type": absence.absence_type,
                "from": absence.start_date.isoformat(),
                "to": absence.end_date.isoformat(),
            },
            request=request,
        )
        return Response(AbsenceSerializer(absence).data)

    @extend_schema(responses={200: None, 302: None, 404: None})
    @action(detail=True, methods=["get"])
    def justification(self, request, pk=None):
        """The supporting document, for whoever is entitled to it.

        The only way to reach one. `MEDIA_URL` is never served, and the file
        URL is not in the serialiser: an absence reveals things --- who was off
        and for how long --- that a colleague has no business reading, and a
        path under /media/ that a web server happens to expose would hand the
        document to anybody who guessed it.

        `get_object` does the checking. It runs against `get_queryset`, which
        already narrows to the caller's own records unless they manage, so a
        worker asking for a colleague's gets a 404 rather than a 403 --- there
        is no reason to confirm the absence even exists.

        With object storage it redirects to a signed URL that expires in five
        minutes; with a filesystem it serves the bytes. Either way the
        permission check happened first, which is the part that matters.
        """
        absence = self.get_object()
        if not absence.justification:
            raise Http404

        # A supporting document is the most sensitive thing here. Somebody
        # else reading yours leaves a trace; reading your own does not.
        if absence.employee_id != request.user.id:
            record(
                action=AuditAction.DOCUMENT_DOWNLOADED,
                actor=request.user,
                target=absence.employee,
                target_type="user",
                target_label=absence.employee.get_full_name(),
                changes={"absence": str(absence.pk), "type": absence.absence_type},
                request=request,
            )

        if getattr(settings, "STORAGE_BACKEND", "filesystem") == "s3":
            return HttpResponseRedirect(absence.justification.url)

        return FileResponse(absence.justification.open("rb"), as_attachment=True)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        cancel_absence(self.get_object(), cancelled_by=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"])
    def balance(self, request):
        """Holiday left. Defaults to the caller; managers may ask for anybody."""
        employee = request.user
        wanted = request.query_params.get("employee")
        if wanted and wanted != str(request.user.id):
            if not request.user.can_manage:
                raise BusinessRuleError(
                    code="not_your_balance",
                    message=_("You can only see your own balance."),
                )
            employee = self._employee_in_company(wanted)

        balance = vacation_balance(employee, request.user.tenant)
        return Response({"employee": str(employee.id), **balance.as_dict()})

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
        ],
        responses={200: AbsenceSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def calendar(self, request):
        """Everything overlapping a window, for the team calendar.

        Overlap, not containment: leave running from June to July has to appear
        when looking at July, and a filter on `start_date` alone would drop it.
        That off-by-one is invisible until somebody books over a colleague's
        holiday because the calendar did not show it.

        A worker sees their own; a manager sees the company. Pending requests
        come too, drawn differently: deciding whether to approve August needs to
        show what else is already asked for.
        """
        try:
            first = date.fromisoformat(request.query_params["from"])
            last = date.fromisoformat(request.query_params["to"])
        except (KeyError, ValueError) as exc:
            raise BusinessRuleError(
                code="bad_window",
                message=_("Give 'from' and 'to' as YYYY-MM-DD."),
            ) from exc

        window = (
            self.get_queryset()
            .filter(start_date__lte=last, end_date__gte=first)
            .exclude(status=AbsenceStatus.REJECTED)
            .order_by("start_date")
        )
        return Response(AbsenceSerializer(window, many=True).data)

    @extend_schema(responses={200: AbsenceSerializer(many=True)})
    @action(detail=False, methods=["get"])
    def pending(self, request):
        """The approval queue. What a manager opens the panel to deal with."""
        if not request.user.can_manage:
            return Response([])
        queue = (
            Absence.objects.filter(status=AbsenceStatus.PENDING)
            .select_related("employee")
            .order_by("start_date")
        )
        # The queue is what a manager opens the panel to deal with, so it has to
        # hold what they can actually decide. Showing a request they cannot
        # resolve is offering work that fails on the second click.
        scope = visible_people(request.user)
        if scope is not None:
            queue = queue.filter(employee__in=scope)
        return Response(AbsenceSerializer(queue, many=True).data)
