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
            # **Cortados al límite de su columna, siempre.** El truncado estaba,
            # pero solo en la rama que deriva la etiqueta de `target`: cuando se
            # la pasan hecha ---y se la pasan en casi todas las llamadas--- iba
            # entera. Una razón social de doscientos veintinueve caracteres es
            # válida para `Tenant.name`, que admite doscientos cincuenta y cinco,
            # y reventaba esta columna de doscientos: la petición contestaba
            # **500** y el cambio se revertía entero.
            #
            # Cortar es lo correcto y no una rebaja: la etiqueta es «lo que se
            # vio», un apoyo para leer el rastro. Lo que identifica la fila es
            # `target_id`, y ese no se toca.
            actor_label=_cortado(actor_label or _label_of(actor), 160),
            action=action,
            target_type=target_type or (type(target).__name__.lower() if target else ""),
            target_id=getattr(target, "pk", None),
            target_label=_cortado(target_label or (str(target) if target else ""), 200),
            changes=changes or {},
            note=_cortado(note, 300),
        )
        # After commit: an entry describing something that then rolled back
        # would be a lie, and a lie in the audit trail is worse than a gap.
        #
        # Y **envuelto**, porque este `try` no lo cubría: el `save` corre después,
        # al confirmar, así que cualquier fallo suyo escapaba de aquí y tumbaba
        # la petición. El docstring prometía «never fatal» y no lo era. Un hueco
        # en el rastro es malo; un hueco **y** un 500 al cliente es peor, y deja
        # además sin hacer lo que la persona pedía.
        transaction.on_commit(lambda: _guardar(entry, action))
    except Exception:
        log.exception("Could not record an audit entry: %s", action)


def _cortado(valor: str, largo: int) -> str:
    """Lo que quepa en su columna. `None` y no cadenas se toleran: esto corre al
    borde de operaciones que ya salieron bien, y no es sitio para reventar."""
    return str(valor or "")[:largo]


def _guardar(entry, action: str) -> None:
    """El asiento, ya confirmada la operación que describe.

    Ruidoso al fallar y nunca fatal: aquí la transacción ya se ha cerrado, de
    modo que lanzar no deshace nada ---solo convierte una operación buena en un
    error para quien la pidió--- y encima deja el hueco igual.
    """
    try:
        entry.save()
    except Exception:
        log.exception("Could not save an audit entry after commit: %s", action)


def _label_of(actor) -> str:
    if actor is None:
        return "sistema"
    if getattr(actor, "is_support", False):
        # Una sola cuenta de soporte por empresa: quién de la instalación estaba
        # detrás viaja en su sesión, y es lo que el asiento tiene que decir.
        quien = getattr(actor, "support_by", "")
        return (f"Soporte ({quien})" if quien else "Soporte")[:160]
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


def record_platform(
    *,
    action: str,
    actor,
    company=None,
    target=None,
    target_type: str = "",
    target_label: str = "",
    changes: dict | None = None,
    note: str = "",
) -> None:
    """Adds an entry to the installation's own trail. Same promises as `record`.

    Never raises, lands only if the request commits, and copies the labels. It
    is the installation's side only: what it does to a company also goes to
    that company's trail, with `record`, so its administrator can see it.
    """
    from apps.audit.models import PlatformAuditEntry

    try:
        entry = PlatformAuditEntry(
            actor=actor if getattr(actor, "pk", None) else None,
            actor_label=_label_of(actor),
            action=action,
            company=company,
            company_label=(company.name[:255] if company is not None else ""),
            target_type=target_type or (type(target).__name__.lower() if target else ""),
            target_id=getattr(target, "pk", None),
            target_label=_cortado(target_label or (str(target) if target else ""), 200),
            changes=changes or {},
            note=_cortado(note, 300),
        )
        # Lo mismo que en `record`: cortado a su columna y guardado sin tumbar nada.
        transaction.on_commit(lambda: _guardar(entry, action))
    except Exception:
        log.exception("Could not record an installation audit entry: %s", action)
