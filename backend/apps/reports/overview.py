"""What the panel shows when somebody opens it.

One request instead of five. The admin panel's first screen answers four
questions --- who is working right now, who is off today, what is waiting for me
to decide, and how the week is going --- and asking for them separately would
mean four round trips before anything is on screen.

Deliberately not a "statistics" endpoint. Everything here is a fact of today,
cheap to compute, and derived from the same records the inspection report reads.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.absences.models import Absence, AbsenceStatus
from apps.common.permissions import IsAuthenticatedInTenant
from apps.punches.corrections import CorrectionStatus, PunchCorrection
from apps.punches.models import Punch, PunchType
from apps.punches.services import build_day_status, local_day_bounds
from apps.users.models import User


class OverviewView(APIView):
    """A snapshot of the company right now."""

    permission_classes = [IsAuthenticatedInTenant]

    @extend_schema(responses={200: dict})
    def get(self, request):
        company = request.user.tenant
        today = timezone.localdate()
        start, end = local_day_bounds(company)

        if not request.user.can_manage:
            # An employee gets their own day and nothing about anybody else.
            return Response(
                {
                    "scope": "self",
                    "day": build_day_status(request.user, company).as_dict(),
                    "pending_requests": self._own_pending(request.user),
                }
            )

        return Response(
            {
                "scope": "company",
                "date": today.isoformat(),
                "headcount": User.objects.filter(is_active=True).count(),
                "working_now": self._working_now(company, start, end),
                "off_today": self._off_today(today),
                "awaiting_decision": {
                    "absences": Absence.objects.filter(status=AbsenceStatus.PENDING).count(),
                    "corrections": PunchCorrection.objects.filter(
                        status=CorrectionStatus.PENDING
                    ).count(),
                },
                "week": self._week(company),
            }
        )

    def _working_now(self, company, start, end) -> list[dict]:
        """Whoever's last event today was a clock-in.

        Computed from the events rather than a status field on the person: a
        status field is a second source of truth that drifts, and this is the
        kind of thing that has to match the record exactly.
        """
        today_punches = (
            Punch.objects.filter(timestamp__gte=start, timestamp__lt=end, is_active=True)
            .select_related("employee")
            .order_by("employee_id", "timestamp")
        )

        last_by_person: dict = {}
        for punch in today_punches:
            last_by_person[punch.employee_id] = punch

        inside = [p for p in last_by_person.values() if p.punch_type == PunchType.IN]
        inside.sort(key=lambda p: p.timestamp)

        return [
            {
                "employee": str(p.employee_id),
                "name": p.employee.get_full_name(),
                "since": p.timestamp.astimezone(company.tzinfo).isoformat(),
                "source": p.source,
            }
            for p in inside
        ]

    def _off_today(self, today) -> list[dict]:
        approved = (
            Absence.objects.filter(
                status=AbsenceStatus.APPROVED,
                start_date__lte=today,
                end_date__gte=today,
            )
            .select_related("employee")
            .order_by("employee__last_name")
        )
        return [
            {
                "employee": str(a.employee_id),
                "name": a.employee.get_full_name(),
                "type": a.absence_type,
                "type_display": a.get_absence_type_display(),
                "until": a.end_date.isoformat(),
            }
            for a in approved
        ]

    def _week(self, company) -> dict:
        """Events per day for the last seven days, for the sparkline.

        Counts events, not hours: hours need pairing and closing open days, and
        this is a shape-of-the-week glance, not a payroll figure. Named so
        nobody mistakes it for one.
        """
        start, _ = local_day_bounds(company)
        first = start - timedelta(days=6)

        rows = (
            Punch.objects.filter(timestamp__gte=first, is_active=True)
            .annotate(day=Count("id"))
            .values("timestamp__date")
            .annotate(events=Count("id"))
            .order_by("timestamp__date")
        )
        by_day = {r["timestamp__date"]: r["events"] for r in rows}

        days = [(first + timedelta(days=i)).date() for i in range(7)]
        return {
            "days": [d.isoformat() for d in days],
            "events": [by_day.get(d, 0) for d in days],
        }

    def _own_pending(self, user) -> dict:
        return {
            "absences": Absence.objects.filter(employee=user, status=AbsenceStatus.PENDING).count(),
            "corrections": PunchCorrection.objects.filter(
                employee=user, status=CorrectionStatus.PENDING
            ).count(),
        }
