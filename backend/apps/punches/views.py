"""Clock-in endpoints.

The heart of the product: one tap, and the server decides everything else.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_view_of_others
from apps.common.exceptions import BusinessRuleError
from apps.common.filters import LocalDayRangeFilter
from apps.common.network import client_ip
from apps.common.permissions import IsAuthenticatedInTenant
from apps.common.scope import person_in_scope, visible_people
from apps.punches import idempotency
from apps.punches.models import HoursNature, Punch, PunchSource
from apps.punches.serializers import PunchSerializer, PunchWriteSerializer
from apps.punches.services import build_day_status, register_punch


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
    # Una sesión obtenida con una aserción de aplicación lo dice en el propio token,
    # y eso manda sobre lo que declare el cuerpo: el origen es parte de la prueba, no
    # una preferencia del cliente. Ver apps/tenants/session_api.py.
    if acting_application_name(request):
        return PunchSource.APPLICATION

    declarado = (request.data or {}).get("source")
    declared = declarado.upper() if isinstance(declarado, str) else ""
    if declared in {PunchSource.MOBILE, PunchSource.WEB, PunchSource.TERMINAL}:
        return declared
    agent = request.META.get("HTTP_USER_AGENT", "").lower()
    return PunchSource.MOBILE if "expo" in agent or "okhttp" in agent else PunchSource.WEB


def _refuse_unless_justified(request, data) -> dict:
    """When the company expects punches from an application, this door asks why.

    It asks, it does not close. If the application is unavailable -- it is being
    deployed, the network is down, the phone is dead -- somebody would be working with
    no way to record their day, and the system that answers to an inspection is this
    one. A record whose availability depends on a third party is not a reliable record.

    So the answer is a reason, kept with the punch and visible in the report, rather
    than a refusal.
    """
    from apps.punches.serializers import EXCEPTION_REASON_MIN

    company = request.user.tenant
    if company.punch_entry != company.PunchEntry.APPLICATION:
        return {}
    # An application acting for the person is the expected door, not the exception.
    if acting_application_name(request):
        return {}

    reason = (data.get("exception_reason") or "").strip()
    if len(reason) < EXCEPTION_REASON_MIN:
        raise BusinessRuleError(
            code="exception_reason_required",
            message=_(
                "This company clocks in through its management application. You can still "
                "clock in here, but say why in a line."
            ),
            details={"field": "exception_reason", "min_length": EXCEPTION_REASON_MIN},
        )
    return {"exception": {"reason": reason}}


def acting_application_name(request) -> str:
    """The application acting for the person, when the session came from an assertion."""
    return _claim(request, "act_app")


def acting_application(request):
    """The application itself, or `None` when the person is acting for themselves.

    Needed rather than just its name for the idempotency receipt, which is scoped to
    the application: two connectors numbering their own operations must not collide.
    """
    from apps.tenants.models import Application

    identifier = _claim(request, "act_app_id")
    if not identifier:
        return None
    return Application.objects.filter(pk=identifier).first()


def _claim(request, name: str) -> str:
    token = getattr(request, "auth", None)
    try:
        return str(token[name]) if token is not None and name in token else ""
    except TypeError, KeyError:
        return ""


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
    # Por nombre, apellido y número de empleado: es lo que se teclea buscando
    # «los fichajes de Hugo». El filtro global ignoraba `?search=` aquí ---no
    # había campos declarados--- y devolvía la empresa entera con un 200.
    search_fields = ["employee__first_name", "employee__last_name", "employee__employee_id"]
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
            "the server infers whether it is an entry or an exit, and sets the timestamp "
            "unless the punch was made offline and says when (`declared_at`).\n\n"
            "**`Idempotency-Key` is accepted when an application holds the session.** "
            "That is the case with a queue at the other end --- a phone that recorded a "
            "punch with no signal and sends it when the signal returns. Repeating a call "
            "with the same key returns the event already recorded, with `200` instead of "
            "`201`. Without it a retry would not repeat the entry: it would record an "
            "**exit**, because the type is inferred from the current state."
        ),
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
                description=(
                    "Identifies the operation so a retry is not recorded twice. Only for a "
                    "session obtained by an application; up to 200 characters."
                ),
            )
        ],
        request=PunchWriteSerializer,
        responses={201: PunchSerializer, 200: PunchSerializer},
    )
    def create(self, request):
        serializer = PunchWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        excepcion = _refuse_unless_justified(request, data)

        # La clave es de la aplicación que sostiene la sesión, porque es la que tiene
        # la cola. Una persona fichando desde la web no tiene nada que reintentar, y
        # aceptarle una clave sería ofrecerle una garantía que no hay quien dé.
        application = acting_application(request)
        key = idempotency.key_from(request)
        if key and application is None:
            raise BusinessRuleError(
                code="idempotency_key_not_accepted",
                message=_(
                    "This key only means something for a session held by an application, "
                    "which is where a queue of unsent punches lives."
                ),
                details={"header": "Idempotency-Key"},
            )

        receipt = None
        if key:
            ya = idempotency.already_recorded(application, key)
            if ya is not None:
                return self._answer(ya, status.HTTP_200_OK)
            receipt, ya = idempotency.claim(request.user.tenant, application, key)
            if ya is not None:
                return self._answer(ya, status.HTTP_200_OK)

        punch = register_punch(
            employee=request.user,
            company=request.user.tenant,
            source=source_for(request),
            source_application=acting_application_name(request),
            interval=data.get("interval"),
            work_mode=data.get("work_mode", ""),
            hours_nature=data.get("hours_nature") or HoursNature.ORDINARY,
            overtime_settlement=data.get("overtime_settlement", ""),
            force_majeure=data.get("force_majeure", False),
            flexibility_measure=data.get("flexibility_measure", ""),
            ip_address=client_ip(request),
            device_id=data.get("device_id", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            trigger=data.get("trigger") or "MANUAL",
            evidence={**(data.get("evidence") or {}), **excepcion},
            declared_at=data.get("declared_at"),
        )

        if receipt is not None:
            idempotency.settle(receipt, punch)

        return self._answer(punch, status.HTTP_201_CREATED)

    @staticmethod
    def _answer(punch, code: int) -> Response:
        data = PunchSerializer(punch).data
        data["day_status"] = build_day_status(punch.employee, punch.tenant).as_dict()
        return Response(data, status=code)

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
