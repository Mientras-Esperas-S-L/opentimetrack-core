"""In what language, and in what time zone, a request is answered.

Lives apart from the middleware that used to do this because **the middleware
could not**. The API authenticates by bearer token, which DRF resolves inside
the view; when middleware runs there is no caller yet and `request.user` is
still anonymous. So a middleware that reads `request.user` to pick a language
picks nobody's, on every single API request, silently.

The codebase had already hit this and written it down --- `TenantMiddleware`
says the tenant "is set again by the permission class" for bearer-token
requests --- and the language sitting right below it never got the same
treatment. This is that treatment.

Deactivation stays in the middleware, which is the only thing wrapping the whole
request: a language left active outlives the response and the next request to
reuse the thread inherits it.
"""

from __future__ import annotations

from django.utils import timezone, translation


def activate_for(caller) -> None:
    """Activates the caller's language and their company's time zone.

    The language is the person's own choice first, and their company's when
    they have not made one. An application has no language of its own, so it
    gets its company's, which is the right answer: what it sends back reaches
    that company's people.

    The time zone is not negotiated. It is the company's, because a working-day
    record has to read in the zone where the work happened --- what matters is
    when the shift started for whoever worked it, not where the server is.
    """
    if caller is None or not getattr(caller, "is_authenticated", False):
        return

    company = getattr(caller, "tenant", None)

    # `locale` is the person's override and is blank far more often than not.
    # `Tenant.language` is the real column with the choices and the default;
    # the middleware used to read `company.settings["language"]`, a key of a
    # JSON blob that nothing in the codebase has ever written.
    language = getattr(caller, "locale", "") or (
        getattr(company, "language", "") if company else ""
    )
    if language:
        translation.activate(language)

    if company is not None:
        tzinfo = getattr(company, "tzinfo", None)
        if tzinfo is not None:
            timezone.activate(tzinfo)
