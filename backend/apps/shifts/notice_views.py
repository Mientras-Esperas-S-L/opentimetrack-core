"""Los avisos de cambio de turno: la persona los ve y dice que los ha visto; la
empresa ve cuándo se envió, cuándo llegó y cuándo se leyó cada uno.

Ver `apps.shifts.notices` para por qué existen.
"""

from __future__ import annotations

import io

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.csv_export import EscritorSeguro
from apps.common.descargas import nombre_seguro
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsAuthenticatedInTenant, IsManagerOrAdmin
from apps.common.scope import visible_people
from apps.punches.views import acting_application_name
from apps.shifts.models import ShiftNotice
from apps.shifts.notices import entregados, leido, lineas


class ShiftNoticeSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ShiftNotice
        fields = [
            "id",
            "employee",
            "employee_name",
            "changed_by",
            "changed_by_name",
            "created_at",
            "changes",
            "first_day",
            "notice_days",
            "short_notice",
            "emailed_at",
            "pushed_at",
            "delivered_at",
            "delivered_via",
            "read_at",
            "read_via",
        ]
        read_only_fields = fields

    def get_changed_by_name(self, aviso) -> str:
        return aviso.changed_by.get_full_name() if aviso.changed_by else ""


@extend_schema(tags=["shifts"])
class ShiftNoticeViewSet(viewsets.ReadOnlyModelViewSet):
    """Cada persona lee los suyos; quien gestiona, los de la gente que lleva.

    Leerlos la propia persona es lo que hace constar que **llegaron**: la lista
    que se le sirve, desde esta aplicación o desde otra con su sesión, es el
    aviso puesto en su pantalla. Que lo ha visto lo dice ella con `read`.
    """

    queryset = ShiftNotice.objects.none()
    serializer_class = ShiftNoticeSerializer
    permission_classes = [IsAuthenticatedInTenant]
    filterset_fields = ["employee"]

    def get_permissions(self):
        if self.action == "export":
            return [IsManagerOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = ShiftNotice.objects.select_related("employee", "changed_by")
        params = self.request.query_params
        if not user.can_read_records or params.get("mine") in ("1", "true"):
            qs = qs.filter(employee=user)
        else:
            scope = visible_people(user)
            if scope is not None:
                qs = qs.filter(employee__in=scope)
        if params.get("unread") in ("1", "true"):
            qs = qs.filter(read_at__isnull=True)
        return qs

    def _entregar(self, avisos):
        """Los propios que aún no constaban como llegados, llegan ahora."""
        propios = [
            a.pk for a in avisos if a.employee_id == self.request.user.id and a.delivered_at is None
        ]
        if not propios:
            return avisos
        via = acting_application_name(self.request)
        entregados(ShiftNotice.objects.filter(pk__in=propios), via)
        frescos = {
            a.pk: a
            for a in ShiftNotice.objects.select_related("employee", "changed_by").filter(
                pk__in=propios
            )
        }
        return [frescos.get(a.pk, a) for a in avisos]

    @extend_schema(
        parameters=[
            OpenApiParameter("mine", bool, description="Solo los de quien pregunta."),
            OpenApiParameter("unread", bool, description="Solo los que no se han leído."),
        ]
    )
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        filas = self._entregar(list(page if page is not None else qs))
        data = self.get_serializer(filas, many=True).data
        return self.get_paginated_response(data) if page is not None else Response(data)

    def retrieve(self, request, *args, **kwargs):
        aviso = self._entregar([self.get_object()])[0]
        return Response(self.get_serializer(aviso).data)

    @extend_schema(request=None, responses={200: ShiftNoticeSerializer})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """La persona dice que lo ha visto. Solo ella: nadie lo lee por otro."""
        aviso = self.get_object()
        if aviso.employee_id != request.user.id:
            raise BusinessRuleError(
                code="not_your_notice",
                message=_("Only the person it was sent to can say they have seen it."),
            )
        return Response(self.get_serializer(leido(aviso, acting_application_name(request))).data)

    @extend_schema(responses={(200, "text/csv"): str})
    @action(detail=False, methods=["get"])
    def export(self, request):
        """Todos, con sus horas: lo que se enseña si alguien pregunta si se avisó.

        Sin paginar, por lo mismo que el registro de actividad: una página de
        cincuenta entregada como si fuera todo es justo el fallo que no puede
        tener una prueba.
        """
        zona = request.user.tenant.tzinfo

        def hora(instante):
            if not instante:
                return ""
            return timezone.localtime(instante, zona).strftime("%d/%m/%Y %H:%M:%S")

        buffer = io.StringIO()
        writer = EscritorSeguro(buffer, delimiter=";", lineterminator="\n")
        writer.writerow(
            [
                _("Sent"),
                _("Person"),
                _("Changed by"),
                _("Changes"),
                _("Days of notice"),
                _("Under the minimum notice"),
                _("Email accepted"),
                _("Browser notification accepted"),
                _("Reached their app"),
                _("Through"),
                _("Read"),
                _("Through"),
            ]
        )
        for aviso in self.filter_queryset(self.get_queryset()).iterator(chunk_size=500):
            writer.writerow(
                [
                    hora(aviso.created_at),
                    aviso.employee.get_full_name() or aviso.employee.email,
                    aviso.changed_by.get_full_name() if aviso.changed_by else "",
                    " | ".join(lineas(aviso)),
                    aviso.notice_days,
                    _("yes") if aviso.short_notice else _("no"),
                    hora(aviso.emailed_at),
                    hora(aviso.pushed_at),
                    hora(aviso.delivered_at),
                    aviso.delivered_via,
                    hora(aviso.read_at),
                    aviso.read_via,
                ]
            )

        respuesta = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        nombre = nombre_seguro(
            f"avisos-de-turno_{timezone.localdate()}", respaldo="avisos-de-turno"
        )
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
        return respuesta
