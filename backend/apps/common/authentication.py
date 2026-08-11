"""Authentication for external applications.

Separate from the JWT of a person because they are different actors and must not
be confused: a request arriving with an application credential has no user, and
whatever it does has to be attributable to the application, not to somebody who
happens to be nearby.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions

from apps.common.models import set_current_tenant
from apps.tenants.applications import TOKEN_PREFIX, ApplicationCredential


class ApplicationUser:
    """Stands in for `request.user` when the caller is an application.

    DRF and Django assume there is a user. Rather than leaving it empty, which
    would make `IsAuthenticated` behave unpredictably, an explicit object says
    what this is: authenticated, not a person, and carrying its own permissions.
    """

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, credential: ApplicationCredential):
        self.credential = credential
        self.application = credential.application
        self.tenant = credential.application.tenant
        self.tenant_id = credential.application.tenant_id

    def __str__(self) -> str:
        return f"application:{self.application.name}"

    def allows(self, scope: str) -> bool:
        return self.application.allows(scope)

    # A person's attributes, answered so that shared code does not have to ask
    # what kind of caller it is dealing with.
    @property
    def can_manage(self) -> bool:
        return False

    @property
    def is_admin(self) -> bool:
        return False


class ApplicationAuthentication(authentication.BaseAuthentication):
    """Reads `Authorization: Bearer ott_app_…`.

    Ignores anything that does not carry the application prefix, so it can sit
    alongside JWT authentication without either getting in the other's way.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()

        if len(header) != 2 or header[0].lower() != self.keyword.lower().encode():
            return None

        raw = header[1].decode()
        if not raw.startswith(TOKEN_PREFIX):
            # A person's JWT. Not ours; let the next backend deal with it.
            return None

        credential = (
            ApplicationCredential.objects_all_tenants.select_related("application__tenant")
            .filter(token_hash=ApplicationCredential.hash_token(raw))
            .first()
        )

        # The same answer whether the token never existed, expired or was
        # revoked. Telling them apart would confirm to whoever holds a leaked
        # token that it was once valid.
        if credential is None or not credential.is_valid:
            raise exceptions.AuthenticationFailed(_("Invalid credential."))

        if not credential.application.tenant.is_active:
            raise exceptions.AuthenticationFailed(_("Invalid credential."))

        credential.touch()
        set_current_tenant(credential.application.tenant_id)

        return (ApplicationUser(credential), credential)

    def authenticate_header(self, request):
        return self.keyword


class ApplicationAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describes the application credential in the published schema.

    Without this the generator warns that it cannot resolve the authenticator
    and, worse, the documentation would not tell an integrator how to
    authenticate -- which is the first thing they need to know.
    """

    target_class = "apps.common.authentication.ApplicationAuthentication"
    name = "applicationCredential"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "ott_app_…",
            "description": (
                "Credential of an external application, issued by the company that "
                "authorises it. Carries only the permissions granted to that "
                "application and can be revoked without affecting anyone's account."
            ),
        }
