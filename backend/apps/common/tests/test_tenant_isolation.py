"""Isolation between companies.

These tests matter more than the rest. A leak across companies is not a
functional bug: it is a privacy breach, in a system holding the working hours of
real people, mixing data from two different clients.

The stated goal is zero leaks, so this covers both the default mechanism and
what happens when somebody forgets to set the company.
"""

from __future__ import annotations

import pytest

from apps.common.models import get_current_tenant, tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department


@pytest.fixture
def acme(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def globex(db):
    return Tenant.objects.create(name="Globex Inc", tax_id="B22222222")


@pytest.fixture
def departments(acme, globex):
    with tenant_context(acme.id):
        a = Department.objects.create(tenant=acme, name="Works")
    with tenant_context(globex.id):
        g = Department.objects.create(tenant=globex, name="Gardening")
    return a, g


@pytest.mark.django_db
def test_each_company_only_sees_its_own(acme, departments):
    acme_dep, globex_dep = departments

    with tenant_context(acme.id):
        visible = list(Department.objects.all())

    assert visible == [acme_dep]
    assert globex_dep not in visible


@pytest.mark.django_db
def test_with_no_company_set_nothing_is_visible(departments):
    """The default failure mode is seeing no data, never seeing too much."""
    assert get_current_tenant() is None
    assert list(Department.objects.all()) == []


@pytest.mark.django_db
def test_another_companys_record_is_not_reachable_by_id(acme, departments):
    """Knowing the identifier of someone else's record is not enough to read it.

    This is the insecure direct object reference case: somebody tries an id that
    is not theirs.
    """
    _, globex_dep = departments

    with tenant_context(acme.id):
        assert not Department.objects.filter(pk=globex_dep.pk).exists()
        with pytest.raises(Department.DoesNotExist):
            Department.objects.get(pk=globex_dep.pk)


@pytest.mark.django_db
def test_the_unfiltered_manager_exists_but_must_be_named(departments):
    """Querying everything stays possible, but never by accident."""
    assert Department.objects_all_tenants.count() == 2


@pytest.mark.django_db
def test_the_context_is_restored_on_exit(acme, globex):
    with tenant_context(acme.id):
        assert get_current_tenant() == acme.id
        with tenant_context(globex.id):
            assert get_current_tenant() == globex.id
        # Leaving the inner block restores the outer one, not the last one seen.
        assert get_current_tenant() == acme.id
    assert get_current_tenant() is None


@pytest.mark.django_db
def test_the_context_is_restored_even_after_an_exception(acme):
    with pytest.raises(ValueError), tenant_context(acme.id):
        raise ValueError("failure halfway through")

    assert get_current_tenant() is None
