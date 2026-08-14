"""Sets the tenant of the request, and the language it is answered in."""

from __future__ import annotations

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
