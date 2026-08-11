"""Authentication with email unique per company, not globally.

Django assumes the sign-in field identifies a person across the whole system.
Not here: the same address may belong to two companies, so authentication has to
resolve which one first.

That is why this backend exists, rather than a check to silence.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class TenantEmailBackend(ModelBackend):
    """Authenticate by email, scoped to a company when it is known.

    Inherits from `ModelBackend` to keep the permission resolution the Django
    admin relies on, but **replaces** its authentication. It matters that this is
    the only configured backend: were `ModelBackend` left behind as a fallback,
    every security rejection made here -- email ambiguous across companies,
    company deactivated -- would land on it and be accepted, because it only
    looks at the address and `is_active`. Isolation at sign-in would cease to
    exist. Covered by the tests in `test_identity.py`.

    - Given `tenant_id`, the lookup is scoped to that company.
    - Without it, an address matching exactly one active person is accepted.
    - An address present in several companies is rejected. That is deliberate:
      picking one would be guessing, and the right answer is for the caller to
      name the company.
    """

    def authenticate(self, request, email=None, password=None, tenant_id=None, **kwargs):
        if email is None:
            email = kwargs.get(User.USERNAME_FIELD)
        if not email or password is None:
            return None

        lookup = Q(email__iexact=email.strip(), is_active=True)
        if tenant_id is not None:
            lookup &= Q(tenant_id=tenant_id)

        candidates = list(User.objects.filter(lookup)[:2])

        if not candidates:
            # Hash a throwaway password anyway, so response time does not reveal
            # whether the address exists.
            User().set_password(password)
            return None

        if len(candidates) > 1:
            return None

        user = candidates[0]

        # A federated account has no usable password here: its identity is
        # governed by the provider. `check_password` already rejects it, but
        # being explicit is worth the two lines.
        if user.is_federated and not user.has_usable_password():
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user) -> bool:
        """Neither the person nor their company may be deactivated."""
        if not user.is_active:
            return False
        if user.tenant_id is not None and not user.tenant.is_active:
            return False
        return True

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
