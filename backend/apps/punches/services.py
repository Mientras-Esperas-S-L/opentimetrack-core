"""Clock-in business rules.

Kept out of the views on purpose: the same rules have to hold whether the event
arrives from the web panel, the mobile app, an external application or a data
import. A rule living in a view is a rule that only applies to one door.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.punches.models import Punch, PunchSource, PunchType


@dataclass(frozen=True)
class DaySegment:
    """A stretch of work: an entry and, if it has happened, its exit."""

    start: datetime
    end: datetime | None

    @property
    def seconds(self) -> int:
        finish = self.end or timezone.now()
        return int((finish - self.start).total_seconds())

    @property
    def is_open(self) -> bool:
        return self.end is None


@dataclass(frozen=True)
class DayStatus:
    state: str  # WORKING | OFF | NOT_STARTED
    segments: list[DaySegment]
    worked_seconds: int

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "segments": [
                {
                    "in": s.start.isoformat(),
                    "out": s.end.isoformat() if s.end else None,
                    "seconds": s.seconds,
                }
                for s in self.segments
            ],
            "worked_seconds": self.worked_seconds,
        }


def local_day_bounds(company, moment: datetime | None = None) -> tuple[datetime, datetime]:
    """Start and end of the working day **in the company's zone**.

    Not a trivial detail: the boundary of a day is a local matter. Slicing by UTC
    would split the day wrongly for anyone east or west of Greenwich, and would
    already be wrong within Spain for a company in the Canary Islands.
    """
    moment = moment or timezone.now()
    local = moment.astimezone(company.tzinfo)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local, start_local + timedelta(days=1)


def punches_of_the_day(employee, company, day: date | None = None):
    reference = timezone.now()
    if day is not None:
        reference = datetime.combine(day, datetime.min.time(), tzinfo=company.tzinfo)

    start, end = local_day_bounds(company, reference)
    return Punch.objects.filter(
        employee=employee,
        is_active=True,
        timestamp__gte=start,
        timestamp__lt=end,
    ).order_by("timestamp")


def infer_type(employee, company) -> str:
    """Entry or exit, worked out from the last event of the day.

    The person is not asked which one it is: one tap, no choices, no chance of
    picking the wrong one.
    """
    last = punches_of_the_day(employee, company).last()
    if last is None or last.punch_type == PunchType.OUT:
        return PunchType.IN
    return PunchType.OUT


def build_day_status(employee, company, day: date | None = None) -> DayStatus:
    events = list(punches_of_the_day(employee, company, day))

    segments: list[DaySegment] = []
    open_start: datetime | None = None

    for event in events:
        if event.punch_type == PunchType.IN:
            # Two entries in a row should not happen, but if they do the first
            # one wins rather than being silently dropped.
            if open_start is None:
                open_start = event.timestamp
        elif open_start is not None:
            segments.append(DaySegment(start=open_start, end=event.timestamp))
            open_start = None

    if open_start is not None:
        segments.append(DaySegment(start=open_start, end=None))

    worked = sum(s.seconds for s in segments)

    if not events:
        state = "NOT_STARTED"
    elif segments and segments[-1].is_open:
        state = "WORKING"
    else:
        state = "OFF"

    return DayStatus(state=state, segments=segments, worked_seconds=worked)


@transaction.atomic
def register_punch(
    *,
    employee,
    company,
    source: str = PunchSource.WEB,
    source_application: str = "",
    recorded_by=None,
    ip_address: str | None = None,
    device_id: str = "",
    user_agent: str = "",
) -> Punch:
    """Record a clock event. The only supported way to create one.

    Everything that must be true of every event happens here: server timestamp,
    inferred type, business checks and integrity hash.
    """
    if not employee.is_active:
        raise BusinessRuleError(
            code="employee_inactive",
            message=_("This person is deactivated and cannot clock in or out."),
        )

    _check_no_approved_absence(employee, company)

    punch = Punch(
        tenant=company,
        employee=employee,
        punch_type=infer_type(employee, company),
        # Server time. Never from the client, ever.
        timestamp=timezone.now(),
        source=source,
        source_application=source_application,
        recorded_by=recorded_by,
        ip_address=ip_address,
        device_id=device_id,
        user_agent=user_agent,
    )
    punch.save()
    return punch


def _check_no_approved_absence(employee, company) -> None:
    """Approved leave blocks clocking in.

    Imported lazily because `punches` must not depend on `absences` at module
    level: the dependency graph in the component view only allows it the other
    way round.
    """
    from apps.absences.models import Absence, AbsenceStatus

    today = timezone.now().astimezone(company.tzinfo).date()

    absence = Absence.objects.filter(
        employee=employee,
        status=AbsenceStatus.APPROVED,
        start_date__lte=today,
        end_date__gte=today,
    ).first()

    if absence is not None:
        raise BusinessRuleError(
            code="punch_blocked_by_absence",
            message=_("You cannot clock in: you have approved leave for today."),
            details={"absence_id": str(absence.id), "date": today.isoformat()},
        )
