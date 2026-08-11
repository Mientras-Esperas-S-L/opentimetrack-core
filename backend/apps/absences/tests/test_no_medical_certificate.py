"""The medical certificate does not get stored here.

Not a preference: a certificate is health data under art. 9 GDPR, it is not
needed to prove working time, and since RD 1060/2022 the worker does not hand
it to the employer at all --- the INSS sends the data to the company. Asking
for it would mean collecting a special category of data that the law took off
the worker's hands.

Other kinds of leave keep their supporting document. The point is to remove the
health data, not the feature.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction

from apps.absences.models import Absence, AbsenceType
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="rosa@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Rosa",
            last_name="Lima",
        )


def _absence(company, employee, kind, **extra):
    return Absence(
        tenant=company,
        employee=employee,
        absence_type=kind,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 5),
        **extra,
    )


def _a_file():
    return SimpleUploadedFile("parte.pdf", b"%PDF-1.4 fake", content_type="application/pdf")


@pytest.mark.django_db
def test_sick_leave_refuses_a_supporting_document(company, employee):
    absence = _absence(company, employee, AbsenceType.SICK_LEAVE, justification=_a_file())

    with pytest.raises(ValidationError) as caught:
        absence.full_clean()

    assert "justification" in caught.value.message_dict


@pytest.mark.django_db
def test_the_database_refuses_it_too(company, employee):
    """The check that matters. `clean()` is skipped by an import, a shell or a
    serializer nobody validated; the constraint is not."""
    absence = _absence(company, employee, AbsenceType.SICK_LEAVE, justification=_a_file())

    with pytest.raises(IntegrityError), transaction.atomic():
        absence.save()  # straight past clean()


@pytest.mark.django_db
def test_sick_leave_itself_is_recorded_normally(company, employee):
    """What is removed is the document, not the absence: the dates and the
    status are exactly what the working-time record needs."""
    absence = _absence(company, employee, AbsenceType.SICK_LEAVE)
    absence.full_clean()
    absence.save()

    absence.refresh_from_db()
    assert absence.absence_type == AbsenceType.SICK_LEAVE
    assert absence.days == 5
    assert not absence.justification


@pytest.mark.django_db
@pytest.mark.parametrize("kind", [AbsenceType.VACATION, AbsenceType.PERSONAL, AbsenceType.OTHER])
def test_other_kinds_of_leave_keep_their_document(company, employee, kind):
    """A court summons or an exam slip is not health data. The feature stays."""
    absence = _absence(company, employee, kind, justification=_a_file())
    absence.full_clean()
    absence.save()

    absence.refresh_from_db()
    assert absence.justification
