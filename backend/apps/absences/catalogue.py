"""Giving a company the leave catalogue of its country.

Copied rather than referenced, which is the decision worth understanding. The
framework knows what the law grants; the company knows what its collective
agreement grants, and the second is always at least the first and usually more.
If the catalogue were read live from the framework, improving a figure would
mean overriding it somewhere, and the day we corrected one of ours we would
quietly rewrite something somebody negotiated.

So: seed once, and after that the company's rows are the truth. Re-seeding adds
what is missing and **never touches what is there**.
"""

from __future__ import annotations

from apps import legal
from apps.absences.models import LeaveType


def seed_leave_types(company) -> dict:
    """Copies the country's catalogue into the company. Idempotent.

    Returns what it did, because the two numbers are different questions: a
    company that already had them wants to hear "nothing to add", and one being
    set up wants to hear how many it got.
    """
    framework = legal.for_company(company)
    known = set(LeaveType.objects.filter(tenant=company).values_list("code", flat=True))

    fresh = [
        LeaveType(
            tenant=company,
            code=kind.code,
            name=kind.name,
            family=kind.family,
            basis=kind.basis,
            amount=kind.amount,
            unit=kind.unit,
            period=kind.per,
            extra_when_travelling=kind.extra_when_travelling,
            paid=kind.paid,
            initiated_by=kind.initiated_by,
            needs_justification=kind.needs_justification,
            note=kind.note,
        )
        for kind in framework.leave_types
        if kind.code not in known
    ]
    LeaveType.objects.bulk_create(fresh)

    return {"added": len(fresh), "already_there": len(known)}
