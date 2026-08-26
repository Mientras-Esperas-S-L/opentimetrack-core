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
from apps.common.scope import person_in_scope, visible_people
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
    """Whether it came from the mobile app or the web panel.

    Lee el cuerpo a pelo, **antes** de que el serializador valide nada, porque
    decide con qué origen se guarda el fichaje. Eso significa que aquí puede
    llegar cualquier cosa: `{"source": 12}` hacía `12.upper()` y devolvía un 500
    ---encontrado con una sonda que mete tipos equivocados en los campos reales
    de cada serializador---.

    Solo una cadena puede declarar un origen. Lo demás no es un error que haya
    que contar: esta función ya tiene una respuesta para «no me han dicho nada
    utilizable», que es mirar el agente del navegador, y un número es
    exactamente eso.
    """
    declarado = (request.data or {}).get("source")
    declared = declarado.upper() if isinstance(declarado, str) else ""
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
            # **Solo si de verdad puede verla.** Antes bastaba con nombrar un
            # identificador: se anotaba «Fulano consultó la ficha de Mengano»
            # aunque el ámbito devolviera cero filas y Fulano no hubiera visto
            # nada. Dos daños, y el segundo es el grave:
            #
            # - Mengano abría su pantalla de Actividad y leía que un compañero
            #   había consultado su registro. Falso, y de los que acaban en una
            #   conversación desagradable entre dos personas.
            # - Un registro de accesos que apunta accesos que no ocurrieron deja
            #   de servir como prueba de los que sí. Es justo lo contrario de
            #   para lo que existe.
            person = person_in_scope(request.user, wanted)
            record_view_of_others(
                request=request, target_employee=person, note="listado de fichajes"
            )
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        # `employee__workplace` y `employee__tenant` porque cada fichaje dice
        # en qué huso se vivió, y ese sale del centro de la persona o ---si no
        # tiene--- de la empresa. Sin los dos saltos se pregunta una vez por
        # fila: son cincuenta por página.
        qs = Punch.objects.select_related(
            "employee", "employee__workplace", "employee__tenant"
        ).all()

        # A worker sees their own history, which the law grants them, and only
        # their own. A manager sees the departments they answer for.
        # Their own if they are not a manager; the departments they answer for
        # if they are. `visible_people` returns None for "no restriction", so an
        # administrator adds no join.
        scope = visible_people(self.request.user)
        if scope is not None:
            qs = qs.filter(employee__in=scope)

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
            trigger=data.get("trigger") or "MANUAL",
            evidence=data.get("evidence") or {},
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
                # La de la persona, no la de la empresa. Esta zona es la del
                # reloj de pared que la pantalla de fichar enseña, y la que
                # decide qué día es «hoy»: para una delegación en Las Palmas
                # dentro de una empresa de Madrid iba sesenta minutos
                # adelantada, así que quien fichaba a las 23:30 veía las 00:30
                # y su jornada empezaba, en pantalla, al día siguiente.
                "time_zone": str(request.user.tzinfo),
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
