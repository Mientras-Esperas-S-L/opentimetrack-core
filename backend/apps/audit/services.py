"""Writing to the audit trail.

One function, `record`, deliberately hard to get wrong: it never raises, it
never blocks the request, and it copies the labels it needs so an entry still
reads sensibly years later when the person has left and the record is gone.

**It never raises** because of what it is used for. If writing the trail could
break a request, the first production incident would be somebody unable to
clock in because the audit table was full. The trail is evidence of what
happened; it must not become a reason for things not to happen. A failure gets
logged loudly instead.
"""

from __future__ import annotations

import logging

from django.db import transaction

from apps.audit.models import AuditLog

log = logging.getLogger(__name__)


def record(
    *,
    action: str,
    actor=None,
    #: Cuando quien actúa no es una persona. Una aplicación integrada empuja un
    #: alta y no tiene fila en `users`, así que sin esto el rastro diría
    #: «sistema» y no se sabría **qué** integración lo hizo --- que es
    #: precisamente lo que hay que poder mirar cuando una ficha cambia sola.
    actor_label: str = "",
    company=None,
    target=None,
    target_type: str = "",
    target_label: str = "",
    changes: dict | None = None,
    note: str = "",
) -> None:
    """Adds an entry. Silent on success, loud on failure, never fatal.

    `company` can be left out when there is an actor: theirs is used. It is a
    parameter at all for the cases where there is no actor to ask --- a failed
    sign-in, or a purge running from cron.
    """
    try:
        tenant = company or getattr(actor, "tenant", None)
        if tenant is None:
            # Without a company the entry cannot be scoped, and an unscoped
            # entry is one another company could read. Dropped, and said.
            log.warning("Audit entry without a company, dropped: %s", action)
            return

        entry = AuditLog(
            tenant=tenant,
            actor=actor if getattr(actor, "pk", None) else None,
            actor_label=actor_label or _label_of(actor),
            action=action,
            target_type=target_type or (type(target).__name__.lower() if target else ""),
            target_id=getattr(target, "pk", None),
            target_label=target_label or (str(target)[:200] if target else ""),
            changes=changes or {},
            note=note[:300],
        )
        # After commit: an entry describing something that then rolled back
        # would be a lie, and a lie in the audit trail is worse than a gap.
        transaction.on_commit(entry.save)
    except Exception:
        log.exception("Could not record an audit entry: %s", action)


def _label_of(actor) -> str:
    if actor is None:
        return "sistema"
    name = getattr(actor, "get_full_name", lambda: "")() or getattr(actor, "email", "")
    return str(name)[:160]


def record_view_of_others(*, request, target_employee, note: str = "") -> None:
    """Reading somebody else's record. The entry that was missing entirely.

    Reading your own leaves no trace, on purpose: it is a right, and logging it
    would bury the entries that matter under thousands that do not.
    """
    from apps.audit.models import AuditAction

    if target_employee is None or target_employee.id == request.user.id:
        return

    record(
        action=AuditAction.RECORD_VIEWED,
        actor=request.user,
        target=target_employee,
        target_type="user",
        target_label=target_employee.get_full_name() or target_employee.email,
        note=note,
    )
