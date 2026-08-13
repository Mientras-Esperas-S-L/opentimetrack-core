"""Overtime, surfaced as an exception and ruled on by a manager.

The reconciliation already knows which days ran into overtime. This is the
other half: a manager looks at those days and records whether the overtime was
authorised, and how it settles --- paid, or given back in rest within four
months (art. 35.1). The punches never change; the decision is a classification
laid on top, which is how a company handles overtime without hiding it or
letting it inflate.

A decision covers one person and one day. It reopens when the figure moves: a
later correction can change how much overtime a day really held, and a ruling
about thirty minutes must not stand as authorising two hours.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.common.four_eyes import refuse_self_decision
from apps.punches.models import OvertimeDecision, OvertimeSettlement


def pending_overtime(*, company, first: date, last: date, scope=None) -> list[dict]:
    """Days with unresolved overtime, for the people in `scope`.

    A day counts when it was rostered, ran past the plan plus its margin, and
    either has no decision or has one for a different figure than it now holds.
    Days worked with no shift at all are a different question --- why did they
    work unplanned --- and not overtime to authorise, so they stay out.
    """
    from apps.shifts.models import Shift
    from apps.shifts.services import day_reconciliation

    shifts = Shift.objects.filter(day__gte=first, day__lte=last).select_related("employee")
    if scope is not None:
        shifts = shifts.filter(employee__in=scope)

    decided = {
        (d.employee_id, d.day): d
        for d in OvertimeDecision.objects.filter(day__gte=first, day__lte=last)
    }

    rows = []
    for shift in shifts.order_by("employee_id", "day"):
        recon = day_reconciliation(employee=shift.employee, company=company, day=shift.day)
        if recon.overtime_minutes <= 0:
            continue
        decision = decided.get((shift.employee_id, shift.day))
        if decision is not None and decision.minutes == recon.overtime_minutes:
            continue  # already ruled on, for this same figure
        rows.append(
            {
                "employee": str(shift.employee_id),
                "employee_name": shift.employee.get_full_name(),
                "day": shift.day.isoformat(),
                "minutes": recon.overtime_minutes,
                "worked_minutes": recon.worked_minutes,
                "expected_minutes": recon.expected_minutes,
                # A stale decision travels with the row so the screen can say
                # "you authorised 30, it is now 120" instead of looking new.
                "previous": decision.as_summary() if decision else None,
            }
        )
    return rows


def overtime_used(*, employee, company, day: date | None = None) -> dict:
    """Cuántas horas extra lleva esa persona en el año, contra el tope legal.

    El tope del art. 35.2 —ochenta al año salvo mejora del convenio— estaba en
    los ajustes desde el principio y **no lo leía nadie**: ni el cuadrante, ni la
    cola, ni el informe. Una empresa podía pasarse con este producto delante sin
    que nada la avisara, que es justo lo que la herramienta existe para evitar.

    Cuenta lo que la ley manda contar, que no es todo:

    - Solo lo **autorizado**. Un día pendiente de resolver todavía no es hora
      extra: puede acabar no autorizado.
    - **Las compensadas con descanso no computan** (art. 35.2). Es la razón de
      que la decisión guarde cómo se salda, y lo que permite contarlo bien aquí.
    - La **fuerza mayor** tampoco (art. 35.3), y por eso no entra en el
      cómputo del día quien la marcó en el fichaje.
    """
    from apps.tenants.rules import WorkingTimeRules

    day = day or timezone.localdate()
    # El tope es anual y va por año natural. El periodo de cómputo de las
    # vacaciones puede ser otro y no se mezcla con este.
    first, last = date(day.year, 1, 1), date(day.year, 12, 31)

    decisions = OvertimeDecision.objects.filter(
        employee=employee,
        day__gte=first,
        day__lte=last,
        status=OvertimeDecision.Status.AUTHORISED,
    ).exclude(settlement=OvertimeSettlement.REST)

    minutes = sum(d.minutes for d in decisions)
    cap = WorkingTimeRules.for_company(company).annual_overtime_hours
    return {
        "year": day.year,
        "minutes": minutes,
        "hours": round(minutes / 60, 1),
        "cap_hours": cap,
        "over_the_cap": cap > 0 and minutes > cap * 60,
    }


def decide_overtime(
    *,
    employee,
    company,
    day: date,
    decided_by,
    authorise: bool,
    settlement: str = "",
    note: str = "",
) -> OvertimeDecision:
    """Record a ruling on a day's overtime. Never touches the punches.

    Reads the overtime from the record at the moment of deciding, not from
    whatever the screen last showed: the figure that gets authorised is the one
    that is true when somebody says yes.
    """
    from apps.shifts.services import day_reconciliation

    recon = day_reconciliation(employee=employee, company=company, day=day)
    if recon.overtime_minutes <= 0:
        raise BusinessRuleError(
            code="no_overtime",
            message=_("That day has no overtime to rule on."),
        )

    if authorise and not settlement:
        # Art. 3.f: authorised overtime has to say how it settles. Authorising
        # without saying is authorising half the fact.
        raise BusinessRuleError(
            code="settlement_required",
            message=_("Say whether the overtime is paid or compensated with rest."),
        )

    alone = refuse_self_decision(
        subject=employee, decider=decided_by, company=company, what="overtime"
    )

    decision, _created = OvertimeDecision.objects.update_or_create(
        tenant=company,
        employee=employee,
        day=day,
        defaults={
            "minutes": recon.overtime_minutes,
            "status": (
                OvertimeDecision.Status.AUTHORISED
                if authorise
                else OvertimeDecision.Status.REJECTED
            ),
            "settlement": settlement if authorise else "",
            "note": note,
            "decided_by": decided_by,
            "decided_alone": alone,
        },
    )
    return decision


def overtime_window(day: date | None = None) -> tuple[date, date]:
    """The default window a manager reviews: the month up to today.

    Overtime is looked at after it happens --- you cannot authorise a day that
    has not been worked --- so the window ends today and reaches back a month.
    """
    day = day or timezone.localdate()
    return day - timedelta(days=31), day
