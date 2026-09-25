"""Who is calling, as an address, behind however many proxies the install has.

`X-Forwarded-For` is a list that every proxy on the way *appends* to, and whose
first entries are whatever the client chose to send. Taking the first one --- as
the punch and the failed sign-in log did --- let anybody pick the address that
went on their punch. And DRF, with `NUM_PROXIES` unset, keys its rate limits on
the whole header, so sending a different one on every request started a fresh
bucket each time: five sign-in attempts a minute became as many as anybody
cared to make.

The only entries that can be trusted are the ones our own proxies wrote, at the
end of the list. How many there are is a setting, `TRUSTED_PROXIES`, and DRF
reads the same number as `NUM_PROXIES`. This module goes through DRF's own
reading of it, so there is one rule and not two that can drift apart.
"""

from __future__ import annotations

from rest_framework.throttling import BaseThrottle


def client_ip(request) -> str | None:
    """The caller's address, as far as this deployment can vouch for it."""
    return BaseThrottle().get_ident(request) or None
