"""Reviewing and ruling on overtime, by a manager.

The exception queue for time: days that ran past the plan and have not been
ruled on. Read and decided only by somebody who manages the person --- the same
scope that governs who sees whose record --- and never on your own, so the
ruling passes through a second person like every other decision here.
"""

from __future__ import annotations

from datetime import date

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsManagerOrAdmin
from apps.common.scope import person_in_scope, visible_people
from apps.punches.models import OvertimeDecision, OvertimeSettlement
from apps.punches.overtime import (
    decide_overtime,
    overtime_used,
    overtime_window,
    pending_overtime,
)


class OvertimeDecisionSerializer(serializers.Serializer):
    """One ruling, over one day or over several of the same person's days.

    Somebody who works five minutes past every day fills a month's queue with
    the same decision, so the screen lets a manager rule on the lot. It is still
    one decision per day underneath --- each carries its own figure and its own
    audit entry --- because that is what a day of overtime is.
    """

    employee = serializers.UUIDField()
    day = serializers.DateField(required=False)
    days = serializers.ListField(
        child=serializers.DateField(), required=False, allow_empty=False, max_length=100
    )
    authorise = serializers.BooleanField()
    settlement = serializers.ChoiceField(
        choices=OvertimeSettlement.choices, required=False, allow_blank=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        days = list(data.get("days") or ([data["day"]] if data.get("day") else []))
        if not days:
            raise serializers.ValidationError({"day": "Give a day, or a list of days."})
        # Same day twice in one call would write the decision twice and audit it
        # twice for one fact.
        data["days"] = sorted(set(days))
        return data


@extend_schema(tags=["overtime"])
class OvertimeView(APIView):
    """Pending overtime for the caller's people, and the ruling on it."""

    permission_classes = [IsManagerOrAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
        ],
        responses={200: dict},
    )
    def get(self, request):
        first, last = self._window(request)
        scope = visible_people(request.user)
        rows = pending_overtime(company=request.user.tenant, first=first, last=last, scope=scope)

        # Lo que cada persona lleva consumido del tope anual, junto a lo que hay
        # que decidir. Autorizar sin saber que esa persona va por 78 de 80 es
        # decidir a ciegas sobre un tope legal --- y hasta hoy el ajuste existía
        # y no lo leía nadie.
        from apps.common.scope import people_queryset

        who = {row["employee"] for row in rows}
        people = {str(p.id): p for p in people_queryset(request.user).filter(id__in=who)}
        used = {
            key: overtime_used(employee=person, company=request.user.tenant)
            for key, person in people.items()
        }
        for row in rows:
            row["used_this_year"] = used.get(row["employee"])

        return Response({"pending": rows})

    @extend_schema(request=OvertimeDecisionSerializer, responses={200: dict})
    def post(self, request):
        form = OvertimeDecisionSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        person = person_in_scope(request.user, data["employee"])
        if person is None:
            raise BusinessRuleError(
                code="unknown_employee",
                message="That person is not in this company.",
            )

        decided, failed = [], []
        for day in data["days"]:
            try:
                decision = decide_overtime(
                    employee=person,
                    company=request.user.tenant,
                    day=day,
                    decided_by=request.user,
                    authorise=data["authorise"],
                    settlement=data.get("settlement", ""),
                    note=data.get("note", ""),
                )
            except BusinessRuleError as exc:
                # One day of a batch can have stopped being overtime since the
                # screen drew it. That is not a reason to lose the other twenty:
                # it comes back named, and the queue redraws without it.
                if len(data["days"]) == 1:
                    raise
                failed.append(
                    {"day": day.isoformat(), "code": exc.code, "message": str(exc.message)}
                )
                continue

            record(
                action=(
                    AuditAction.OVERTIME_AUTHORISED
                    if decision.status == OvertimeDecision.Status.AUTHORISED
                    else AuditAction.OVERTIME_REJECTED
                ),
                actor=request.user,
                target=person,
                target_type="user",
                target_label=person.get_full_name(),
                changes={
                    "day": decision.day.isoformat(),
                    "minutes": decision.minutes,
                    "settlement": decision.settlement,
                    "decided_alone": decision.decided_alone,
                },
            )
            decided.append(
                {
                    "day": decision.day.isoformat(),
                    "status": decision.status,
                    "minutes": decision.minutes,
                    "settlement": decision.settlement,
                    "decided_alone": decision.decided_alone,
                }
            )

        last = decided[-1] if decided else {}
        return Response(
            {
                # The shape a single ruling always had, so one caller reads one
                # answer; `decided`/`failed` is what a batch reads.
                "status": last.get("status", ""),
                "settlement": last.get("settlement", ""),
                "decided_alone": last.get("decided_alone", False),
                "decided": decided,
                "failed": failed,
            }
        )

    def _window(self, request):
        got_from = request.query_params.get("from")
        got_to = request.query_params.get("to")
        if got_from and got_to:
            try:
                return date.fromisoformat(got_from), date.fromisoformat(got_to)
            except ValueError as exc:
                raise BusinessRuleError(
                    code="bad_window", message="Give 'from' and 'to' as YYYY-MM-DD."
                ) from exc
        return overtime_window()
