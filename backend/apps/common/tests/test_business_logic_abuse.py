"""Adversarial pass over the rules that protect the record.

The isolation sweep next door asks "can another company reach this". This one
asks a different question: **inside one company, with a legitimate session, what
can somebody make the record say that it should not?**

That is the shape of the risk in a working-time product. Nobody needs to break
in to falsify a register; they need a role that already exists and a path
nobody thought to close. So every test here holds a valid session and tries to
do something the law, or the product's own promises, say it should not.

Written as attacks rather than as features. A test that passes means the attack
was refused; the docstring says what was attempted and why it matters.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def make(company, email, role=Role.EMPLOYEE, **extra):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email,
            password=PASSWORD,
            tenant=company,
            first_name=email.split("@")[0],
            last_name="Prueba",
            role=role,
            **extra,
        )


def client_for(person):
    client = APIClient()
    client.force_authenticate(person)
    return client


@pytest.fixture
def people(company):
    return {
        "admin": make(company, "admin@acme.test", Role.ADMIN),
        "manager": make(company, "jefa@acme.test", Role.MANAGER),
        "worker": make(company, "ana@acme.test"),
        "other": make(company, "luis@acme.test"),
    }


# ==========================================================================
# The clock event itself
# ==========================================================================


@pytest.mark.django_db
def test_the_client_cannot_choose_the_time_of_its_own_punch(people):
    """The whole evidentiary value rests on this. A timestamp the caller can
    set is a timestamp the caller can invent, and the register stops being a
    record of when things happened."""
    before = timezone.now()
    response = client_for(people["worker"]).post(
        "/api/punches/",
        {"timestamp": "2020-01-01T03:00:00Z", "device_id": "tablet-1"},
        format="json",
    )

    assert response.status_code == 201
    saved = Punch.objects_all_tenants.get(pk=response.data["id"])
    assert saved.timestamp >= before  # server time, not the one sent


@pytest.mark.django_db
def test_the_client_cannot_choose_whose_punch_it_is(people):
    """`employee` in the body must not name somebody else. Clocking in for a
    colleague is the most direct way to fake a presence."""
    response = client_for(people["worker"]).post(
        "/api/punches/", {"employee": str(people["other"].id)}, format="json"
    )

    assert response.status_code == 201
    assert str(response.data["employee"]) == str(people["worker"].id)


@pytest.mark.django_db
def test_the_client_cannot_choose_in_or_out(people, company):
    """Otherwise somebody could close a day they never opened, or stack two
    entries to inflate the hours. The type is inferred from what came before."""
    client = client_for(people["worker"])
    first = client.post("/api/punches/", {"punch_type": "OUT"}, format="json")

    assert first.data["punch_type"] == PunchType.IN  # nothing was open


@pytest.mark.django_db
def test_a_punch_cannot_be_edited_through_the_api(people):
    """ADR-0003: the register is append-only. A PATCH that worked would make
    every other guarantee decoration."""
    client = client_for(people["worker"])
    punch = client.post("/api/punches/", {}, format="json").data

    changed = client.patch(
        f"/api/punches/{punch['id']}/", {"timestamp": "2020-01-01T03:00:00Z"}, format="json"
    )
    deleted = client.delete(f"/api/punches/{punch['id']}/")

    assert changed.status_code == 405
    assert deleted.status_code == 405


@pytest.mark.django_db
def test_an_administrator_cannot_edit_one_either(people):
    """The role with the most reach is the one worth checking: a register the
    company can quietly rewrite proves nothing about the company."""
    punch = client_for(people["worker"]).post("/api/punches/", {}, format="json").data

    response = client_for(people["admin"]).patch(
        f"/api/punches/{punch['id']}/", {"timestamp": "2020-01-01T03:00:00Z"}, format="json"
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_tampering_with_a_stored_punch_is_detectable(people, company):
    """The hash is what makes an edit made outside the API --- straight in the
    database --- something a reader can notice."""
    with tenant_context(company.id):
        punch = register_punch(employee=people["worker"], company=company)
        assert punch.verify_hash()

        Punch.objects_all_tenants.filter(pk=punch.pk).update(
            timestamp=punch.timestamp - timedelta(hours=3)
        )
        punch.refresh_from_db()

    assert not punch.verify_hash()


# ==========================================================================
# Corrections: the door through which the record legitimately changes
# ==========================================================================


def ask_correction(client, **extra):
    return client.post(
        "/api/corrections/",
        {
            "kind": "ADD",
            "proposed_type": "OUT",
            "proposed_timestamp": (timezone.now() - timedelta(hours=1)).isoformat(),
            "reason": "Se me olvidó fichar la salida.",
            **extra,
        },
        format="json",
    )


@pytest.mark.django_db
def test_a_worker_cannot_resolve_their_own_correction(people):
    """They ask; somebody else decides. A request that its author can approve
    is not a request, it is an edit with extra steps."""
    client = client_for(people["worker"])
    correction = ask_correction(client).data

    approved = client.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert approved.status_code == 403


@pytest.mark.django_db
def test_a_worker_cannot_ask_for_a_correction_on_somebody_else(people):
    """Naming a colleague in the body. It would put an event in their record
    that they never made and never asked for."""
    response = ask_correction(client_for(people["worker"]), employee=str(people["other"].id))

    assert response.status_code in {400, 403, 409}
    if response.status_code == 201:  # pragma: no cover - kept for the message
        pytest.fail("a worker filed a correction against another person's record")


@pytest.mark.django_db
def test_a_worker_cannot_accept_a_change_proposed_to_somebody_else(people, company):
    """Art. 4.b makes the authorisation personal. Accepting on behalf of a
    colleague is signing for them."""
    from apps.punches.corrections import propose_correction

    with tenant_context(company.id):
        proposal = propose_correction(
            employee=people["other"],
            company=company,
            proposed_by=people["manager"],
            kind="ADD",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
            reason="Olvidó fichar.",
        )

    response = client_for(people["worker"]).post(
        f"/api/corrections/{proposal.pk}/accept/", {}, format="json"
    )

    assert response.status_code in {403, 404, 409}
    proposal.refresh_from_db()
    assert proposal.status == "AWAITING_EMPLOYEE"


@pytest.mark.django_db
def test_a_worker_cannot_impose_a_change_on_their_own_record(people, company):
    """`apply-anyway` is the company's move under art. 4.b. In the worker's
    hands it is a way to write their own hours with no approval at all."""
    from apps.punches.corrections import propose_correction

    with tenant_context(company.id):
        proposal = propose_correction(
            employee=people["worker"],
            company=company,
            proposed_by=people["manager"],
            kind="ADD",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
            reason="Olvidó fichar.",
        )

    response = client_for(people["worker"]).post(
        f"/api/corrections/{proposal.pk}/apply-anyway/", {}, format="json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_correction_cannot_be_applied_twice(people):
    """Approving the same request again would add the hours a second time."""
    correction = ask_correction(client_for(people["worker"])).data
    boss = client_for(people["manager"])

    first = boss.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")
    second = boss.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.django_db
def test_a_rejected_correction_cannot_then_be_approved(people):
    """The refusal is part of the history. Reopening it after the fact would
    let somebody change the answer without a new request."""
    correction = ask_correction(client_for(people["worker"])).data
    boss = client_for(people["manager"])

    boss.post(f"/api/corrections/{correction['id']}/reject/", {"note": "No consta."}, format="json")
    again = boss.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert again.status_code == 409


@pytest.mark.django_db
def test_a_correction_cannot_place_an_event_in_the_future(people):
    """A future clock event is not a record of anything, and it would sit in
    the register as time already worked."""
    response = ask_correction(
        client_for(people["worker"]),
        proposed_timestamp=(timezone.now() + timedelta(days=1)).isoformat(),
    )

    assert response.status_code in {400, 409}


@pytest.mark.django_db
def test_a_manager_cannot_dispute_on_behalf_of_the_worker(people, company):
    """The dissent is the person's own words under art. 4.b. Written by the
    company it is worth nothing --- worse, it looks like the person spoke."""
    from apps.punches.corrections import propose_correction

    with tenant_context(company.id):
        proposal = propose_correction(
            employee=people["worker"],
            company=company,
            proposed_by=people["manager"],
            kind="ADD",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
            reason="Olvidó fichar.",
        )

    response = client_for(people["manager"]).post(
        f"/api/corrections/{proposal.pk}/dispute/",
        {"account": "Dice que salió antes."},
        format="json",
    )

    assert response.status_code in {403, 409}


# ==========================================================================
# Absences
# ==========================================================================


def ask_absence(client, **extra):
    return client.post(
        "/api/absences/",
        {
            "absence_type": AbsenceType.VACATION,
            "start_date": (date.today() + timedelta(days=30)).isoformat(),
            "end_date": (date.today() + timedelta(days=32)).isoformat(),
            "reason": "Vacaciones",
            **extra,
        },
        format="json",
    )


@pytest.mark.django_db
def test_a_worker_cannot_approve_their_own_leave(people):
    absence = ask_absence(client_for(people["worker"])).data

    response = client_for(people["worker"]).post(
        f"/api/absences/{absence['id']}/approve/", {}, format="json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_worker_cannot_file_leave_for_a_colleague(people):
    response = ask_absence(client_for(people["worker"]), employee=str(people["other"].id))

    assert response.status_code in {400, 403, 409}


@pytest.mark.django_db
def test_a_worker_cannot_cancel_a_colleagues_leave(people):
    absence = ask_absence(client_for(people["other"])).data

    response = client_for(people["worker"]).post(
        f"/api/absences/{absence['id']}/cancel/", {}, format="json"
    )

    assert response.status_code in {403, 404}


@pytest.mark.django_db
def test_approved_leave_cannot_be_approved_again(people):
    absence = ask_absence(client_for(people["worker"])).data
    boss = client_for(people["manager"])

    boss.post(f"/api/absences/{absence['id']}/approve/", {}, format="json")
    again = boss.post(f"/api/absences/{absence['id']}/approve/", {}, format="json")

    assert again.status_code == 409


# ==========================================================================
# Roles and reach
# ==========================================================================


@pytest.mark.django_db
def test_a_worker_cannot_promote_themselves(people):
    response = client_for(people["worker"]).patch(
        reverse("employee-detail", args=[people["worker"].pk]), {"role": "ADMIN"}, format="json"
    )

    assert response.status_code == 403
    people["worker"].refresh_from_db()
    assert people["worker"].role == Role.EMPLOYEE


@pytest.mark.django_db
def test_a_manager_cannot_promote_themselves(people):
    """The interesting one: managers reach the people screen, so the guard has
    to be the role and not the screen."""
    response = client_for(people["manager"]).patch(
        reverse("employee-detail", args=[people["manager"].pk]), {"role": "ADMIN"}, format="json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_the_only_administrator_cannot_demote_themselves(people, company):
    """A company with nobody able to administer it cannot be repaired from
    inside: no new people, no decisions, no undo."""
    people["admin"].refresh_from_db()
    with tenant_context(company.id):
        User.objects.filter(role=Role.ADMIN).exclude(pk=people["admin"].pk).delete()

    response = client_for(people["admin"]).patch(
        reverse("employee-detail", args=[people["admin"].pk]),
        {"role": "EMPLOYEE"},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "last_administrator"


@pytest.mark.django_db
def test_an_administrator_cannot_deactivate_themselves(people):
    response = client_for(people["admin"]).delete(
        reverse("employee-detail", args=[people["admin"].pk])
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_a_deactivated_person_cannot_clock_in(people, company):
    """Their session may outlive the deactivation --- the token is valid until it
    expires --- so the refusal has to be at the act, not only at sign-in."""
    person = people["worker"]
    client = client_for(person)
    with tenant_context(company.id):
        person.is_active = False
        person.save(update_fields=["is_active"])

    response = client.post("/api/punches/", {}, format="json")

    assert response.status_code in {401, 403, 409}


# ==========================================================================
# Reading other people
# ==========================================================================


@pytest.mark.django_db
def test_a_worker_cannot_list_a_colleagues_punches(people, company):
    with tenant_context(company.id):
        register_punch(employee=people["other"], company=company)

    body = (
        client_for(people["worker"])
        .get("/api/punches/", {"employee": str(people["other"].id)})
        .json()
    )

    assert body["count"] == 0


@pytest.mark.django_db
def test_a_worker_cannot_read_a_colleagues_punch_by_id(people, company):
    with tenant_context(company.id):
        theirs = register_punch(employee=people["other"], company=company)

    response = client_for(people["worker"]).get(f"/api/punches/{theirs.pk}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_worker_cannot_export_a_colleagues_report(people):
    """The report is the whole record of a person in a period. It is the single
    most valuable thing to pull, and the least noisy."""
    response = client_for(people["worker"]).get(
        "/api/reports/working-time/",
        {
            "employee": str(people["other"].id),
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "format": "json",
        },
    )

    assert response.status_code in {400, 403, 404}


@pytest.mark.django_db
def test_a_worker_cannot_read_the_whole_companys_trail(people, company):
    """The trail names who did what. For somebody without a role it is a map of
    the organisation and of everybody's movements."""
    with tenant_context(company.id):
        register_punch(employee=people["other"], company=company)
    client_for(people["manager"]).get("/api/punches/", {"employee": str(people["other"].id)})

    body = client_for(people["worker"]).get("/api/audit/").json()

    concerning_others = [
        row
        for row in body["results"]
        if row.get("target_id") not in {None, str(people["worker"].id)}
        and row.get("actor") not in {None, str(people["worker"].id)}
    ]
    assert concerning_others == []


@pytest.mark.django_db
def test_the_trail_cannot_be_written_through_the_api(people):
    """ADR-0003. An audit trail somebody can add to is not evidence of
    anything."""
    client = client_for(people["admin"])

    posted = client.post("/api/audit/", {"action": "PERSON_CREATED"}, format="json")

    assert posted.status_code == 405


@pytest.mark.django_db
def test_reading_a_colleagues_record_leaves_a_trace(
    people, company, django_capture_on_commit_callbacks
):
    """The gap the trail exists to close. A manager may read; what they may not
    do is read without it being knowable."""
    from apps.audit.models import AuditAction, AuditLog

    with tenant_context(company.id):
        register_punch(employee=people["worker"], company=company)

    # Entries are written on commit, which in a transactional test never
    # arrives on its own.
    with django_capture_on_commit_callbacks(execute=True):
        client_for(people["manager"]).get("/api/punches/", {"employee": str(people["worker"].id)})

    with tenant_context(company.id):
        seen = AuditLog.objects.filter(
            action=AuditAction.RECORD_VIEWED, target_id=people["worker"].id
        )
        assert seen.exists()


@pytest.mark.django_db
def test_reading_your_own_record_does_not(people, company, django_capture_on_commit_callbacks):
    """Otherwise the trail fills with people exercising a right and the pointed
    lookups get buried."""
    from apps.audit.models import AuditAction, AuditLog

    with tenant_context(company.id):
        register_punch(employee=people["worker"], company=company)

    with django_capture_on_commit_callbacks(execute=True):
        client_for(people["worker"]).get("/api/punches/", {"employee": str(people["worker"].id)})

    with tenant_context(company.id):
        assert not AuditLog.objects.filter(action=AuditAction.RECORD_VIEWED).exists()


# ==========================================================================
# Nothing at all
# ==========================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method,url",
    [
        ("get", "/api/punches/"),
        ("post", "/api/punches/"),
        ("get", "/api/employees/"),
        ("get", "/api/absences/"),
        ("get", "/api/audit/"),
        ("get", "/api/company/"),
        ("get", "/api/overview/"),
        ("get", "/api/working-time-rules/"),
        ("get", "/api/shifts/roster/"),
        ("get", "/api/reports/working-time/"),
        ("get", "/api/reports/payroll-summary/"),
        ("get", "/api/corrections/"),
        ("get", "/api/departments/"),
        ("get", "/api/shift-patterns/"),
    ],
)
def test_no_endpoint_answers_without_a_session(method, url, people):
    """The blunt check. One view with the wrong permission class is all it
    takes, and it is the kind of thing that arrives with a refactor."""
    response = getattr(APIClient(), method)(url)

    assert response.status_code in {401, 403}, (
        f"{method.upper()} {url} answered {response.status_code}"
    )


@pytest.mark.django_db
def test_an_absence_of_another_company_is_not_found_by_id(company, people):
    """Belt and braces over the sweep: the id is a UUID, but guessing is not
    the only way to come by one."""
    other = Tenant.objects.create(name="Globex", tax_id="B22222222")
    theirs = make(other, "suya@globex.test")
    with tenant_context(other.id):
        absence = Absence.objects.create(
            tenant=other,
            employee=theirs,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            status=AbsenceStatus.PENDING,
        )

    response = client_for(people["admin"]).get(f"/api/absences/{absence.pk}/")

    assert response.status_code == 404


# ==========================================================================
# Deciding on your own case
# ==========================================================================
#
# The two above are about somebody reaching a role they should not have. These
# are about somebody using the role they legitimately do have, on themselves.


@pytest.mark.django_db
def test_a_manager_cannot_approve_a_change_to_their_own_record(people):
    """The one that matters most. A manager who can approve their own
    correction can write their own hours: file it, approve it, done, with no
    second pair of eyes anywhere in the path.

    Nothing about the role makes this necessary --- there is always an
    administrator, and in a company with a single person there is nothing to
    falsify against."""
    boss = client_for(people["manager"])
    correction = ask_correction(boss).data

    response = boss.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert response.status_code == 409, "a manager approved a change to their own working time"
    assert response.data["error"]["code"] == "cannot_decide_your_own"


@pytest.mark.django_db
def test_an_administrator_cannot_either(people):
    """Same reasoning, and the role with the most reach. If the register can be
    rewritten by one person acting alone, its value as evidence rests on
    trusting that person --- which is what a register is for not having to do."""
    admin = client_for(people["admin"])
    correction = ask_correction(admin).data

    response = admin.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert response.status_code == 409


@pytest.mark.django_db
def test_a_manager_cannot_approve_their_own_leave(people):
    """Less grave than the hours --- leave is the company's to grant --- but it is
    the same principle and an auditor asks the same question."""
    boss = client_for(people["manager"])
    absence = ask_absence(boss).data

    response = boss.post(f"/api/absences/{absence['id']}/approve/", {}, format="json")

    assert response.status_code == 409


@pytest.mark.django_db
def test_the_only_administrator_may_still_resolve_their_own(company):
    """The exception that has to keep working. A self-employed person, or a
    two-person business where only one administers, would otherwise be unable
    to correct their own record at all --- unable to use the product."""
    alone = make(company, "sola@acme.test", Role.ADMIN)
    client = client_for(alone)
    correction = ask_correction(client).data

    response = client.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert response.status_code == 200


@pytest.mark.django_db
def test_and_the_record_says_it_was_resolved_alone(company):
    """Allowed is not the same as unremarkable. A change a second person
    approved and one the same person filed and resolved are different evidence,
    and the register has to keep them apart --- that being the whole point of
    the procedure."""
    alone = make(company, "sola@acme.test", Role.ADMIN)
    client = client_for(alone)
    correction = ask_correction(client).data

    body = client.post(
        f"/api/corrections/{correction['id']}/approve/",
        {"note": "Corrijo mi salida."},
        format="json",
    ).json()

    assert "Corrijo mi salida." in body["resolution_note"]
    assert "no other manager or administrator" in body["resolution_note"].lower() or (
        "ningún otro" in body["resolution_note"].lower()
    )


@pytest.mark.django_db
def test_a_second_administrator_closes_the_exception(company):
    """The moment somebody else exists, the door shuts. Nothing to configure:
    the rule follows the company's own shape."""
    alone = make(company, "sola@acme.test", Role.ADMIN)
    client = client_for(alone)
    correction = ask_correction(client).data
    make(company, "segunda@acme.test", Role.ADMIN)

    response = client.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert response.status_code == 409


@pytest.mark.django_db
def test_a_manager_may_still_resolve_a_colleagues(people):
    """The fix must not turn into "managers cannot approve anything"."""
    correction = ask_correction(client_for(people["worker"])).data

    response = client_for(people["manager"]).post(
        f"/api/corrections/{correction['id']}/approve/", {}, format="json"
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_lone_administrator_of_another_company_is_not_a_second_pair_of_eyes(company):
    """The subtle way this check could have been wrong: `User.objects` spans
    every company, because sign-in has to find people before the company is
    known. Without the tenant filter, somebody else's manager would count."""
    alone = make(company, "sola@acme.test", Role.ADMIN)
    other = Tenant.objects.create(name="Globex", tax_id="B22222222")
    make(other, "ajena@globex.test", Role.ADMIN)

    client = client_for(alone)
    correction = ask_correction(client).data
    response = client.post(f"/api/corrections/{correction['id']}/approve/", {}, format="json")

    assert response.status_code == 200, "another company's administrator counted as a second person"


@pytest.mark.django_db
def test_a_manager_cannot_route_around_it_by_proposing_on_themselves(people, company):
    """The other door. `propose_correction` is the company acting on somebody
    else's record, and it lands in AWAITING_EMPLOYEE waiting for that person to
    authorise it. Aimed at yourself, you are both parties: propose, accept,
    applied --- and the four-eyes check on `approve` never runs, because this
    path does not go through it."""
    from apps.punches.corrections import accept_correction, propose_correction

    with tenant_context(company.id):
        mine = propose_correction(
            employee=people["manager"],
            company=company,
            proposed_by=people["manager"],
            kind="ADD",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=1),
            reason="Me olvidé de fichar.",
        )

    from apps.common.exceptions import BusinessRuleError

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        accept_correction(mine, employee=people["manager"])

    # The exact code, not "something raised": a refusal for a different reason
    # would leave this door open and the test green.
    assert caught.value.code == "cannot_decide_your_own"
    mine.refresh_from_db()
    assert mine.status == "AWAITING_EMPLOYEE"
    assert mine.result is None
