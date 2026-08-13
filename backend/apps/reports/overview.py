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

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.absences.models import Absence, AbsenceStatus
from apps.common.permissions import IsAuthenticatedInTenant
from apps.common.scope import visible_people
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

        # Every figure below counts people, so every one of them is scoped.
        # A headcount of the whole company next to a queue holding only your own
        # department is two numbers that do not belong on the same screen.
        scope = visible_people(request.user)
        mine = Q() if scope is None else Q(employee__in=scope)
        people = User.objects.filter(tenant=company) if scope is None else scope

        return Response(
            {
                "scope": "company" if scope is None else "departments",
                "date": today.isoformat(),
                "headcount": people.filter(is_active=True).count(),
                "working_now": self._working_now(company, start, end, scope),
                "off_today": self._off_today(today, scope),
                "awaiting_decision": self._awaiting_decision(company, mine),
                "week": self._week(company),
            }
        )

    def _awaiting_decision(self, company, mine) -> dict:
        """Lo que espera una decisión, y **todo** lo que espera una decisión.

        Contaba dos colas de las cinco que tiene «Por decidir»: las ausencias y
        las correcciones pendientes. Se dejaba fuera los cambios propuestos que
        la persona no ha contestado y las horas extra por saldar, que eran las
        dos grandes. Medido el 13/08/2026 en la base de demostración: la tarjeta
        decía **2** y había **57**.

        No es un número de adorno. Es lo que decide si alguien entra en «Por
        decidir», y las horas extra tienen plazo ---cuatro meses para compensar
        con descanso, art. 35.1--- así que una cola que nadie mira porque la
        portada dice que está vacía se convierte en un incumplimiento.

        `overtime` va aparte y sin número a propósito: calcularlo cuesta medio
        segundo con veinte personas ---hay que reconciliar cada día de cada
        una--- y esto se pide al abrir el panel y se refresca cada minuto. Se
        dice que hay cola sin decir cuánta, y la pantalla de decisiones, que ya
        lo calcula, pone la cifra. Mejor un «hay» honesto que un número caro o
        un cero falso.
        """
        from apps.absences.recovery import pending_recoveries

        return {
            "absences": Absence.objects.filter(mine, status=AbsenceStatus.PENDING).count(),
            "corrections": PunchCorrection.objects.filter(
                mine, status=CorrectionStatus.PENDING
            ).count(),
            # Propuestas de la empresa que la persona no ha contestado o ha
            # discutido: se pueden retirar o aplicar, y hasta entonces cuentan.
            "awaiting_employee": PunchCorrection.objects.filter(
                mine, status=CorrectionStatus.AWAITING_EMPLOYEE
            ).count(),
            "recoveries": len(pending_recoveries(company=company)),
            "overtime_pending": True,
        }

    def _working_now(self, company, start, end, scope) -> list[dict]:
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
        if scope is not None:
            today_punches = today_punches.filter(employee__in=scope)

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

    def _off_today(self, today, scope) -> list[dict]:
        approved = (
            Absence.objects.filter(
                status=AbsenceStatus.APPROVED,
                start_date__lte=today,
                end_date__gte=today,
            )
            .select_related("employee")
            .order_by("employee__last_name")
        )
        if scope is not None:
            approved = approved.filter(employee__in=scope)
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
