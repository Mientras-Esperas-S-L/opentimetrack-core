"""Sending a notification to a browser, with nobody in the middle.

Web Push is a W3C standard, not a service: the server signs a message with its
own key pair (VAPID) and posts it to the address the browser gave, at the
browser vendor's push endpoint. There is no account to open and no third party
to trust with the content --- the payload is encrypted for that one subscription
and the vendor relays a blob it cannot read.

Two things follow, and both matter for a product meant to be self-hosted:

- **The keys belong to the deployment.** `python manage.py vapid_keys` prints a
  pair; they go in the environment and nowhere else. Without them push is
  simply off, and everything still works over email.
- **A dead address deletes itself.** When the vendor answers 404 or 410 the
  browser is gone for good --- uninstalled, permission revoked, profile wiped
  --- and the row goes with it. Anything else accumulates rot and eventually
  slows every send.

A notification is a courtesy on top of the record. Nothing here can fail in a
way that loses a punch, and nothing here writes to the register.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

log = logging.getLogger(__name__)


def push_is_configured() -> bool:
    """Whether this deployment can send push at all.

    Asked before offering it on screen: proposing to notify somebody and then
    silently doing nothing is worse than not offering it.
    """
    return bool(settings.WEBPUSH_PUBLIC_KEY and settings.WEBPUSH_PRIVATE_KEY)


def send_push(
    person,
    *,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "",
    personal: bool = False,
    urgent: bool = False,
) -> int:
    """Notify every browser and every app this person registered. Returns how
    many took it.

    `personal` says the body carries details of this person's working time (a
    shift that moved, its hours). Web Push encrypts for the browser alone, so it
    goes as it is; the app's relay (FCM) can read what it carries, so there the
    body is swapped for a neutral line and the details stay one tap away.

    `urgent` sends it, in the app, through the channel that rings and drops over
    whatever is on screen. Only for what has to be acted on now: a reminder to
    clock in is; a shift that moved next week is not.

    Never raises. A notification that fails is a notification that did not
    arrive, which is the same as the person having their phone off --- the
    caller has already recorded what it needed to record.
    """
    try:
        delivered = _send_to_apps(
            person, title=title, body=body, url=url, tag=tag, personal=personal, urgent=urgent
        )
    except Exception:
        log.exception("no se pudo avisar en la aplicación a %s", person.pk)
        delivered = 0
    if not push_is_configured():
        return delivered

    from apps.notifications.models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(employee=person))
    if not subscriptions:
        return delivered
    return delivered + _send_to_browsers(subscriptions, title=title, body=body, url=url, tag=tag)


def _send_to_browsers(subscriptions, *, title: str, body: str, url: str, tag: str) -> int:
    from apps.notifications.models import PushSubscription

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    delivered, dead = 0, []
    for subscription in subscriptions:
        outcome = _post_one(subscription, payload)
        if outcome == "gone":
            dead.append(subscription.pk)
        elif outcome == "sent":
            delivered += 1

    if dead:
        PushSubscription.objects.filter(pk__in=dead).delete()
    if delivered:
        PushSubscription.objects.filter(
            pk__in=[s.pk for s in subscriptions if s.pk not in dead]
        ).update(last_sent_at=timezone.now())
    return delivered


def _send_to_apps(
    person, *, title: str, body: str, url: str, tag: str, personal: bool, urgent: bool
) -> int:
    from apps.notifications import fcm
    from apps.notifications.models import NativePushDevice

    if not fcm.fcm_is_configured():
        return 0
    devices = list(NativePushDevice.objects.filter(employee=person))
    if not devices:
        return 0

    if personal:
        body = str(_("Open the app to see it."))
    delivered, dead = 0, []
    for device in devices:
        outcome = fcm.send_one(
            device.token,
            title=title,
            body=body,
            url=url,
            tag=tag,
            channel=fcm.URGENT_CHANNEL if urgent else "",
        )
        if outcome == "gone":
            dead.append(device.pk)
        elif outcome == "sent":
            delivered += 1

    if dead:
        NativePushDevice.objects.filter(pk__in=dead).delete()
    if delivered:
        NativePushDevice.objects.filter(pk__in=[d.pk for d in devices if d.pk not in dead]).update(
            last_sent_at=timezone.now()
        )
    return delivered


def _post_one(subscription, payload: str) -> str:
    """`sent`, `gone` (delete it) or `failed` (keep it, try again next time)."""
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:  # pragma: no cover - la dependencia está en base.txt
        log.warning("pywebpush no está instalado; no se envía push")
        return "failed"

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload,
            vapid_private_key=settings.WEBPUSH_PRIVATE_KEY,
            vapid_claims={"sub": settings.WEBPUSH_SUBJECT},
            ttl=settings.WEBPUSH_TTL_SECONDS,
        )
        return "sent"
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return "gone"
        log.warning("push rechazado (%s) para %s", status, subscription.pk)
        return "failed"
    except Exception:
        log.exception("no se pudo enviar push a %s", subscription.pk)
        return "failed"
