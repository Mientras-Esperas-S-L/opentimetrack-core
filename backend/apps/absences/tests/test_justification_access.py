"""Who can download a supporting document, and who cannot.

The store is a deployment choice --- a disk on one server, or object storage
when there is more than one process --- but **access control is not**. Both
paths go through the same endpoint and the same check.

The hole this closes: before, the file URL travelled in the serialiser and
`MEDIA_URL` was one nginx rule away from being public. A path under /media/
that a web server happens to expose hands the document to anybody who guesses
it, with no session at all.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def make(company, email, role=Role.EMPLOYEE):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email, password=PASSWORD, tenant=company, first_name=email[:3], role=role
        )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def leave_with_file(company, person, content=b"%PDF-1.4 citacion judicial"):
    with tenant_context(company.id):
        return request_absence(
            employee=person,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            justification=SimpleUploadedFile("citacion.pdf", content, "application/pdf"),
        )


# ------------------------------------------------------------------- the check


@pytest.mark.django_db
def test_you_can_download_your_own(company):
    ana = make(company, "ana@example.com")
    absence = leave_with_file(company, ana)

    response = client_for(ana).get(f"/api/absences/{absence.id}/justification/")

    assert response.status_code == 200
    assert b"citacion judicial" in b"".join(response.streaming_content)


@pytest.mark.django_db
def test_a_colleague_cannot(company):
    """The one that matters. Absences reveal who was off and for how long."""
    ana = make(company, "ana@example.com")
    beto = make(company, "beto@example.com")
    absence = leave_with_file(company, ana)

    response = client_for(beto).get(f"/api/absences/{absence.id}/justification/")

    # 404 rather than 403: there is no reason to confirm the absence exists.
    assert response.status_code == 404


@pytest.mark.django_db
def test_a_manager_can(company):
    ana = make(company, "ana@example.com")
    boss = make(company, "boss@example.com", Role.MANAGER)
    absence = leave_with_file(company, ana)

    assert client_for(boss).get(f"/api/absences/{absence.id}/justification/").status_code == 200


@pytest.mark.django_db
def test_another_companys_manager_cannot(company):
    ana = make(company, "ana@example.com")
    absence = leave_with_file(company, ana)

    elsewhere = Tenant.objects.create(name="Otra SL", tax_id="B22222222", time_zone="Europe/Madrid")
    stranger = make(elsewhere, "boss@otra.com", Role.ADMIN)

    response = client_for(stranger).get(f"/api/absences/{absence.id}/justification/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_signing_out_is_enough_to_lose_access(company):
    ana = make(company, "ana@example.com")
    absence = leave_with_file(company, ana)

    assert APIClient().get(f"/api/absences/{absence.id}/justification/").status_code == 401


@pytest.mark.django_db
def test_an_absence_with_no_document_is_a_404(company):
    ana = make(company, "ana@example.com")
    with tenant_context(company.id):
        absence = request_absence(
            employee=ana,
            company=company,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
        )

    assert client_for(ana).get(f"/api/absences/{absence.id}/justification/").status_code == 404


# ------------------------------------------------------------- what leaks where


@pytest.mark.django_db
def test_the_file_path_is_not_in_the_response(company):
    """It used to be. A URL in every list response is a bearer secret handed
    out to whoever can read the list."""
    ana = make(company, "ana@example.com")
    leave_with_file(company, ana)

    body = client_for(ana).get("/api/absences/").json()["results"][0]

    assert body["has_justification"] is True
    assert "justification" not in body
    assert "media" not in str(body)
    assert "citacion.pdf" not in str(body)


@pytest.mark.django_db
@override_settings(STORAGE_BACKEND="s3")
def test_with_object_storage_it_redirects_instead_of_proxying(company):
    """Django does not need to push the bytes when the store can hand out a
    signed URL --- but only after the same permission check."""
    ana = make(company, "ana@example.com")
    beto = make(company, "beto@example.com")
    absence = leave_with_file(company, ana)

    # The check comes first, whatever the backend.
    assert client_for(beto).get(f"/api/absences/{absence.id}/justification/").status_code == 404

    mine = client_for(ana).get(f"/api/absences/{absence.id}/justification/")
    assert mine.status_code == 302
    assert mine.headers["Location"]


@pytest.mark.django_db
def test_with_a_filesystem_it_serves_the_bytes(company):
    ana = make(company, "ana@example.com")
    absence = leave_with_file(company, ana, b"%PDF-1.4 contenido en disco")

    response = client_for(ana).get(f"/api/absences/{absence.id}/justification/")

    assert response.status_code == 200
    assert b"contenido en disco" in b"".join(response.streaming_content)
    assert "attachment" in response.headers.get("Content-Disposition", "")
