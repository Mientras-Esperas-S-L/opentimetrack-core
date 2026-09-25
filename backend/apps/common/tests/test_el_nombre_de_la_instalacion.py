"""The name people see: OpenTimeTrack, unless the installation sets its own.

A company can run the Core as one more part of its own product. Its people should
see that product's name on the sign-in screen and at the foot of the mail, while
whatever connects to the installation still learns that OpenTimeTrack answers.
"""

from __future__ import annotations

import pytest
from django.template.loader import render_to_string
from django.test import override_settings
from rest_framework.test import APIClient

REMINDER = {
    "first_name": "Ana",
    "company": "Empresa de Ejemplo",
    "clock_in": True,
    "day": "01/09/2026",
}
REPRESENTATIVES = {"company": "Empresa de Ejemplo", "employee": "Ana Ejemplo", "day": "01/09/2026"}


@pytest.mark.django_db
def test_without_a_name_of_its_own_the_installation_is_opentimetrack():
    data = APIClient().get("/api/instance/").data

    assert data["name"] == "OpenTimeTrack"
    assert data["product"] == "OpenTimeTrack"


@pytest.mark.django_db
@override_settings(INSTALLATION_NAME="Fichaje de Ejemplo")
def test_the_installation_shows_its_own_name_and_still_says_what_it_is():
    """The name is for people; `product` is for whoever connects, and never changes."""
    data = APIClient().get("/api/instance/").data

    assert data["name"] == "Fichaje de Ejemplo"
    assert data["product"] == "OpenTimeTrack"


@pytest.mark.parametrize(
    ("template", "context"),
    [
        ("emails/punch_reminder.txt", REMINDER),
        ("emails/representatives_informed.txt", REPRESENTATIVES),
    ],
)
@override_settings(INSTALLATION_NAME="Fichaje de Ejemplo")
def test_the_mail_is_signed_with_the_installation_name(template, context):
    body = render_to_string(template, context)

    assert body.rstrip().endswith("Fichaje de Ejemplo")
    assert "OpenTimeTrack" not in body


@pytest.mark.parametrize(
    ("template", "context"),
    [
        ("emails/punch_reminder.txt", REMINDER),
        ("emails/representatives_informed.txt", REPRESENTATIVES),
    ],
)
def test_by_default_the_mail_is_signed_opentimetrack(template, context):
    assert render_to_string(template, context).rstrip().endswith("OpenTimeTrack")
