"""Nudging somebody to make a punch they forgot, without ever making it for them.

The whole design in one line: a reminder prompts the *real* act, it never
records anything. So it cannot hide a late arrival, invent an ordinary day, or
bury overtime --- the three ways an assisted system turns into the "fichaje de
horario" the law exists to stop. The most it can do is make a forgotten punch
get made, by the person, at the real time.

Two nudges, both keyed off the reconciliation between roster and record:

- **Missing entry.** A shift started, its entry margin has passed, and nothing
  is clocked. "Remember to clock in."
- **Open day.** The shift's end has passed, its exit margin with it, and the day
  is still open. "Remember to clock out when you finish." Deliberately worded to
  prompt the real exit --- which captures overtime --- rather than to suggest
  auto-closing at the planned time, which would erase it.

Ran every few minutes by cron or celery-beat. `PunchReminder` is what stops it
sending the same nudge on every tick until the person finally clocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from apps.punches.models import PunchReminder
from apps.shifts.services import day_reconciliation


@dataclass(frozen=True)
class DueReminder:
    employee: object
    day: date
    kind: str  # PunchReminder.Kind


def reminders_due(company, now=None) -> list[DueReminder]:
    """Who, in this company, should be nudged right now, and about what.

    Reads the person's own clock: their today and their now, in their
    workplace's zone, so a shift in the Canary delegation is judged an hour
    behind Madrid. Excludes anyone who opted out, anyone already reminded of
    that thing on that day, and every case where the punch is not overdue yet.
    """
    from apps.shifts.models import Shift
    from apps.tenants.rules import WorkingTimeRules
    from apps.users.models import User

    now = now or timezone.now()
    rules = WorkingTimeRules.for_company(company)
    entry_tol = timedelta(minutes=rules.entry_tolerance_minutes)
    exit_tol = timedelta(minutes=rules.exit_tolerance_minutes)

    people = User.objects.filter(tenant=company, is_active=True, wants_punch_reminders=True)

    due: list[DueReminder] = []
    for person in people:
        local_now = now.astimezone(person.tzinfo)
        today = local_now.date()

        # Yesterday too: a day opened last night and never closed is the
        # commonest "forgot to clock out", and at 00:30 the shift's end is on the
        # previous date. Looking only at `today` would miss it every night.
        for day in (today, today - timedelta(days=1)):
            shift = Shift.objects.filter(employee=person, day=day).first()
            if shift is None:
                continue

            recon = day_reconciliation(employee=person, company=company, day=day)
            planned_start = shift.starts_at.replace(tzinfo=person.tzinfo)
            planned_end = shift.ends_at.replace(tzinfo=person.tzinfo)

            # Missing entry: only for today, and only inside the shift. Nagging
            # about a shift that already ended helps nobody --- that is a
            # no-show for a manager to see, not a reminder for the worker.
            if (
                day == today
                and recon.status == "MISSING"
                and planned_start + entry_tol <= local_now <= planned_end
                and not _already_sent(person, day, PunchReminder.Kind.CLOCK_IN)
            ):
                due.append(DueReminder(person, day, PunchReminder.Kind.CLOCK_IN))

            # Open day: the shift's end has passed and they are still clocked in.
            if (
                recon.status == "OPEN"
                and local_now >= planned_end + exit_tol
                and not _already_sent(person, day, PunchReminder.Kind.CLOCK_OUT)
            ):
                due.append(DueReminder(person, day, PunchReminder.Kind.CLOCK_OUT))

    return due


def _already_sent(person, day, kind) -> bool:
    return PunchReminder.objects.filter(employee=person, day=day, kind=kind).exists()


def send_reminders(company, now=None) -> int:
    """Send every due reminder once, and record that it went out.

    The record is written whether or not the mail leaves: an SMTP hiccup must
    not turn into the same nudge every five minutes. A reminder is a courtesy,
    not part of the register --- losing one is a worse day for somebody, not a
    hole in the record.
    """
    sent = 0
    for item in reminders_due(company, now):
        _, created = PunchReminder.objects.get_or_create(
            tenant=company, employee=item.employee, day=item.day, kind=item.kind
        )
        if not created:
            continue
        _deliver(item)
        sent += 1
    return sent


def _deliver(item) -> None:
    """Email today; the channel is a detail. The frontend is a PWA, so web push
    is the same message through a different pipe when it lands."""
    import logging

    from django.conf import settings
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils import translation
    from django.utils.translation import gettext as _

    log = logging.getLogger(__name__)
    person = item.employee
    if not person.email:
        return

    # This runs from cron, so no language is active. The person reads their own,
    # falling back to the company's, so a reminder does not arrive in English to
    # a Spanish worker just because it was a scheduled job that sent it. Both the
    # subject and the body are translated, so both go inside the override.
    language = person.locale or person.tenant.language
    clock_in = item.kind == PunchReminder.Kind.CLOCK_IN
    try:
        with translation.override(language):
            body = render_to_string(
                "emails/punch_reminder.txt",
                {
                    "first_name": person.first_name,
                    "company": person.tenant.name,
                    "clock_in": clock_in,
                    "day": item.day.strftime("%d/%m/%Y"),
                },
            )
            subject = _("Remember to clock in") if clock_in else _("You have not clocked out yet")
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[person.email],
            fail_silently=True,
        )
    except Exception:
        log.exception("Could not send punch reminder to %s", person.pk)
