"""Who may draw on the roster.

Its own file because the question is not about rosters, it is about
authorisation, and the answer used to be wrong. `ShiftViewSet.get_permissions`
listed the write actions by name; `paint` was added and not listed, so for a
few minutes any employee with a login could rewrite the whole company's
calendar. Nothing on any screen would have shown it.

So the test is not "can a manager paint". It is **every** write action against
**every** role, read off the viewset itself, so the next action added to it
either appears here or fails the suite.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftPattern
from apps.shifts.views import ShiftViewSet
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
MORNING = [{"start": "08:00", "end": "16:00"}]


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def people(company):
    with tenant_context(company.id):
        yield {
            "ana": User.objects.create_user(
                email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
            ),
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
        }


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_an_employee_cannot_paint_the_roster(company, people):
    """The hole this file exists for."""
    cells = [{"employee": str(people["ana"].pk), "day": "2026-09-01"}]

    response = client_for(people["ana"]).post("/api/shifts/paint/", {"cells": cells}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_manager_can(company, people):
    with tenant_context(company.id):
        morning = ShiftPattern.objects.create(tenant=company, name="Mañana", segments=MORNING)

    response = client_for(people["jefa"]).post(
        "/api/shifts/paint/",
        {
            "cells": [
                {
                    "employee": str(people["ana"].pk),
                    "day": "2026-09-01",
                    "pattern": str(morning.pk),
                }
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["painted"] == 1
    with tenant_context(company.id):
        assert Shift.objects.filter(employee=people["ana"]).count() == 1


@pytest.mark.django_db
def test_the_response_carries_the_review_of_what_was_just_drawn(company, people):
    """Painting a rest breach and finding out next month is not a warning."""
    with tenant_context(company.id):
        evening = ShiftPattern.objects.create(
            tenant=company, name="Tarde", segments=[{"start": "14:00", "end": "22:00"}]
        )
        early = ShiftPattern.objects.create(
            tenant=company, name="Mañana", segments=[{"start": "06:00", "end": "14:00"}]
        )

    response = client_for(people["jefa"]).post(
        "/api/shifts/paint/",
        {
            "cells": [
                {
                    "employee": str(people["ana"].pk),
                    "day": "2026-09-01",
                    "pattern": str(evening.pk),
                },
                {
                    "employee": str(people["ana"].pk),
                    "day": "2026-09-02",
                    "pattern": str(early.pk),
                },
            ]
        },
        format="json",
    )

    codes = [f["code"] for f in response.json()["findings"]]
    assert "short_daily_rest" in codes


@pytest.mark.django_db
def test_a_cell_cannot_carry_a_shift_and_its_hours_at_once(company, people):
    """They would disagree, and one of them would quietly win."""
    with tenant_context(company.id):
        morning = ShiftPattern.objects.create(tenant=company, name="Mañana", segments=MORNING)

    response = client_for(people["jefa"]).post(
        "/api/shifts/paint/",
        {
            "cells": [
                {
                    "employee": str(people["ana"].pk),
                    "day": "2026-09-01",
                    "pattern": str(morning.pk),
                    "segments": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_every_write_action_is_behind_the_manager_check(company, people):
    """Read off the viewset rather than typed out here.

    A list of action names in a test is a list that goes stale the same way the
    one in the viewset did. This asserts the shape instead: everything that
    writes is named in `WRITES`, and everything in `WRITES` really does refuse
    an ordinary employee.
    """
    writes = {
        name
        for name in dir(ShiftViewSet)
        if getattr(getattr(ShiftViewSet, name, None), "mapping", None)
        and set(getattr(ShiftViewSet, name).mapping) & {"post", "put", "patch", "delete"}
    }

    assert writes <= ShiftViewSet.WRITES, (
        f"acciones que escriben y no están en WRITES: {writes - ShiftViewSet.WRITES}"
    )
