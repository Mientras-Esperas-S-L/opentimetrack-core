"""Getting a new person into the product.

The account used to be created and nothing else happened: no message, no link,
no way in. The only people who could sign in were the ones seeded into the
database. Creating somebody and inviting them are the same act from the
administrator's side, so the invitation is not a second button they have to
remember.

The link itself is tested in `test_passwords`; what is checked here is that one
gets sent, that it is not sent where it would be useless, and that sending it
is an administrator's job --- it hands somebody a way into the company's records.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


def make(company, email, role=Role.ADMIN, **extra):
    return User.objects.create_user(
        email=email, password=PASSWORD, tenant=company, first_name=email[:3], role=role, **extra
    )


@pytest.fixture
def admin(company):
    return make(company, "admin@example.com")


@pytest.fixture
def as_admin(admin):
    client = APIClient()
    client.force_authenticate(admin)
    return client


def create_person(client, **extra):
    return client.post(
        reverse("employee-list"),
        {
            "email": "nuevo@example.com",
            "first_name": "Nuevo",
            "last_name": "Operario",
            "role": Role.EMPLOYEE,
            **extra,
        },
        format="json",
    )


# ------------------------------------------------------------- on being created


@pytest.mark.django_db
def test_creating_somebody_sends_them_the_link(as_admin, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = create_person(as_admin)

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["nuevo@example.com"]
    assert "/set-password/" in mail.outbox[0].body


@pytest.mark.django_db
def test_the_message_reads_as_an_invitation_not_a_recovery(
    as_admin, django_capture_on_commit_callbacks
):
    """Same link, different message. Somebody who never had an account being
    told to "reset your password" has nothing to reset."""
    with django_capture_on_commit_callbacks(execute=True):
        create_person(as_admin)

    assert "ACME Ltd" in mail.outbox[0].subject
    assert "restablecer" not in mail.outbox[0].subject.lower()


@pytest.mark.django_db
def test_a_password_in_the_payload_means_no_link(as_admin, django_capture_on_commit_callbacks):
    """Somebody is setting it deliberately --- a migration, a test account --- and
    a link on top would only muddle which one applies."""
    with django_capture_on_commit_callbacks(execute=True):
        response = create_person(as_admin, password=PASSWORD)

    assert response.status_code == 201
    assert mail.outbox == []


@pytest.mark.django_db
def test_the_invitation_is_recorded(as_admin, django_capture_on_commit_callbacks, company):
    """It is a change to who can reach the company's records, so it belongs in
    the trail next to the role changes and not in a log file."""
    with django_capture_on_commit_callbacks(execute=True):
        create_person(as_admin)

    trail = AuditLog.objects.filter(tenant=company, action=AuditAction.INVITATION_SENT)
    assert trail.count() == 1
    assert trail.first().target_label == "Nuevo Operario"


# ------------------------------------------------------------------ sending again


@pytest.mark.django_db
def test_the_link_can_be_sent_again(as_admin, company, django_capture_on_commit_callbacks):
    """Links expire, mail goes astray, and every account created before any of
    this existed never got one."""
    person = make(company, "vieja@example.com", role=Role.EMPLOYEE)

    with django_capture_on_commit_callbacks(execute=True):
        response = as_admin.post(reverse("employee-invite", args=[person.pk]))

    assert response.status_code == 200
    assert response.data["sent_to"] == "vieja@example.com"
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_a_manager_cannot_send_it(company):
    """Managers read this page; they do not hand out access to it."""
    manager = make(company, "jefa@example.com", role=Role.MANAGER)
    person = make(company, "otra@example.com", role=Role.EMPLOYEE)
    client = APIClient()
    client.force_authenticate(manager)

    response = client.post(reverse("employee-invite", args=[person.pk]))

    assert response.status_code == 403
    assert mail.outbox == []


@pytest.mark.django_db
def test_another_company_cannot_send_it(as_admin):
    """The most direct way this could leak: an id from somewhere else. It has to
    be a 404, because a 403 would confirm the account exists."""
    other = Tenant.objects.create(name="Globex Inc", tax_id="B22222222")
    theirs = make(other, "suya@example.com", role=Role.EMPLOYEE)

    response = as_admin.post(reverse("employee-invite", args=[theirs.pk]))

    assert response.status_code == 404
    assert mail.outbox == []


@pytest.mark.django_db
def test_nothing_is_sent_to_somebody_deactivated(as_admin, company):
    """They cannot sign in, so the link would be a dead end. Saying so beats a
    message that quietly does nothing."""
    person = make(company, "baja@example.com", role=Role.EMPLOYEE, is_active=False)

    response = as_admin.post(reverse("employee-invite", args=[person.pk]))

    assert response.status_code == 409
    assert response.data["error"]["code"] == "cannot_invite"
    assert mail.outbox == []


@pytest.mark.django_db
def test_nothing_is_sent_to_a_federated_account(as_admin, company):
    """Their credentials belong to the identity provider. A password set from
    here could never be used to sign in."""
    person = make(company, "sso@example.com", role=Role.EMPLOYEE, oidc_sub="okta|abc123")

    response = as_admin.post(reverse("employee-invite", args=[person.pk]))

    assert response.status_code == 409
    assert mail.outbox == []


# ------------------------------------------------------------------ coming back


@pytest.mark.django_db
def test_reactivating_somebody_is_its_own_entry(
    as_admin, company, django_capture_on_commit_callbacks
):
    """Not an ordinary edit. It is the reverse of a deactivation and should sit
    next to it when somebody reads the history of an account."""
    person = make(company, "vuelve@example.com", role=Role.EMPLOYEE, is_active=False)

    with django_capture_on_commit_callbacks(execute=True):
        response = as_admin.patch(
            reverse("employee-detail", args=[person.pk]), {"is_active": True}, format="json"
        )

    assert response.status_code == 200
    person.refresh_from_db()
    assert person.is_active

    actions = list(
        AuditLog.objects.filter(tenant=company, target_id=person.pk).values_list(
            "action", flat=True
        )
    )
    assert AuditAction.PERSON_REACTIVATED in actions
    assert AuditAction.PERSON_UPDATED not in actions


@pytest.mark.django_db
def test_an_ordinary_edit_is_still_an_ordinary_edit(
    as_admin, company, django_capture_on_commit_callbacks
):
    """The guard above must not swallow every update. Somebody active stays on
    the PERSON_UPDATED path."""
    person = make(company, "activa@example.com", role=Role.EMPLOYEE)

    with django_capture_on_commit_callbacks(execute=True):
        as_admin.patch(
            reverse("employee-detail", args=[person.pk]), {"first_name": "Otra"}, format="json"
        )

    actions = list(
        AuditLog.objects.filter(tenant=company, target_id=person.pk).values_list(
            "action", flat=True
        )
    )
    assert actions == [AuditAction.PERSON_UPDATED]
