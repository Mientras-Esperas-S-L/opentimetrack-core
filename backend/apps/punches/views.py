"""Clock-in endpoints.

The heart of the product: one tap, and the server decides everything else.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_view_of_others
from apps.common.filters import LocalDayRangeFilter
from apps.common.permissions import IsAuthenticatedInTenant
from apps.punches.models import HoursNature, Punch, PunchInterval, PunchSource
from apps.punches.serializers import PunchSerializer, PunchWriteSerializer
from apps.punches.services import build_day_status, register_punch


def client_ip(request) -> str | None:
    """Real address, honouring a reverse proxy when there is one."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class PunchFilter(LocalDayRangeFilter):
    day_field = "timestamp"

    class Meta:
        model = Punch
        fields = ["employee", "punch_type", "source", "is_active"]


def source_for(request) -> str:
    """Whether it came from the mobile app or the web panel."""
    declared = (request.data or {}).get("source", "").upper()
    if declared in {PunchSource.MOBILE, PunchSource.WEB, PunchSource.TERMINAL}:
        return declared
    agent = request.META.get("HTTP_USER_AGENT", "").lower()
    return PunchSource.MOBILE if "expo" in agent or "okhttp" in agent else PunchSource.WEB


@extend_schema(tags=["punches"])
@extend_schema_view(
    list=extend_schema(summary="List clock events"),
    retrieve=extend_schema(summary="Read one clock event"),
)
class PunchViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Punch.objects.none()  # see the note in UserViewSet
    serializer_class = PunchSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_class = PunchFilter
    ordering_fields = ["timestamp"]

    def list(self, request, *args, **kwargs):
        """Leaves a trace when the list is somebody else's.

        This was the gap the audit trail existed to close and did not: a
        manager could read any worker's history and nothing recorded it. Only
        a filtered request is logged --- asking for one named person --- because
        that is the one that answers "who has been looking at me".

        The company-wide list is not logged. It is the ordinary act of running
        a payroll, it happens dozens of times a day, and an entry per page view
        would bury the pointed ones.
        """
        wanted = request.query_params.get("employee")
        if wanted and wanted != str(request.user.id):
            from apps.users.models import User

            person = User.objects.filter(tenant=request.user.tenant, pk=wanted).first()
            record_view_of_others(
                request=request, target_employee=person, note="listado de fichajes"
            )
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = Punch.objects.select_related("employee").all()

        # A worker sees their own history, which the law grants them, and only
        # their own. Managers and administrators see the whole company.
        if not self.request.user.can_manage:
            qs = qs.filter(employee=self.request.user)

        # `date_from` and `date_to` used to be applied here with
        # `timestamp__date__gte`, which under USE_TZ converts using the
        # **TIME_ZONE setting** --- UTC --- and not the company's zone. For Madrid
        # that moved the boundary two hours: every punch between midnight and
        # 02:00 counted towards the day before, so a night shift's start landed
        # on the wrong date and a range asking for a month lost its first hours.
        # PunchFilter does it in the company's own zone.
        return qs

    # ------------------------------------------------------------------ clocking

    @extend_schema(
        summary="Clock in or out",
        description=(
            "Records a clock event. The client sends neither the time nor the type: "
            "the server sets the timestamp and infers whether it is an entry or an exit."
        ),
        request=PunchWriteSerializer,
        responses={201: PunchSerializer},
    )
    def create(self, request):
        serializer = PunchWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        punch = register_punch(
            employee=request.user,
            company=request.user.tenant,
            source=source_for(request),
            interval=data.get("interval") or PunchInterval.WORK,
            work_mode=data.get("work_mode", ""),
            hours_nature=data.get("hours_nature") or HoursNature.ORDINARY,
            overtime_settlement=data.get("overtime_settlement", ""),
            force_majeure=data.get("force_majeure", False),
            flexibility_measure=data.get("flexibility_measure", ""),
            ip_address=client_ip(request),
            device_id=data.get("device_id", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )

        data = PunchSerializer(punch).data
        data["day_status"] = build_day_status(request.user, request.user.tenant).as_dict()
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Today's status",
        description="Segments worked today, accumulated time and current state.",
        responses={200: None},
    )
    @action(detail=False, methods=["get"])
    def today(self, request):
        estado = build_day_status(request.user, request.user.tenant)
        return Response(
            {
                "employee": str(request.user.id),
                "time_zone": request.user.tenant.time_zone,
                **estado.as_dict(),
            }
        )

    # ---------------------------------------------------------------- correction

    # `void` used to live here, and it is gone on purpose.
    #
    # It let an administrator strike a clock event with **no reason and no
    # notice**, while a correction with exactly the same effect (`kind=VOID`)
    # requires both. Two doors to the same act, one of them without the
    # guarantees, empties ADR-0014: "nobody touches a time without leaving why"
    # is not a rule if there is a second way in.
    #
    # To void an event: POST /api/corrections/ with kind=VOID. Reason mandatory,
    # author recorded, the person told, and the original left readable.
