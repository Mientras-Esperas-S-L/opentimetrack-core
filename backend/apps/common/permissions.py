"""Role permissions, and where the tenant gets set for API requests.

Token authentication is resolved inside the view, later than the middleware, so
this is where the tenant is pinned for API traffic.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.common.models import set_current_tenant


class IsAuthenticatedInTenant(BasePermission):
    """Requires a valid session and pins its company.

    Every permission in the application inherits from this one, so that no view
    can run without isolation being active.
    """

    message = _("A valid session is required.")

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # A platform superuser without a company only exists on self-hosted
        # installs and does not operate on service data.
        if user.tenant_id is None:
            return bool(user.is_superuser)

        set_current_tenant(user.tenant_id)
        return True


class IsAdmin(IsAuthenticatedInTenant):
    message = _("Only an administrator may perform this operation.")

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.is_admin


class IsManagerOrAdmin(IsAuthenticatedInTenant):
    message = _("Manager or administrator profile required.")

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.can_manage


class ReadForAllWriteForAdmin(IsAuthenticatedInTenant):
    """Anyone in the company reads; only an administrator writes."""

    message = _("Only an administrator may modify this resource.")

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin


class IsOwnerOrCanManage(IsAuthenticatedInTenant):
    """Each person sees their own; managers and admins see their scope.

    This is the permission behind clock events and absences: a worker is entitled
    to their own history, which the law requires, but not to a colleague's.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        owner_id = getattr(obj, "employee_id", None)
        if owner_id == request.user.id:
            return True
        if not request.user.can_manage:
            return False
        # "Their scope" used to mean the whole company. It now means the
        # departments they answer for, and the object check has to agree with
        # the list check or a row hidden from the list is still readable by id.
        from apps.common.scope import visible_people

        scope = visible_people(request.user)
        return scope is None or scope.filter(pk=owner_id).exists()


class HasApplicationScope(BasePermission):
    """The caller is an application and carries the required permission.

    The scope is declared on the view as `required_scope`. A view without it
    denies access rather than allowing it: forgetting to declare a permission
    must not open a door.
    """

    message = _("The application does not carry the required permission.")

    def has_permission(self, request, view) -> bool:
        caller = request.user
        if not (caller and getattr(caller, "is_authenticated", False)):
            return False
        if not hasattr(caller, "allows"):
            return False  # a person, not an application

        scope = getattr(view, "required_scope", None)
        if scope is None:
            return False

        if not caller.allows(scope):
            return False

        set_current_tenant(caller.tenant_id)
        return True
