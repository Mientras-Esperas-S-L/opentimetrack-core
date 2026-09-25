"""Sets the tenant of the request and its language, and checks the proxy setting."""

from __future__ import annotations

import ipaddress
import logging

from django.conf import settings
from django.utils import timezone, translation

from apps.common.locale import activate_for
from apps.common.models import reset_current_tenant, set_current_tenant


class TenantMiddleware:
    """Keeps the tenant set for the life of the request, and clears it after.

    The tenant is **always** derived from whoever is authenticated, never from
    anything the client sends: not a header, not a parameter, not the body.
    Accepting a company identifier from outside would turn isolation into a
    suggestion.

    Runs after Django's authentication. API views authenticate with a bearer
    token, which is resolved later in the cycle, so for those the tenant is set
    again by the permission class.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        tenant_id = getattr(user, "tenant_id", None) if user else None

        token = set_current_tenant(tenant_id)
        try:
            return self.get_response(request)
        finally:
            # Without this the context would outlive the request and the next
            # one reusing the thread would inherit the previous company.
            reset_current_tenant(token)


class LocaleAndTimeZoneMiddleware:
    """Clears the language and time zone after every request, and sets them for
    the ones where it can.

    It used to do the whole job here, and for the API it did **nothing at all**:
    the language block hung off `request.user.is_authenticated`, and API callers
    authenticate with a bearer token that DRF resolves inside the view. At
    middleware time there is no caller yet, so the condition was false on every
    API request and neither the language nor the time zone was ever activated.

    The class two above says exactly this about the tenant ---"for those the
    tenant is set again by the permission class"--- and this one, written right
    below it with the same shape, never got the same treatment. The activation
    now lives in `apps.common.locale.activate_for`, called from the permission
    class for bearer-token callers and from here for the paths where there
    really is a user this early: the Django admin, and anything session-based.

    What has to stay here is the clearing. `translation.activate` and
    `timezone.activate` set thread locals, and this is the only thing that wraps
    the whole request: without the `finally` the next request to reuse the
    thread would answer in the previous caller's language. Both are cleared
    unconditionally now, because who activated them is no longer knowable from
    here.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            activate_for(user)
            request.LANGUAGE_CODE = translation.get_language()

        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
            translation.deactivate()


class ProxyConfigurationCheck:
    """Says so in the log, once, when a proxy is plainly in front and nobody said.

    With `TRUSTED_PROXIES` at 0 behind a proxy, every caller arrives from the
    proxy's address: they all share one rate-limit bucket, and five failed
    sign-ins anywhere lock everybody out for a minute. The symptom points at
    the login, not at the setting, so the setting gets named here.

    «Plainly» is a forwarded header arriving from an address that is not on the
    internet. It does not change anything --- guessing the count is the mistake
    this setting exists to avoid --- it only says what to look at.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.warned = False

    def __call__(self, request):
        if not self.warned and request.META.get("HTTP_X_FORWARDED_FOR"):
            self._check(request)
        return self.get_response(request)

    def _check(self, request):
        if settings.TRUSTED_PROXIES:
            self.warned = True
            return
        try:
            local = not ipaddress.ip_address(request.META.get("REMOTE_ADDR", "")).is_global
        except ValueError:
            return
        if local:
            self.warned = True
            logging.getLogger("security").warning(
                "Requests arrive with X-Forwarded-For from %s but TRUSTED_PROXIES is 0: every "
                "caller is counted as that address and they all share one rate limit. Set "
                "TRUSTED_PROXIES to the number of proxies in front of the API (1 behind a "
                "single nginx or Caddy).",
                request.META.get("REMOTE_ADDR"),
            )
