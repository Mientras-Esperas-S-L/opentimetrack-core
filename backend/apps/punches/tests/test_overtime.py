"""Validación de horas extra por un responsable.

El registro capta el tiempo real; esto es la capa de encima que dice cuál de
ese tiempo es extra autorizada y cómo se salda. Nunca toca un fichaje.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import OvertimeDecision, Punch, PunchType
from apps.punches.overtime import decide_overtime, pending_overtime
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def people(company):
    with tenant_context(company.id):
        yield {
            "worker": User.objects.create_user(
                email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
            ),
            "boss": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Luisa",
                role=Role.MANAGER,
            ),
            "admin": User.objects.create_user(
                email="dire@example.com",
                password=PASSWORD,
                tenant=company,
                first_name="Ana",
                role=Role.ADMIN,
            ),
        }


def worked_overtime(company, worker, day, extra_hours=2):
    """A rostered 8-hour day, worked longer."""
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company, employee=worker, day=day, segments=[{"start": "09:00", "end": "17:00"}]
        )
        # 09:00 to 17:00+extra, Madrid = 07:00 UTC start.
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.IN,
            timestamp=datetime(day.year, day.month, day.day, 7, 0, tzinfo=UTC),
        )
        Punch.objects.create(
            tenant=company,
            employee=worker,
            punch_type=PunchType.OUT,
            timestamp=datetime(day.year, day.month, day.day, 15 + extra_hours, 0, tzinfo=UTC),
        )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ------------------------------------------------------------------ pendientes


@pytest.mark.django_db
def test_an_overtime_day_appears_pending(company, people):
    worked_overtime(company, people["worker"], date(2026, 9, 1))
    with tenant_context(company.id):
        rows = pending_overtime(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))
    assert len(rows) == 1
    assert rows[0]["minutes"] == 120


@pytest.mark.django_db
def test_a_day_within_the_plan_does_not(company, people):
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=people["worker"],
            day=date(2026, 9, 1),
            segments=[{"start": "09:00", "end": "17:00"}],
        )
        Punch.objects.create(
            tenant=company,
            employee=people["worker"],
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 7, 0, tzinfo=UTC),
        )
        Punch.objects.create(
            tenant=company,
            employee=people["worker"],
            punch_type=PunchType.OUT,
            timestamp=datetime(2026, 9, 1, 15, 0, tzinfo=UTC),
        )
        rows = pending_overtime(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))
    assert rows == []


# -------------------------------------------------------------------- decidir


@pytest.mark.django_db
def test_authorising_records_the_settlement_and_leaves_pending(company, people):
    worked_overtime(company, people["worker"], date(2026, 9, 1))
    with tenant_context(company.id):
        decide_overtime(
            employee=people["worker"],
            company=company,
            day=date(2026, 9, 1),
            decided_by=people["boss"],
            authorise=True,
            settlement="PAID",
        )
        rows = pending_overtime(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))
    assert rows == []
    with tenant_context(company.id):
        d = OvertimeDecision.objects.get()
    assert d.status == "AUTHORISED"
    assert d.settlement == "PAID"


@pytest.mark.django_db
def test_authorising_needs_a_settlement(company, people):
    from apps.common.exceptions import BusinessRuleError

    worked_overtime(company, people["worker"], date(2026, 9, 1))
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        decide_overtime(
            employee=people["worker"],
            company=company,
            day=date(2026, 9, 1),
            decided_by=people["boss"],
            authorise=True,
        )
    assert caught.value.code == "settlement_required"


@pytest.mark.django_db
def test_rejecting_needs_no_settlement(company, people):
    """Extra no autorizada: no hay nada que saldar. El registro sigue mostrando
    el tiempo real; la decisión solo dice que no se autoriza."""
    worked_overtime(company, people["worker"], date(2026, 9, 1))
    with tenant_context(company.id):
        d = decide_overtime(
            employee=people["worker"],
            company=company,
            day=date(2026, 9, 1),
            decided_by=people["boss"],
            authorise=False,
        )
    assert d.status == "REJECTED"
    assert d.settlement == ""


@pytest.mark.django_db
def test_a_decision_does_not_touch_the_punches(company, people):
    worked_overtime(company, people["worker"], date(2026, 9, 1))
    with tenant_context(company.id):
        before = list(Punch.objects.values_list("hash_integrity", flat=True))
        decide_overtime(
            employee=people["worker"],
            company=company,
            day=date(2026, 9, 1),
            decided_by=people["boss"],
            authorise=True,
            settlement="REST",
        )
        after = list(Punch.objects.values_list("hash_integrity", flat=True))
    assert before == after  # los sellos no se movieron


@pytest.mark.django_db
def test_a_changed_figure_reopens_the_day(company, people):
    """Autorizar treinta minutos no puede quedar autorizando dos horas si una
    corrección posterior cambia lo que el día tenía de verdad."""
    with tenant_context(company.id):
        Shift.objects.create(
            tenant=company,
            employee=people["worker"],
            day=date(2026, 9, 1),
            segments=[{"start": "09:00", "end": "17:00"}],
        )
        entry = Punch.objects.create(
            tenant=company,
            employee=people["worker"],
            punch_type=PunchType.IN,
            timestamp=datetime(2026, 9, 1, 7, 0, tzinfo=UTC),
        )
        out = Punch.objects.create(
            tenant=company,
            employee=people["worker"],
            punch_type=PunchType.OUT,
            timestamp=datetime(2026, 9, 1, 15, 30, tzinfo=UTC),  # 30 min extra
        )
        decide_overtime(
            employee=people["worker"],
            company=company,
            day=date(2026, 9, 1),
            decided_by=people["boss"],
            authorise=True,
            settlement="PAID",
        )
        assert (
            pending_overtime(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30)) == []
        )

        # Una corrección hace que fueran dos horas.
        out.timestamp = datetime(2026, 9, 1, 17, 0, tzinfo=UTC)
        out.hash_integrity = ""
        out.save()
        del entry
        rows = pending_overtime(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30))
    assert len(rows) == 1
    assert rows[0]["minutes"] == 120
    assert rows[0]["previous"]["minutes"] == 30  # dice lo que ya se había autorizado


# ------------------------------------------------------------ cuatro ojos


@pytest.mark.django_db
def test_the_sole_admin_may_rule_on_their_own_but_it_is_marked(company):
    """Sin otra persona, se resuelve y se anota que fue en solitario."""
    with tenant_context(company.id):
        admin = User.objects.create_user(
            email="solo@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Sole",
            role=Role.ADMIN,
        )
        worked_overtime(company, admin, date(2026, 9, 1))
        d = decide_overtime(
            employee=admin,
            company=company,
            day=date(2026, 9, 1),
            decided_by=admin,
            authorise=True,
            settlement="PAID",
        )
    assert d.decided_alone is True


@pytest.mark.django_db
def test_a_manager_cannot_rule_on_their_own_when_others_exist(company, people):
    from apps.common.exceptions import BusinessRuleError

    worked_overtime(company, people["boss"], date(2026, 9, 1))
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        decide_overtime(
            employee=people["boss"],
            company=company,
            day=date(2026, 9, 1),
            decided_by=people["boss"],
            authorise=True,
            settlement="PAID",
        )
    assert caught.value.code == "cannot_decide_your_own"


# ------------------------------------------------------------------- la API


@pytest.mark.django_db
def test_an_employee_cannot_reach_the_overtime_queue(company, people):
    worked_overtime(company, people["worker"], date(2026, 9, 1))
    r = client_for(people["worker"]).get("/api/overtime/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_a_manager_lists_and_decides_through_the_api(company, people):
    worked_overtime(company, people["worker"], date(2026, 9, 1))

    listed = (
        client_for(people["admin"])
        .get("/api/overtime/", {"from": "2026-09-01", "to": "2026-09-30"})
        .json()
    )
    assert len(listed["pending"]) == 1

    decided = client_for(people["admin"]).post(
        "/api/overtime/",
        {
            "employee": str(people["worker"].id),
            "day": "2026-09-01",
            "authorise": True,
            "settlement": "REST",
        },
        format="json",
    )
    assert decided.status_code == 200
    assert decided.json()["settlement"] == "REST"


@pytest.mark.django_db
def test_several_days_are_ruled_on_in_one_call(company, people):
    """Quien se queda de más cada tarde llena la cola con la misma decisión.
    Se resuelve de una vez, pero sigue siendo una decisión por día."""
    days = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]
    for day in days:
        worked_overtime(company, people["worker"], day)

    answer = client_for(people["admin"]).post(
        "/api/overtime/",
        {
            "employee": str(people["worker"].id),
            "days": [d.isoformat() for d in days],
            "authorise": True,
            "settlement": "PAID",
        },
        format="json",
    )
    assert answer.status_code == 200
    assert len(answer.json()["decided"]) == 3
    assert answer.json()["failed"] == []

    with tenant_context(company.id):
        assert OvertimeDecision.objects.count() == 3
        assert (
            pending_overtime(company=company, first=date(2026, 9, 1), last=date(2026, 9, 30)) == []
        )


@pytest.mark.django_db
def test_a_day_that_stopped_being_overtime_does_not_sink_the_batch(company, people):
    """La pantalla se dibujó antes; entre medias un día dejó de tener extra. El
    lote sigue, y ese día vuelve nombrado."""
    worked_overtime(company, people["worker"], date(2026, 9, 1))

    answer = client_for(people["admin"]).post(
        "/api/overtime/",
        {
            "employee": str(people["worker"].id),
            "days": ["2026-09-01", "2026-09-02"],  # el 2 no se trabajó
            "authorise": True,
            "settlement": "PAID",
        },
        format="json",
    )
    assert answer.status_code == 200
    body = answer.json()
    assert [d["day"] for d in body["decided"]] == ["2026-09-01"]
    assert body["failed"] == [
        {
            "day": "2026-09-02",
            "code": "no_overtime",
            "message": "That day has no overtime to rule on.",
        }
    ]


@pytest.mark.django_db
def test_one_day_alone_still_answers_with_its_error(company, people):
    """Un día suelto que ya no tiene extra es un error, no un lote a medias."""
    answer = client_for(people["admin"]).post(
        "/api/overtime/",
        {"employee": str(people["worker"].id), "day": "2026-09-01", "authorise": False},
        format="json",
    )
    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "no_overtime"


@pytest.mark.django_db
def test_the_same_day_twice_is_decided_once(company, people):
    worked_overtime(company, people["worker"], date(2026, 9, 1))
    answer = client_for(people["admin"]).post(
        "/api/overtime/",
        {
            "employee": str(people["worker"].id),
            "days": ["2026-09-01", "2026-09-01"],
            "authorise": True,
            "settlement": "REST",
        },
        format="json",
    )
    assert len(answer.json()["decided"]) == 1
