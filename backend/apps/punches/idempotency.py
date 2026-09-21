"""Answering a retry with what it already recorded, instead of recording it twice.

The commonest way a client fails is not losing the write: it is losing the **answer**.
The punch is stored, the response times out or the phone loses signal, and whatever
sent it tries again. Here that retry is not harmless --- the type is inferred from the
state, so a repeated "clock Rosa in" records a clock *out*, and a nine-hour day reads
as thirty seconds. The double-tap guard does not reach it either: five seconds is a
finger, not a queue draining after an hour in a park with no coverage.

Two doors need this and they are the same problem, so the rules live here rather than
in each: the delegated punch, where an application acts for somebody, and the ordinary
punch made through an application acting with the person's own session. Both have an
application at the other end, which is what the receipt is scoped to --- two
connectors numbering their own operations must not collide, and one must never read
back an event the other recorded.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.punches.models import DelegatedPunchReceipt

#: Cuánto de la cabecera se guarda. Lo que pase de aquí se recorta en vez de
#: rechazarse: una clave larga sigue identificando la operación.
MAX_KEY = 200


def key_from(request) -> str:
    """The `Idempotency-Key` header, trimmed, or empty when it was not sent."""
    return (request.headers.get("Idempotency-Key") or "").strip()[:MAX_KEY]


def already_recorded(application, key: str):
    """The punch this key already produced, or `None` if it produced none yet.

    Raises `in_progress` for a key that was claimed but never finished: the first
    request is still in flight or died before committing. Saying "in progress" sends
    the caller back later; answering as if it had worked would be a lie about a record
    that has to be reliable.
    """
    done = DelegatedPunchReceipt.objects.filter(application=application, key=key).first()
    if done is None:
        return None
    if done.punch is None:
        raise _in_progress()
    return done.punch


def claim(company, application, key: str):
    """Reserves the key **before** recording, so two retries at once cannot both pass.

    Returns the receipt to fill in once the punch exists. If another request claimed it
    a moment ago, returns its punch instead --- the caller answers with that one --- or
    raises `in_progress` if that other request has not finished.
    """
    try:
        with transaction.atomic():
            return DelegatedPunchReceipt.objects.create(
                tenant=company, application=application, key=key
            ), None
    except IntegrityError:
        done = DelegatedPunchReceipt.objects.filter(application=application, key=key).first()
        if done is not None and done.punch is not None:
            return None, done.punch
        raise _in_progress() from None


def settle(receipt, punch) -> None:
    """Ties the key to what it produced, so the next retry finds it."""
    receipt.punch = punch
    receipt.save(update_fields=["punch", "updated_at"])


def _in_progress() -> BusinessRuleError:
    return BusinessRuleError(
        code="in_progress",
        message=_("That operation is still being recorded. Try again shortly."),
    )
