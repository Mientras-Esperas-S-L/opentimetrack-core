"""Base models and tenant isolation.

This is the most delicate piece in the system. A query that escapes its tenant is
not a functional bug: it is a privacy breach that mixes the working hours of two
different companies. So isolation is not left to each view remembering to filter
-- it lives in the model's default manager.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models
from django.utils.translation import gettext_lazy as _

# Tenant of the request in flight. A context variable rather than a module
# attribute, because this has to stay correct under async servers too, where
# several requests share a thread.
_current_tenant: ContextVar[uuid.UUID | None] = ContextVar("current_tenant", default=None)


def get_current_tenant() -> uuid.UUID | None:
    return _current_tenant.get()


def set_current_tenant(tenant_id: uuid.UUID | None):
    return _current_tenant.set(tenant_id)


def reset_current_tenant(token) -> None:
    _current_tenant.reset(token)


@contextmanager
def tenant_context(tenant_id: uuid.UUID | None):
    """Run a block scoped to one tenant."""
    token = set_current_tenant(tenant_id)
    try:
        yield
    finally:
        reset_current_tenant(token)


class BaseModel(models.Model):
    """Opaque identifier and timestamps, shared by the whole domain."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant_id):
        return self.filter(tenant_id=tenant_id)


class TenantManager(models.Manager):
    """Default manager: always filters by the tenant in context.

    With no tenant set it returns nothing rather than everything. That asymmetry
    is deliberate -- the default failure mode has to be seeing no data, never
    seeing too much.
    """

    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        tenant_id = get_current_tenant()
        if tenant_id is None:
            return qs.none()
        return qs.filter(tenant_id=tenant_id)


class AllTenantsManager(models.Manager):
    """Unfiltered manager, for migrations, system tasks and tests.

    The name is long on purpose: seeing `objects_all_tenants` inside a view
    should stand out in review.
    """

    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)


class TenantOwnedModel(BaseModel):
    """Everything that belongs to a company inherits from here."""

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
        verbose_name=_("company"),
    )

    # The default manager filters. The unfiltered one must be asked for by name.
    objects = TenantManager()
    objects_all_tenants = AllTenantsManager()

    class Meta:
        abstract = True
