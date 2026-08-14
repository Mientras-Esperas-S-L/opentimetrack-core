"""Confirmar los días de vacaciones que una baja se comió (art. 38.3 ET).

La detección es automática, la decisión no. Devolver días al saldo sin que
nadie lo mire es de las cosas que después nadie sabe explicar delante de una
inspección; pero el derecho es del trabajador y no puede depender de que
alguien se acuerde, así que lo detectado aparece en la cola desde el primer
momento y la persona lo ve en su pantalla aunque todavía no esté confirmado.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.absences.models import RecoveredHoliday
from apps.absences.recovery import confirm_recovery, pending_recoveries
from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsManagerOrAdmin
from apps.common.scope import person_in_scope, visible_people


class RecoverySerializer(serializers.Serializer):
    recovery = serializers.UUIDField()
    accept = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, default="")


@extend_schema(tags=["absences"])
class HolidayRecoveryView(APIView):
    """Lo detectado y sin confirmar, y la confirmación."""

    permission_classes = [IsManagerOrAdmin]

    @extend_schema(responses={200: dict})
    def get(self, request):
        rows = pending_recoveries(company=request.user.tenant, scope=visible_people(request.user))
        return Response({"pending": rows})

    @extend_schema(request=RecoverySerializer, responses={200: dict})
    def post(self, request):
        form = RecoverySerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        recovery = RecoveredHoliday.objects.filter(pk=data["recovery"]).first()
        if recovery is None or person_in_scope(request.user, recovery.employee_id) is None:
            # Indistinguible de «no existe», como en todo lo demás: decir que
            # existe pero no es tuyo ya es decir que existe.
            raise BusinessRuleError(
                code="unknown_recovery", message="That recovery is not in this company."
            )

        confirm_recovery(
            recovery=recovery,
            company=request.user.tenant,
            decided_by=request.user,
            accept=data["accept"],
            note=data.get("note", ""),
        )
        record(
            action=(
                AuditAction.HOLIDAY_RECOVERY_CONFIRMED
                if data["accept"]
                else AuditAction.HOLIDAY_RECOVERY_DISMISSED
            ),
            actor=request.user,
            target=recovery.employee,
            target_type="user",
            target_label=recovery.employee.get_full_name(),
            changes={
                "days": recovery.days,
                "from": recovery.first_day.isoformat(),
                "to": recovery.last_day.isoformat(),
                "regime": recovery.regime,
            },
        )
        return Response({"status": recovery.status, "days": recovery.days})
