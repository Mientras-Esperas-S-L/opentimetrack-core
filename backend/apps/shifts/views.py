"""Roster endpoints.

A worker reads their own shifts and nothing else. Managers read the company's
and draw them.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps import legal
from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.audit.trail import StructureTrail
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import (
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.common.scope import visible_people
from apps.shifts.models import Shift, ShiftPattern, validate_segments
from apps.shifts.services import (
    assign_pattern,
    clear_shifts,
    expected_vs_worked,
    paint_cells,
    review_roster,
    weekdays_in,
)
from apps.tenants.rules import ComputationRuleChange, WorkingTimeRules


class ShiftPatternSerializer(serializers.ModelSerializer):
    minutes = serializers.IntegerField(read_only=True)
    #: How many published days use it. Deleting one is SET_NULL, so nothing is
    #: lost, but the days it was painted on quietly stop naming a shift --- and
    #: the screen offering the delete had no way to say how many.
    shifts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ShiftPattern
        fields = ["id", "name", "segments", "colour", "is_active", "minutes", "shifts_count"]
        read_only_fields = ["id", "minutes", "shifts_count"]

    def validate_segments(self, value):
        validate_segments(value)
        return value


class ShiftSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    pattern_name = serializers.CharField(source="pattern.name", read_only=True, default="")
    colour = serializers.CharField(source="pattern.colour", read_only=True, default="#1b5e4a")
    minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Shift
        fields = [
            "id",
            "employee",
            "employee_name",
            "day",
            "pattern",
            "pattern_name",
            "colour",
            "segments",
            "minutes",
            "note",
        ]
        read_only_fields = ["id", "employee_name", "pattern_name", "colour", "minutes"]


def _weekdays_wanted(data: dict) -> list[int]:
    """Los días de la semana que pide la petición, distinguiendo dos cosas.

    **Omitir** el campo significa todos los días del rango: es el atajo cómodo
    para cubrir un periodo entero, y es lo que usa «Vaciar el mes».

    **Mandarlo vacío** significa ningún día, y eso es un error que hay que
    decir. Antes las dos cosas llegaban iguales ---el serializador ponía `[]`
    por defecto--- y quien desmarcaba todos los días en el cuadrante se
    encontraba turnos los siete, sábados y domingos incluidos. Justo lo
    contrario de lo que había pedido, y sin un aviso.
    """
    if "weekdays" in data and not data["weekdays"]:
        raise BusinessRuleError(
            code="no_weekdays",
            message=_("Pick at least one weekday, or leave the field out to mean every day."),
        )
    return data.get("weekdays") or list(range(7))


class ReassignSerializer(serializers.Serializer):
    """A quién pasa el turno. Un identificador y nada más."""

    employee = serializers.UUIDField()


class AssignSerializer(serializers.Serializer):
    employees = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    pattern = serializers.UUIDField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    # Monday = 0.
    #
    # **Omitido** significa todos los días del rango, que es el atajo cómodo
    # para un conector que quiere cubrir un periodo entero. **Vacío** no: una
    # lista vacía enviada a propósito significa ningún día, y hay que decirlo en
    # vez de adivinar.
    #
    # La diferencia importa porque el cuadrante manda `[]` cuando se desmarcan
    # todos los días. Con `default=list` las dos cosas llegaban iguales, y quien
    # había quitado hasta el último día se encontraba turnos los siete
    # ---sábados y domingos incluidos---, que es justo lo contrario de lo que
    # pidió. Salió en las pruebas del cuadrante: apareció un turno el sábado 5.
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6), required=False
    )


class PaintCellSerializer(serializers.Serializer):
    """One square of the grid, and what it becomes."""

    employee = serializers.UUIDField()
    day = serializers.DateField()
    #: A pattern, or bare spans, or neither --- in which case the day is rubbed
    #: out. Both together is a contradiction rather than a preference, so it is
    #: refused instead of one quietly winning.
    pattern = serializers.UUIDField(required=False, allow_null=True)
    segments = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        if attrs.get("pattern") and attrs.get("segments"):
            raise serializers.ValidationError(
                _("Give a shift or its hours, not both: they would disagree.")
            )
        if attrs.get("segments"):
            validate_segments(attrs["segments"])
        return attrs


class PaintSerializer(serializers.Serializer):
    """A stroke on the roster: some cells, each set to something of its own.

    Capped, and the cap is not a formality --- a whole workforce across a year
    would be six figures of rows behind one click. A month of a hundred people
    is three thousand, so the ceiling sits above any stroke a hand can draw and
    well below anything that would hold the database open.
    """

    cells = serializers.ListField(child=PaintCellSerializer(), allow_empty=False, max_length=4000)


class ClearSerializer(AssignSerializer):
    """Rubbing days out takes everything assigning does, minus the pattern.

    It was sharing `AssignSerializer`, which made the pattern required and then
    ignored it --- so a caller had to invent one, and a company with no patterns
    defined could not clear a roster at all. A required field nobody reads is a
    trap for whoever writes the next client.
    """

    pattern = serializers.UUIDField(required=False, allow_null=True)


@extend_schema(tags=["shifts"])
class ShiftPatternViewSet(StructureTrail, viewsets.ModelViewSet):
    """The shapes of a working day. Anyone reads; an administrator draws."""

    queryset = ShiftPattern.objects.none()
    serializer_class = ShiftPatternSerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["is_active"]
    # Los tramos son la forma del día: mover un turno de 08:00 a 07:00 cambia a
    # qué hora se espera a todo el que lo tenga puesto, y contra eso se comparan
    # los fichajes después.
    trail_fields = ("name", "segments", "is_active")

    def get_queryset(self):
        # El `order_by` explícito aunque el modelo declare `ordering = ["name"]`,
        # y esa es justo la trampa: `annotate` con un agregado mete un GROUP BY,
        # y Django **descarta la ordenación por defecto** en las consultas
        # agregadas. La anotación se añadió para poder decir cuántos días usan
        # un turno antes de borrarlo, y se llevó el orden por delante sin que
        # nada lo dijera salvo un aviso de DRF que solo se ve en las pruebas.
        #
        # Sin orden, PostgreSQL no promete nada entre páginas: la 2 puede
        # repetir filas de la 1 y saltarse otras. Con pocos turnos no se nota,
        # que es lo que lo hace difícil de encontrar.
        return ShiftPattern.objects.annotate(shifts_count=Count("shifts")).order_by("name")

    def perform_create(self, serializer):
        self.anotar(serializer.save(tenant=self.request.user.tenant), _("Added"))


@extend_schema(tags=["shifts"])
class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.none()
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["employee", "day"]

    def get_queryset(self):
        qs = Shift.objects.select_related("employee", "pattern")
        # Their own if they are not a manager; the departments they answer for
        # if they are. `visible_people` returns None for "no restriction", so an
        # administrator adds no join.
        scope = visible_people(self.request.user)
        if scope is not None:
            qs = qs.filter(employee__in=scope)
        return qs

    #: Everything that writes a roster. Kept as a constant next to the actions
    #: it names: adding one and forgetting to list it here hands the whole
    #: company's calendar to anybody with a login, and the omission looks like
    #: nothing on the screen.
    WRITES = {
        "create",
        "update",
        "partial_update",
        "destroy",
        "assign",
        "clear",
        "paint",
        "reassign",
    }

    #: Lecturas que tampoco son de cualquiera. `coverage` no escribe nada, pero
    #: de cada compañero dice cuántas horas lleva esa semana y si está de baja,
    #: y eso no es asunto de quien solo ficha. Aparte de `WRITES` porque el
    #: motivo es distinto ---ahí es quién puede decidir, aquí es quién puede
    #: mirar--- y juntarlas haría que la próxima lectura sensible se colara por
    #: no ser una escritura.
    MANAGER_READS = {"coverage"}

    def get_permissions(self):
        if self.action in self.WRITES or self.action in self.MANAGER_READS:
            return [IsManagerOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def _window(self, request):
        try:
            return (
                date.fromisoformat(request.query_params["from"]),
                date.fromisoformat(request.query_params["to"]),
            )
        except (KeyError, ValueError) as exc:
            raise BusinessRuleError(
                code="bad_window",
                message=_("Give 'from' and 'to' as YYYY-MM-DD."),
            ) from exc

    @extend_schema(
        # `filters=False` porque esta acción **no** es una lista del ViewSet: no
        # pagina, no ordena, no busca y no aplica sus filtros. El generador los
        # publicaba todos por herencia, así que el contrato prometía
        # `?employee=` y quien lo usara recibía la plantilla entera creyendo que
        # había filtrado. Silencioso y con la forma correcta: lo peor.
        filters=False,
        parameters=[
            OpenApiParameter("from", str, required=True, description="YYYY-MM-DD, inclusive."),
            OpenApiParameter("to", str, required=True, description="YYYY-MM-DD, inclusive."),
        ],
        responses={
            200: OpenApiResponse(
                # A mano, porque con `ShiftSerializer(many=True)` el generador
                # le pone el sobre paginado del ViewSet. Esta acción no pasa por
                # el paginador ---devuelve `Response(datos)` sin más--- así que
                # quien leyera el contrato escribía `respuesta.results.map(...)`
                # y recibía `undefined`.
                response={"type": "array", "items": {"$ref": "#/components/schemas/Shift"}},
            )
        },
    )
    @action(detail=False, methods=["get"])
    def roster(self, request):
        """The grid: every shift in a window."""
        first, last = self._window(request)
        rows = self.get_queryset().filter(day__gte=first, day__lte=last).order_by("day")
        return Response(ShiftSerializer(rows, many=True).data)

    @extend_schema(request=AssignSerializer, responses={201: dict})
    @action(detail=False, methods=["post"])
    def assign(self, request):
        """Paints a pattern over a range for several people at once."""
        form = AssignSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        if data["date_to"] < data["date_from"]:
            raise BusinessRuleError(
                code="ends_before_it_starts",
                message=_("The end date cannot precede the start date."),
            )

        pattern = ShiftPattern.objects.filter(pk=data["pattern"]).first()
        if pattern is None:
            raise BusinessRuleError(
                code="unknown_pattern", message=_("That shift pattern does not exist.")
            )

        days = weekdays_in(data["date_from"], data["date_to"], _weekdays_wanted(data))

        from apps.users.models import User

        people = User.objects.filter(tenant=request.user.tenant, pk__in=data["employees"])
        if people.count() != len(set(data["employees"])):
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("Somebody in that list is not in this company."),
            )

        created = 0
        for person in people:
            created += len(
                assign_pattern(
                    employee=person, company=request.user.tenant, pattern=pattern, days=days
                )
            )

        # Una entrada por operación, no una por turno: pintar un mes a veinte
        # personas son seiscientas filas, y seiscientas entradas idénticas no
        # son un rastro sino ruido que entierra el resto. Lo que hay que poder
        # responder después es quién repintó, cuándo y sobre qué tramo.
        record(
            action=AuditAction.SHIFTS_ASSIGNED,
            actor=request.user,
            target_type="shift",
            target_label=f"{data['date_from'].isoformat()} — {data['date_to'].isoformat()}",
            changes={
                "created": created,
                "people": len(people),
                "pattern": pattern.name,
                "from": data["date_from"].isoformat(),
                "to": data["date_to"].isoformat(),
            },
        )

        # Reviewed straight away: a roster that breaks a rest rule is worth
        # knowing about now, not the day somebody notices on the calendar.
        findings = review_roster(
            company=request.user.tenant, first=data["date_from"], last=data["date_to"]
        )
        return Response(
            {"created": created, "findings": [f.as_dict() for f in findings]}, status=201
        )

    @extend_schema(request=PaintSerializer, responses={200: dict})
    @action(detail=False, methods=["post"])
    def paint(self, request):
        """A stroke drawn straight onto the grid.

        Separate from `assign` because it answers a different question. Assign
        takes a pattern and a rectangle of the calendar, which is how a roster
        gets built. This takes a list of squares, each with its own answer,
        which is how one gets corrected --- and it is what lets undo put back a
        stroke that crossed four different shifts and two blanks.
        """
        form = PaintSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        cells = form.validated_data["cells"]

        result = paint_cells(company=request.user.tenant, cells=cells)

        days = [cell["day"] for cell in cells]
        findings = review_roster(company=request.user.tenant, first=min(days), last=max(days))
        return Response({**result, "findings": [f.as_dict() for f in findings]})

    @extend_schema(request=ClearSerializer, responses={200: dict})
    @action(detail=False, methods=["post"])
    def clear(self, request):
        form = ClearSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        days = weekdays_in(data["date_from"], data["date_to"], _weekdays_wanted(data))

        from apps.users.models import User

        removed = 0
        for person in User.objects.filter(tenant=request.user.tenant, pk__in=data["employees"]):
            removed += clear_shifts(employee=person, days=days)

        # De las tres del cuadrante esta es la que más falta hace que conste:
        # borra. Un mes que desaparece sin que nadie figure haciéndolo es
        # justamente el hueco que una inspección no puede reconstruir, porque el
        # cuadrante es contra lo que se comparan los fichajes.
        record(
            action=AuditAction.SHIFTS_CLEARED,
            actor=request.user,
            target_type="shift",
            target_label=f"{data['date_from'].isoformat()} — {data['date_to'].isoformat()}",
            changes={
                "removed": removed,
                "people": len(data["employees"]),
                "from": data["date_from"].isoformat(),
                "to": data["date_to"].isoformat(),
            },
        )
        return Response({"removed": removed})

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
        ],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def review(self, request):
        """What the roster departs from, and on what basis. Never a refusal."""
        first, last = self._window(request)
        employee = None if request.user.can_manage else request.user
        findings = review_roster(
            company=request.user.tenant, first=first, last=last, employee=employee
        )
        return Response({"findings": _grouped(findings)})

    @extend_schema(request=ReassignSerializer, responses={200: dict})
    @action(detail=True, methods=["post"])
    def reassign(self, request, pk=None):
        """Pasa un turno de una persona a otra.

        Una operación y no dos. La primera versión de la pantalla asignaba a la
        nueva y después limpiaba a la anterior, y ese orden tiene un fallo en
        medio que deja el turno duplicado ---o, al revés, borrado y sin nadie---.
        Mover conserva además el identificador del turno, así que lo que ya
        apuntara a él sigue apuntando a lo mismo.

        No comprueba si la persona nueva puede: eso lo dice `coverage`, y lo dice
        con matices ---puede pero se pasa de horas, puede pero se queda sin
        descanso--- que aquí solo se podrían convertir en un sí o un no. Cubrir
        una baja incumpliendo algo a sabiendas es una decisión legítima de quien
        organiza; lo que el producto tiene que hacer es enseñarle el precio y
        dejar constancia, no impedírselo.
        """
        from apps.users.models import User

        shift = self.get_object()

        # Por serializador y no filtrando con lo que venga: `pk=[]` levanta un
        # `ValidationError` de Django ---no de DRF--- que nadie captura, y la
        # respuesta era un 500. Lo cazó una sonda que mete tipos equivocados en
        # los campos reales, y el fallo era de este mismo endpoint recién
        # escrito: un `filter(pk=...)` acepta lo que le den hasta que la base de
        # datos se queja.
        forma = ReassignSerializer(data=request.data)
        forma.is_valid(raise_exception=True)

        # `tenant=` explícito: sin él esto aceptaba el UUID de una persona de
        # otra empresa y le enlazaba el turno, dejando además su nombre escrito
        # en el rastro append-only de la empresa equivocada. Sus dos vecinas
        # ---`assign` y `clear`--- sí lo llevaban; esta se escribió después y se
        # quedó sin él. El UUID que hace falta lo repartía `coverage`.
        destino = User.objects.filter(
            tenant=request.user.tenant,
            pk=forma.validated_data["employee"],
            is_active=True,
        ).first()
        if destino is None:
            raise BusinessRuleError(
                code="unknown_employee",
                message=_("That person is not on the staff list."),
            )

        if Shift.objects.filter(employee=destino, day=shift.day).exists():
            raise BusinessRuleError(
                code="already_rostered",
                message=_("They already have a shift that day."),
            )

        antes = shift.employee
        shift.employee = destino
        shift.save(update_fields=["employee"])

        record(
            action=AuditAction.SHIFT_REASSIGNED,
            actor=request.user,
            target=shift,
            target_label=f"{shift.day.isoformat()} {antes.get_full_name()}",
            changes={
                "employee": [str(antes.id), str(destino.id)],
                "from_label": antes.get_full_name() or antes.email,
                "to_label": destino.get_full_name() or destino.email,
            },
            note=str(_("Shift covered by somebody else.")),
        )

        return Response(ShiftSerializer(shift).data)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="coverage")
    def coverage(self, request):
        """Los turnos que se han quedado sin nadie, y quién puede cogerlos.

        Solo para quien gestiona: reasignar el turno de otra persona es una
        decisión de organización, y la lista de candidatos dice de cada
        compañero cuántas horas lleva y si está de baja.

        Los candidatos van dentro de cada hueco y no en una lista aparte porque
        dependen del turno: quién puede cubrir el martes de mañana no es quién
        puede cubrir el miércoles de noche, y servirlos juntos obligaría a la
        pantalla a recalcularlo mal.
        """
        from apps.shifts.coverage import uncovered, who_can_cover
        from apps.tenants.rules import WorkingTimeRules

        first, last = self._window(request)
        company = request.user.tenant
        rules = WorkingTimeRules.for_company(company)

        huecos = []
        for hueco in uncovered(company=company, first=first, last=last):
            candidatos = who_can_cover(shift=hueco.shift, company=company, rules=rules)
            huecos.append(
                {
                    **hueco.as_dict(),
                    # Los inviables se sirven igual, con su motivo: sin ellos,
                    # quien mira no sabe si la lista está corta porque no hay
                    # nadie o porque el filtro se pasó de listo.
                    "candidates": [c.as_dict() for c in candidatos],
                }
            )

        return Response({"uncovered": huecos})

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        """Expected against recorded, for the caller, today."""
        return Response(
            expected_vs_worked(
                employee=request.user,
                company=request.user.tenant,
                # Their today: date.today() is the container's UTC date, which
                # is yesterday for all of Spain between midnight and 01:00.
                day=local_today(request.user),
            )
        )


def _grouped(findings):
    """One row per person and kind, not one per day.

    A month of real data produced a hundred and fifty-six warnings, and a
    hundred and thirty of them were the same sentence about the same person on
    consecutive days: somebody whose shift pattern is nine hours continuous is
    owed a break every one of them.

    Each of those is true and the list of them is useless --- a wall nobody
    reads is the same as no warning at all, and it buries the three that were
    about something else. So they are folded: the count, the first day, and the
    days themselves for anybody who wants them.

    Folded here rather than in `review_roster` because the per-day findings are
    the accurate answer and the tests check them. This is presentation.
    """
    grouped: dict = {}
    for finding in findings:
        row = finding.as_dict()
        key = (row["employee"], row["code"])
        if key not in grouped:
            grouped[key] = {**row, "days": [], "count": 0}
        grouped[key]["days"].append(row["day"])
        grouped[key]["count"] += 1

    out = []
    for row in grouped.values():
        row["days"].sort()
        # The earliest, so the list still sorts by when the problem starts.
        row["day"] = row["days"][0]
        out.append(row)
    return sorted(out, key=lambda r: (r["day"], r["code"]))


def _describe(part, as_time: tuple[str, ...] = ()) -> dict | None:
    """A frozen dataclass from the legal layer, as JSON.

    Written once here rather than a serializer per dataclass: these carry no
    behaviour and no validation --- they are the country's numbers, read-only,
    and a country that has none returns null so the screen can leave the section
    out instead of rendering an empty one.
    """
    if part is None:
        return None
    body = {name: getattr(part, name) for name in part.__dataclass_fields__ if name != "citations"}
    for name in as_time:
        body[name] = body[name].isoformat(timespec="minutes")
    body["citations"] = {
        key: {"basis": c.basis, "note": c.note} for key, c in part.citations.items()
    }
    return body


def _outside_the_law(rules, framework, changed) -> list[dict]:
    """Los campos que se salen del límite que fija un artículo, con su cita.

    Solo los que acaban de cambiar: repetir en cada respuesta lo que la empresa
    ya sabe y decidió hace meses convierte el aviso en ruido, y un aviso que
    siempre está no lo lee nadie.

    Ni `fatal` ni nada parecido: esto informa. La validación de las fichas de
    convenio hace lo mismo con `fatal=False` y por el mismo motivo --- el
    RD 1561/1995 baja algunos de estos suelos para sectores concretos, así que
    un valor por debajo puede ser correcto y quien lo sabe es la empresa.
    """
    avisos = []

    # El plazo del art. 4.b, aparte: **el artículo no fija días**, y declarar un
    # suelo en el marco sería atribuirle un número que no dice. Lo que sí se
    # puede decir es qué pasa con el cero, y es que deja de haber procedimiento:
    # la empresa propone y aplica en el mismo segundo, sin dar ocasión de
    # responder ni de discrepar. Pedir el consentimiento y no esperarlo es no
    # pedirlo.
    if "correction_consent_days" in changed and not rules.correction_consent_days:
        cita = framework.citations.get("correction_consent_days")
        avisos.append(
            {
                "field": "correction_consent_days",
                "basis": cita.basis if cita else "",
                "message": str(
                    _(
                        "With no days to answer, a change can be applied the moment it is "
                        "proposed: nobody gets the chance to agree or to disagree."
                    )
                ),
            }
        )

    for campo in changed:
        cita = framework.citations.get(campo)
        if cita is None:
            continue
        valor = getattr(rules, campo, None)
        if valor is None:
            continue
        valor = float(valor)

        if cita.floor is not None and valor < float(cita.floor):
            avisos.append(
                {
                    "field": campo,
                    "basis": cita.basis,
                    "message": str(
                        _("%(value)s is below the %(floor)s that %(basis)s sets.")
                        % {"value": valor, "floor": cita.floor, "basis": cita.basis}
                    ),
                }
            )
        elif cita.ceiling is not None and valor > float(cita.ceiling):
            avisos.append(
                {
                    "field": campo,
                    "basis": cita.basis,
                    "message": str(
                        _("%(value)s is above the %(ceiling)s that %(basis)s sets.")
                        % {"value": valor, "ceiling": cita.ceiling, "basis": cita.basis}
                    ),
                }
            )
    return avisos


class RulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingTimeRules
        exclude = ["tenant", "created_at", "updated_at"]
        # `from_agreement` se lee y no se escribe: lo pone `apply_to_rules` al
        # aplicar una ficha, y es la procedencia de cada cifra. Dejarlo
        # escribible permitiría declarar que un número viene de un artículo que
        # nadie ha comprobado --- y además contestaba un 500 a cualquier basura,
        # que es lo que cazó `test_ningun_campo_de_la_api_contesta_un_500`.
        read_only_fields = ["id", "from_agreement"]


@extend_schema(tags=["organisation"])
class WorkingTimeRulesView(APIView):
    """The figures the roster is checked against.

    Read for anyone: a worker is entitled to know which rules their employer has
    configured, and a warning nobody can trace to a number is not a warning.
    """

    def get_permissions(self):
        from apps.common.permissions import IsAdmin

        return [IsAdmin()] if self.request.method == "PATCH" else [IsAuthenticatedInTenant()]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(self._body(WorkingTimeRules.for_company(request.user.tenant), request))

    @staticmethod
    def _body(rules, request):
        """The figures, and where each one comes from.

        The citations used to be written twice: in the model's `help_text`,
        which nothing read, and by hand into the settings screen, which is the
        copy people actually saw --- untranslatable, unable to vary by country,
        and free to drift from the backend.

        Serving them is what removes both problems at once. The screen renders
        what it is given, and a company in another country is given that
        country's articles.
        """
        framework = legal.for_company(request.user.tenant)
        data = RulesSerializer(rules).data
        citas = {
            key: {
                "basis": c.basis,
                "note": c.note,
                # El límite del artículo, cuando lo hay. Va aquí y no en la
                # pantalla porque es un dato del país: una copia en el
                # frontend acabaría enseñando la cifra española a una
                # empresa de fuera.
                "floor": c.floor,
                "ceiling": c.ceiling,
            }
            for key, c in framework.citations.items()
        }

        # Y si una ficha de convenio puso la cifra, **ese** es el artículo que
        # la fija. Antes ganaba siempre el del marco del país: el convenio de
        # jardinería fija el descanso entre jornadas por su art. 16 y la
        # pantalla lo atribuía al art. 34.3 ET.
        #
        # La cifra coincidía en ese caso y el problema no es la cifra: es la
        # procedencia. Cuando el convenio se renueve, nadie sabrá que ese valor
        # venía de él; y ante una inspección, la empresa tiene que poder decir
        # qué norma aplica y no una parecida.
        #
        # El suelo y el techo del país se quedan: son el límite que ningún
        # convenio puede bajar, y siguen sirviendo para avisar.
        for campo, origen in (rules.from_agreement or {}).items():
            previa = citas.get(campo, {})
            citas[campo] = {
                **previa,
                "basis": origen.get("basis") or previa.get("basis", ""),
                "note": origen.get("note") or previa.get("note", ""),
                "agreement": origen.get("agreement", ""),
                "framework_basis": previa.get("basis", ""),
            }

        return {
            **data,
            "country": framework.country,
            "framework": framework.name,
            "citations": citas,
            # Not settings and never will be: no agreement may lower them, so a
            # field to edit them would be a field whose only use is breaking the
            # law. Served so the screen can say what they are.
            "minors": {
                "max_daily_hours": framework.minors.max_daily_hours,
                "break_after_hours": framework.minors.break_after_hours,
                "break_minutes": framework.minors.break_minutes,
                "weekly_rest_hours": framework.minors.weekly_rest_hours,
                "night_work_forbidden": framework.minors.night_work_forbidden,
                "overtime_forbidden": framework.minors.overtime_forbidden,
                "citations": {
                    key: {"basis": c.basis, "note": c.note}
                    for key, c in framework.minors.citations.items()
                },
            },
            # Also not settings, and for a different reason: the night window is
            # one --- a company can move it --- but what the status *means* is
            # not. The figures are served so the screen can explain why somebody
            # on nights is checked differently, without writing the article into
            # the frontend again.
            "night": _describe(framework.night, ("window_starts_at", "window_ends_at")),
            "shifts": _describe(framework.shifts),
            # The subdivisions that set their own public holidays. Served here
            # so the workplace form offers the country's own list instead of
            # carrying a copy of Spain's --- which is the mistake the citations
            # made before this endpoint existed.
            "regions": framework.regions,
            # Igual que las regiones y por el mismo motivo: la pantalla del
            # centro no puede llevar escrito «Europe/Madrid», que es una cifra
            # española enseñada a quien no está en España.
            "time_zones": framework.time_zones,
        }

    #: Las dos que deciden **qué dice el registro**, no si cumple. Cambiarlas sin
    #: fecha reescribía periodos ya cerrados: medido, marcar que la pausa cuenta
    #: llevaba un abril terminado de 7:00 a 8:00 h, y bajar el tope pasaba un
    #: turno de noche bien fichado a «entrada sin salida» con cero horas.
    #:
    #: Las otras dieciséis no llevan fecha a propósito ---son valoración, no
    #: registro--- y deben recalcularse con lo vigente hoy.
    DEL_COMPUTO = ("break_counts_as_work", "max_open_hours")

    @extend_schema(request=RulesSerializer, responses={200: RulesSerializer})
    def patch(self, request):
        rules = WorkingTimeRules.for_company(request.user.tenant)
        before = RulesSerializer(rules).data

        # Antes de guardar nada: si se toca una de las dos, hay que decir desde
        # cuándo. La fecha la declara quien cambia la regla porque sale del
        # convenio, y el sistema no puede saberla --- poner «desde hoy» por su
        # cuenta sería tomar una decisión laboral que no le toca.
        serializer = RulesSerializer(rules, data=request.data, partial=True)
        # Se valida **antes** de pedir la fecha: si el valor no vale ---un tope de
        # cero--- lo que hay que decir es eso, no hacer que alguien declare una
        # fecha de efecto para un número que se va a rechazar igual.
        serializer.is_valid(raise_exception=True)

        del_computo = [
            campo
            for campo in self.DEL_COMPUTO
            if campo in request.data and request.data[campo] != before.get(campo)
        ]
        desde = request.data.get("effective_from")
        if del_computo and not desde:
            raise ValidationError(
                {
                    "effective_from": _(
                        "Changing how time is counted needs the day it starts to apply. "
                        "Without it the change would reach periods already closed and "
                        "reported."
                    )
                }
            )

        serializer.save()

        if del_computo:
            # **Anclar el pasado antes de escribir el cambio.** Sin esto el
            # arreglo no servía de nada: los días anteriores a la fecha
            # declarada no encuentran ninguna fila y caen a las reglas de hoy,
            # que son justamente las que se acaban de cambiar. Medido: declarando
            # que la pausa cuenta desde julio, un abril terminado se movía igual
            # de 7:00 a 8:00 h.
            #
            # Así que la primera vez se deja constancia de cómo se contaba hasta
            # ahora, y rige **desde siempre**: lo que había antes del primer
            # cambio declarado valía desde que existe el registro. Con la fecha
            # de alta de la empresa no bastaba ---si el alta es posterior a los
            # fichajes importados, o al periodo que se consulta, el ancla no los
            # cubre y vuelven a caer en las reglas de hoy.
            if not ComputationRuleChange.objects.filter(
                tenant=request.user.tenant, effective_from__lt=desde
            ).exists():
                ComputationRuleChange.objects.update_or_create(
                    tenant=request.user.tenant,
                    effective_from=date.min,
                    defaults={
                        "break_counts_as_work": before["break_counts_as_work"],
                        "max_open_hours": before["max_open_hours"],
                        "recorded_by": request.user,
                        "note": str(_("How time was counted until this change.")),
                    },
                )

            ComputationRuleChange.objects.update_or_create(
                tenant=request.user.tenant,
                effective_from=desde,
                defaults={
                    "break_counts_as_work": rules.break_counts_as_work,
                    "max_open_hours": rules.max_open_hours,
                    "recorded_by": request.user,
                    "note": str(request.data.get("effective_note", ""))[:300],
                },
            )

        # These decide what the roster is measured against, so a change to them
        # changes what "compliant" means. Only what moved is recorded.
        changed = {
            field: [before[field], value]
            for field, value in serializer.data.items()
            if before.get(field) != value
        }
        # Lo que queda fuera del suelo o del techo que fija un artículo. **Se
        # avisa y no se impide**, que es como funciona el resto de esta
        # pantalla: la decisión es de la empresa y el producto dice con qué se
        # compara. Lo que faltaba era decirlo **por la API**.
        #
        # El aviso solo existía en el frontend, que tiene las `citations` y las
        # pinta en amarillo. Quien entra por la API ---un conector, un script de
        # migración--- no recibía ninguna señal, y no es un valor raro y ya:
        # medido, poner `daily_rest_hours` a cero **apaga** el aviso de descanso
        # corto del cuadrante. Una salvaguarda del art. 34.3 se desactiva
        # escribiendo un número.
        #
        # La cifra del límite sale del marco del país y no de aquí, por lo mismo
        # que explica `Citation`: escribirla en el código sería enseñarle la
        # española a una empresa de fuera.
        fuera_de_la_ley = _outside_the_law(rules, legal.for_company(request.user.tenant), changed)
        if changed:
            record(
                action=AuditAction.RULES_CHANGED,
                actor=request.user,
                target=request.user.tenant,
                target_type="company",
                target_label=request.user.tenant.name,
                changes=changed,
                # En el rastro también: dentro de dos años, «12 → 0» no dice por
                # sí solo que ese cero esté por debajo de un mínimo legal, y
                # quien lo lea no tiene por qué saberse el artículo.
                note="; ".join(a["message"] for a in fuera_de_la_ley)[:300],
            )
        return Response({**self._body(rules, request), "warnings": fuera_de_la_ley})
