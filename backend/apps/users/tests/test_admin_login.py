"""Signing in to the Django admin site.

Worth its own file because it broke once and nothing else caught it: Django's
login form calls `authenticate(username=...)` regardless of what USERNAME_FIELD
is called, while the API calls it with `email=...`. A backend that only reads one
of the two leaves the admin site unusable while every API test stays green.
"""

from __future__ import annotations

import pytest
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import authenticate, get_user_model

from apps.tenants.models import Tenant

User = get_user_model()
PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="root@example.com",
        password=PASSWORD,
        first_name="Root",
        last_name="Local",
    )


@pytest.mark.django_db
def test_authenticate_accepts_the_username_keyword(superuser):
    """What Django's own form sends."""
    assert authenticate(None, username="root@example.com", password=PASSWORD) is not None


@pytest.mark.django_db
def test_authenticate_accepts_the_email_keyword(superuser):
    """What the API sends."""
    assert authenticate(None, email="root@example.com", password=PASSWORD) is not None


@pytest.mark.django_db
def test_a_platform_superuser_has_no_company(superuser):
    """It does not belong to any company because it does not operate on their data."""
    assert superuser.tenant_id is None
    assert superuser.is_staff and superuser.is_superuser


@pytest.mark.django_db
def test_the_admin_form_accepts_the_superuser(superuser):
    """The admin's own form, which is where the username/email mismatch bit.

    Driven directly rather than through the URL: the admin site is only routed
    when DEBUG is on, and Django turns DEBUG off during tests.
    """
    form = AdminAuthenticationForm(data={"username": "root@example.com", "password": PASSWORD})

    assert form.is_valid(), form.errors
    assert form.get_user() == superuser


@pytest.mark.django_db
def test_the_admin_form_rejects_somebody_without_staff_access(db):
    company = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    User.objects.create_user(
        email="ana@example.com",
        password=PASSWORD,
        tenant=company,
        first_name="Ana",
        last_name="García",
    )

    form = AdminAuthenticationForm(data={"username": "ana@example.com", "password": PASSWORD})

    # Correct credentials are not enough without staff access.
    assert not form.is_valid()
