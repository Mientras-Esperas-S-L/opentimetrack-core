"""The six fields the domain reads and nothing could write.

`date_of_birth`, `part_time`, `part_time_percentage`, `contracted_schedule`,
`default_work_mode` and `is_worker_representative` were on the model, read by
the roster review, by `register_punch`, by the inspection report and by the
art. 4.b notice --- and absent from every serializer. There was no way to fill
them in, by API or by screen.

What that meant in practice, and what these tests are really about:

* no under-eighteen protection ever applied, because `age_is_known` was always
  false;
* art. 12.4.c never refused overtime on a part-time contract;
* the report's art. 3.b content came out empty;
* and the art. 4.b notice never found anybody to inform.

So the tests do not stop at "the field saves". Each one goes on to check the
thing that field switches on.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone, translation
from rest_framework.test import APIClient

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import HoursNature, OvertimeSettlement
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
            email=email, password=PASSWORD, tenant=company, first_name="Ana", role=role, **extra
        )


@pytest.fixture
def as_admin(company):
    client = APIClient()
    client.force_authenticate(make(company, "admin@example.com", Role.ADMIN))
    return client


def patch(client, person, **fields):
    return client.patch(reverse("employee-detail", args=[person.pk]), fields, format="json")


# --------------------------------------------------- date of birth, and minors


@pytest.mark.django_db
def test_a_date_of_birth_can_be_set_and_read_back(as_admin, company):
    person = make(company, "joven@example.com")

    response = patch(as_admin, person, date_of_birth="2009-06-15")

    assert response.status_code == 200
    assert response.data["date_of_birth"] == "2009-06-15"


@pytest.mark.django_db
def test_setting_it_is_what_turns_the_protections_on(as_admin, company):
    """The point of the field. Before this the age was never known, so no
    under-eighteen rule could fire for anybody, ever."""
    person = make(company, "joven@example.com")
    assert not person.age_is_known

    patch(
        as_admin,
        person,
        date_of_birth=(timezone.localdate() - timedelta(days=365 * 17)).isoformat(),
    )
    person.refresh_from_db()

    assert person.age_is_known
    assert person.is_minor_on(timezone.localdate())


@pytest.mark.django_db
def test_a_minor_with_a_recorded_birthday_cannot_be_given_overtime(as_admin, company):
    """End to end: fill the field through the API, then check art. 6.3 bites."""
    person = make(company, "joven@example.com")
    patch(
        as_admin,
        person,
        date_of_birth=(timezone.localdate() - timedelta(days=365 * 17)).isoformat(),
    )
    person.refresh_from_db()

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        register_punch(
            employee=person,
            company=company,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
        )

    assert caught.value.code == "overtime_forbidden_for_minors"


@pytest.mark.django_db
def test_a_future_date_of_birth_is_refused(as_admin, company):
    person = make(company, "joven@example.com")

    response = patch(
        as_admin, person, date_of_birth=(timezone.localdate() + timedelta(days=1)).isoformat()
    )

    assert response.status_code == 400
    person.refresh_from_db()
    assert person.date_of_birth is None


@pytest.mark.django_db
def test_an_age_below_sixteen_is_refused(as_admin, company):
    """Art. 6.1 ET does not allow work below sixteen, so it is a typo --- and a
    typo here silently decides whether the protections apply."""
    person = make(company, "joven@example.com")

    response = patch(
        as_admin,
        person,
        date_of_birth=(timezone.localdate() - timedelta(days=365 * 12)).isoformat(),
    )

    assert response.status_code == 400
    assert "part_time" not in str(response.data)  # the error is about the date


@pytest.mark.django_db
def test_an_absurd_age_is_refused(as_admin, company):
    person = make(company, "joven@example.com")

    response = patch(as_admin, person, date_of_birth="1890-01-01")

    assert response.status_code == 400


@pytest.mark.django_db
def test_it_can_be_cleared(as_admin, company):
    """A wrong one has to be removable, and clearing it means "we do not know"
    rather than "adult"."""
    person = make(company, "joven@example.com", date_of_birth=date(2009, 6, 15))

    response = patch(as_admin, person, date_of_birth=None)

    assert response.status_code == 200
    person.refresh_from_db()
    assert person.date_of_birth is None
    assert not person.age_is_known


# --------------------------------------------------- the working-time regime
#
# Not a list of contract types. What the product needs to know is which limits
# apply and what hours beyond the agreed ones are called --- and within one
# company there will be people on forty hours, on twenty-five, on a reduced
# day, and with no agreed figure at all.


@pytest.mark.django_db
def test_a_part_time_contract_needs_its_hours(as_admin, company):
    """Art. 3.b asks for the agreed figure. Without it there is nothing to
    measure against, and the roster would fall back to the company's forty."""
    person = make(company, "parcial@example.com")

    response = patch(as_admin, person, regime="PART_TIME")

    assert response.status_code == 400
    assert "contracted_hours" in response.data["error"]["details"]


@pytest.mark.django_db
def test_hours_on_a_contract_with_no_agreed_figure_are_refused(as_admin, company):
    """The leftover somebody forgot to clear when the terms changed."""
    person = make(company, "suelto@example.com")

    response = patch(as_admin, person, regime="VARIABLE", contracted_hours="20")

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_week_longer_than_the_company_week_is_refused(as_admin, company):
    """Art. 34.1 ET is a ceiling: no contract may agree past it. Forty-five
    here is either a typo or a contract that does not hold."""
    person = make(company, "larga@example.com")

    response = patch(as_admin, person, regime="FULL_TIME", contracted_hours="45")

    assert response.status_code == 400


@pytest.mark.django_db
def test_twenty_five_hours_a_week_is_accepted_and_its_share_worked_out(as_admin, company):
    """The percentage art. 3.b asks for is derived, not typed. Two fields
    saying the same thing end up disagreeing."""
    from apps.tenants.rules import WorkingTimeRules

    person = make(company, "parcial@example.com")

    response = patch(as_admin, person, regime="PART_TIME", contracted_hours="25")

    assert response.status_code == 200
    person.refresh_from_db()
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
    assert person.agreed_hours(rules) == (25.0, "WEEK")
    assert person.share_of_full_time(rules) == 62.5


@pytest.mark.django_db
def test_an_annual_figure_is_kept_as_annual(as_admin, company):
    """The state gardening agreement sets 1700 hours a year and no weekly
    figure. Dividing by 52 would invent a number nobody agreed to."""
    from apps.tenants.rules import WorkingTimeRules

    person = make(company, "anual@example.com")

    response = patch(
        as_admin, person, regime="FULL_TIME", contracted_hours="1700", contracted_period="YEAR"
    )

    assert response.status_code == 200
    person.refresh_from_db()
    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
    assert person.agreed_hours(rules) == (1700.0, "YEAR")
    # No weekly share: the two are not the same period, and pretending they are
    # is the mistake this guards against.
    assert person.share_of_full_time(rules) is None


@pytest.mark.django_db
def test_a_reduced_day_is_not_part_time(as_admin, company):
    """The distinction that costs money if it is wrong. A reduction under
    art. 37.6 is a full-time contract worked less, so the overtime ban of
    art. 12.4.c does not reach it. Filing both as "part time" would deny
    overtime to people entitled to it."""
    from apps.punches.models import HoursNature, OvertimeSettlement
    from apps.punches.services import register_punch

    person = make(company, "reducida@example.com")
    patch(as_admin, person, regime="REDUCED", contracted_hours="30")
    person.refresh_from_db()

    assert not person.part_time

    with tenant_context(company.id):
        event = register_punch(
            employee=person,
            company=company,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
        )

    assert event.pk is not None


@pytest.mark.django_db
def test_part_time_is_what_refuses_the_overtime(as_admin, company):
    """Art. 12.4.c, and the other side of the test above."""
    person = make(company, "parcial@example.com")
    patch(as_admin, person, regime="PART_TIME", contracted_hours="25")
    person.refresh_from_db()

    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        register_punch(
            employee=person,
            company=company,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
        )

    assert caught.value.code == "overtime_not_available_part_time"


@pytest.mark.django_db
def test_a_full_time_contract_with_nothing_written_uses_the_company_week(as_admin, company):
    """Full time *is* the ordinary week. Asking every full-timer to retype it
    invites a typo in the one value already known."""
    from apps.tenants.rules import WorkingTimeRules

    person = make(company, "completa@example.com")

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)

    assert person.agreed_hours(rules) == (40.0, "WEEK")


@pytest.mark.django_db
def test_no_agreed_figure_means_none(as_admin, company):
    """And the caller has to handle it rather than get a zero, which would read
    as "contracted for nothing"."""
    from apps.tenants.rules import WorkingTimeRules

    person = make(company, "suelto@example.com")
    patch(as_admin, person, regime="VARIABLE")
    person.refresh_from_db()

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)

    assert person.agreed_hours(rules) is None
    assert not person.has_agreed_hours


# ------------------------------------------- what reaches the inspection report


@pytest.mark.django_db
def test_the_agreed_hours_reach_the_report(as_admin, company):
    """Art. 3.b names it as minimum content of the record. It came out empty
    because there was no way to fill it in."""
    from apps.reports.services import build_report

    person = make(company, "ana@example.com")
    patch(as_admin, person, contracted_schedule="L-V 09:00-17:00", regime="FULL_TIME")
    person.refresh_from_db()  # build_report reads the object, not the row

    # In English so the assertion tests that the field reaches the report, not
    # which catalogue happens to be compiled. The report does render the label
    # translated, which is what an inspection in Spain should see.
    with tenant_context(company.id), translation.override("en"):
        data = build_report(
            employee=person,
            company=company,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
        )

    assert data.contracted_schedule == "L-V 09:00-17:00"
    assert data.regime == "Full time"


@pytest.mark.django_db
def test_the_usual_mode_is_what_a_punch_assumes(as_admin, company):
    """Art. 3.e. A clock event that says nothing takes it from here."""
    person = make(company, "remota@example.com")
    patch(as_admin, person, default_work_mode="REMOTE")
    person.refresh_from_db()

    with tenant_context(company.id):
        event = register_punch(employee=person, company=company)

    assert event.work_mode == "REMOTE"


# ------------------------------------------------------- the representatives


@pytest.mark.django_db
def test_somebody_can_be_marked_as_a_representative(as_admin, company):
    person = make(company, "delegada@example.com")

    response = patch(as_admin, person, is_worker_representative=True)

    assert response.status_code == 200
    person.refresh_from_db()
    assert person.is_worker_representative


@pytest.mark.django_db
def test_marking_one_is_what_makes_the_article_4b_notice_reach_anybody(as_admin, company):
    """The whole point. `_inform_representatives` looks for people with the
    flag; with nobody marked it recorded that the obligation had gone unmet,
    truthfully and forever."""
    from apps.punches.corrections import dispute_correction, propose_correction

    worker = make(company, "trabajadora@example.com")
    boss = make(company, "jefa@example.com", Role.MANAGER)

    with tenant_context(company.id):
        nobody = propose_correction(
            employee=worker,
            company=company,
            proposed_by=boss,
            kind="ADD",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=2),
            reason="Se olvidó fichar la salida.",
        )
        dispute_correction(nobody, employee=worker, account="Salí más tarde.")
    nobody.refresh_from_db()
    assert "No consta" in nobody.representatives_notice

    delegate = make(company, "delegada@example.com")
    patch(as_admin, delegate, is_worker_representative=True)

    with tenant_context(company.id):
        again = propose_correction(
            employee=worker,
            company=company,
            proposed_by=boss,
            kind="ADD",
            proposed_type="OUT",
            proposed_timestamp=timezone.now() - timedelta(hours=3),
            reason="Otra salida sin fichar.",
        )
        dispute_correction(again, employee=worker, account="Tampoco fue así.")
    again.refresh_from_db()

    assert "No consta" not in again.representatives_notice
    assert delegate.get_full_name() in again.representatives_notice


@pytest.mark.django_db
def test_a_manager_cannot_write_any_of_them(company):
    """These decide who is protected and who gets informed. Same door as every
    other write on a person: administrators only."""
    manager = make(company, "jefa@example.com", Role.MANAGER)
    person = make(company, "ana@example.com")
    client = APIClient()
    client.force_authenticate(manager)

    response = patch(client, person, is_worker_representative=True)

    assert response.status_code == 403
    person.refresh_from_db()
    assert not person.is_worker_representative
