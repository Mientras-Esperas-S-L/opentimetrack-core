"""Clocking in from an external application.

This is the reason the project exists: a product like GreenCity records the
working time of its field operatives against this service instead of keeping its
own module. What is checked here is that it works, that it does not become a way
around isolation, and that the resulting record still says what it is.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchSource
from apps.reports.services import build_report, day_notes, to_csv
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def other_company(db):
    return Tenant.objects.create(name="Globex Inc", tax_id="B22222222")


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="marta@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Marta",
            last_name="Ruiz",
            employee_id="EMP-0003",
        )


def authorise(company, scopes, name="GreenCity"):
    with tenant_context(company.id):
        application = Application.objects.create(tenant=company, name=name, scopes=scopes)
        _credential, raw = ApplicationCredential.issue(application)
    return application, raw


def as_application(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


# --------------------------------------------------------------------- happy path


@pytest.mark.django_db
def test_an_application_clocks_in_for_an_employee(client, company, employee):
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003", "device_id": "site-tablet"}
    )

    assert response.status_code == 201
    assert response.data["source"] == PunchSource.DELEGATED
    assert response.data["source_application"] == "GreenCity"
    assert response.data["day_status"]["state"] == "WORKING"


@pytest.mark.django_db
def test_the_employee_can_be_named_by_staff_number_email_or_id(client, company, employee):
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = as_application(client, token)

    for reference in ("EMP-0003", "marta@example.com", str(employee.id)):
        response = caller.post(reverse("punch-delegated"), {"employee_ref": reference})
        assert response.status_code == 201, reference


@pytest.mark.django_db
def test_a_shared_terminal_is_recorded_as_such(client, company, employee):
    """Not the same as an application acting on its own: worth telling apart."""
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003", "terminal": True}
    )

    assert response.data["source"] == PunchSource.TERMINAL


@pytest.mark.django_db
def test_the_server_still_owns_the_clock(client, company, employee):
    """Delegating who presses the button does not delegate who sets the time."""
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"),
        {
            "employee_ref": "EMP-0003",
            # Both ignored: they are not even in the serializer.
            "timestamp": "2020-01-01T00:00:00Z",
            "punch_type": "OUT",
        },
    )

    assert response.status_code == 201
    assert response.data["punch_type"] == "IN"  # inferred, not accepted
    assert response.data["timestamp"].startswith("20")
    assert not response.data["timestamp"].startswith("2020")


# ------------------------------------------------------------------- permissions


@pytest.mark.django_db
def test_without_the_permission_it_is_refused(client, company, employee):
    """An application that may only read must not be able to clock in."""
    _app, token = authorise(company, [ApplicationScope.READ_ATTENDANCE])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_application_with_no_permissions_can_do_nothing(client, company, employee):
    _app, token = authorise(company, [])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_deactivated_application_stops_working(client, company, employee):
    app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    app.is_active = False
    app.save()

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_a_revoked_credential_stops_working(client, company, employee):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="GreenCity", scopes=[ApplicationScope.PUNCH_DELEGATED]
        )
        credential, token = ApplicationCredential.issue(application)
        credential.revoke()

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_a_made_up_token_is_refused(client, company, employee):
    response = as_application(client, "ott_app_made-up").post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 401


# --------------------------------------------------------------------- isolation


@pytest.mark.django_db
def test_an_application_cannot_reach_another_company(client, company, other_company, employee):
    """The reason this test exists: a delegated door is a door.

    An application of Globex naming an employee of ACME must find nobody, even
    knowing the exact staff number.
    """
    _app, token = authorise(other_company, [ApplicationScope.PUNCH_DELEGATED], name="Otra")

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "employee_not_found"
    assert Punch.objects_all_tenants.count() == 0


@pytest.mark.django_db
def test_an_unknown_reference_is_refused(client, company, employee):
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "does-not-exist"}
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "employee_not_found"


# ------------------------------------------------------------------ the evidence


@pytest.mark.django_db
def test_delegation_reaches_the_report(client, company, employee):
    """What ADR-0010 promises: an inspector can tell the two apart.

    Both outputs are checked, because they drifted apart once already -- the PDF
    said it and the CSV kept quiet.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    as_application(client, token).post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    from django.utils import timezone

    today = timezone.now().astimezone(company.tzinfo).date()
    with tenant_context(company.id):
        report = build_report(employee=employee, company=company, date_from=today, date_to=today)

        assert report.rows[0].delegated
        assert "application" in day_notes(report.rows[0])
        assert "application" in to_csv(report)


@pytest.mark.django_db
def test_credentials_are_not_stored_in_the_clear(company):
    """A secret the server can read back is a secret the server can leak."""
    with tenant_context(company.id):
        application = Application.objects.create(tenant=company, name="GreenCity", scopes=[])
        credential, raw = ApplicationCredential.issue(application)

        assert credential.token_hash != raw
        assert raw not in credential.token_hash
        assert len(credential.token_hash) == 64
        # Only the tail is kept, to tell one credential from another.
        assert credential.token_hint == raw[-6:]
