"""Sets the tenant of the request, and the language it is answered in."""

from __future__ import annotations

from django.utils import timezone, translation

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
    """Activates the language and time zone of whoever is asking.

    Order of preference for the language: the person's own setting, then the
    company's, then whatever `LocaleMiddleware` worked out from the request.
    For the time zone there is no negotiation: it is the company's, because a
    working-day record has to read in the zone where the work happened.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        activated_language = False

        if user is not None and user.is_authenticated:
            company = getattr(user, "tenant", None)

            language = getattr(user, "locale", "") or (
                (company.settings or {}).get("language") if company else ""
            )
            if language:
                translation.activate(language)
                request.LANGUAGE_CODE = translation.get_language()
                activated_language = True

            if company is not None:
                timezone.activate(company.tzinfo)

        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
            if activated_language:
                translation.deactivate()
