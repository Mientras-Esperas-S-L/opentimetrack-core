"""Rate limits that know the difference between a person and an application.

The rates were declared in settings and nothing applied them: DRF only reads
`throttle_scope` when `ScopedRateThrottle` is among the throttle classes, and
only enforces the anon/user rates when those classes are listed. None of the
three was. So `login: 5/min` allowed as many password attempts as anybody cared
to make, and the recovery endpoint would send as much mail as it was asked to,
to any address.

Turning them on plainly broke every external integration, which is worth
recording because the failure was silent in a different way: DRF's
`UserRateThrottle` builds its cache key from `request.user.pk`, and an
application authenticates as `ApplicationUser`, a stand-in with no primary key.
Every delegated punch answered with an AttributeError.

Hence these two. An application is a legitimate caller and should be limited
too --- an integration in a loop is the likeliest source of a flood --- but it is
limited *as an application*, by its own credential and at its own rate.
"""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


def _application_of(request):
    """The calling application, or None when the caller is a person."""
    caller = getattr(request, "user", None)
    return getattr(caller, "application", None) if hasattr(caller, "allows") else None


class PersonRateThrottle(UserRateThrottle):
    """The ordinary per-person limit, which skips applications.

    Returning None from `get_cache_key` tells DRF this throttle does not apply,
    which is how a caller it cannot key is meant to be handled --- rather than
    reaching for a `pk` that is not there.
    """

    scope = "user"

    def get_cache_key(self, request, view):
        if _application_of(request) is not None:
            return None
        return super().get_cache_key(request, view)


class ApplicationRateThrottle(UserRateThrottle):
    """The per-application limit, keyed on the credential.

    On the credential and not on the application: revoking one and issuing
    another is how a leaked key is dealt with, and the new one should not
    inherit the spent budget of the old.
    """

    scope = "application"

    def get_cache_key(self, request, view):
        application = _application_of(request)
        if application is None:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.credential.pk),
        }
