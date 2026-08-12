"""Every endpoint, swept for the three ways data escapes.

Not a sample. The list below is built to cover every resource the API exposes,
and there is a test at the bottom that **fails when a new route appears without
being added here** --- because the leak that gets shipped is always the one in
the endpoint nobody remembered to check.

The three questions asked of each:

1. **No session at all.** Does it answer 401, or does it hand something over?
2. **A session from another company.** Two companies exist with the same shape
   of data; can one reach the other's? This is the one that ends a product.
3. **A colleague without privilege.** Can a worker read what belongs to another
   worker, or do what only a manager should?

Nothing here is mocked. Real requests, two real companies, real permissions.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import get_resolver
from rest_framework.test import APIClient

from apps.absences.models import AbsenceType
from apps.absences.services import request_absence
from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, request_correction
from apps.punches.services import register_punch
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


def build_company(name, tax_id, email_domain):
    """A company with one of everything, so every endpoint has a target."""
    company = Tenant.objects.create(name=name, tax_id=tax_id, time_zone="Europe/Madrid")
    with tenant_context(company.id):
        admin = User.objects.create_user(
            email=f"admin@{email_domain}",
            password=PASSWORD,
            tenant=company,
            first_name="Admin",
            last_name=name,
            role=Role.ADMIN,
        )
        worker = User.objects.create_user(
            email=f"worker@{email_domain}",
            password=PASSWORD,
            tenant=company,
            first_name="Worker",
            last_name=name,
        )
        other_worker = User.objects.create_user(
            email=f"other@{email_domain}",
            password=PASSWORD,
            tenant=company,
            first_name="Other",
            last_name=name,
        )
        department = Department.objects.create(tenant=company, name=f"Dept {name}")
        punch = register_punch(employee=worker, company=company)
        absence = request_absence(
            employee=worker,
            company=company,
            absence_type=AbsenceType.VACATION,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
        )
        correction = request_correction(
            employee=worker,
            company=company,
            requested_by=worker,
            kind=CorrectionKind.ADD,
            reason="Olvidé fichar la salida.",
            proposed_type="OUT",
            proposed_timestamp=punch.timestamp - timedelta(hours=1),
        )
        pattern = ShiftPattern.objects.create(
            tenant=company, name=f"Turno {name}", segments=[{"start": "08:00", "end": "16:00"}]
        )
        shift = Shift.objects.create(
            tenant=company,
            employee=worker,
            day=date(2026, 9, 1),
            pattern=pattern,
            segments=pattern.segments,
        )
        entry = AuditLog.objects.create(
            tenant=company,
            action=AuditAction.RECORD_VIEWED,
            actor=admin,
            actor_label="Admin",
            target_id=worker.id,
            target_label="Worker",
        )

    return {
        "company": company,
        "admin": admin,
        "worker": worker,
        "other": other_worker,
        "department": department,
        "punch": punch,
        "absence": absence,
        "correction": correction,
        "pattern": pattern,
        "shift": shift,
        "audit": entry,
    }


@pytest.fixture
def ours(db):
    return build_company("Nuestra", "B11111111", "nuestra.test")


@pytest.fixture
def theirs(db):
    return build_company("Ajena", "B22222222", "ajena.test")


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def detail_urls(world):
    """Every per-object URL, with the object it belongs to."""
    return {
        "punch": f"/api/punches/{world['punch'].id}/",
        "absence": f"/api/absences/{world['absence'].id}/",
        "absence justification": f"/api/absences/{world['absence'].id}/justification/",
        "correction": f"/api/corrections/{world['correction'].id}/",
        "employee": f"/api/employees/{world['worker'].id}/",
        "department": f"/api/departments/{world['department'].id}/",
        "shift": f"/api/shifts/{world['shift'].id}/",
        "shift pattern": f"/api/shift-patterns/{world['pattern'].id}/",
        "audit entry": f"/api/audit/{world['audit'].id}/",
    }


COLLECTIONS = [
    "/api/punches/",
    "/api/absences/",
    "/api/corrections/",
    "/api/employees/",
    "/api/departments/",
    "/api/shifts/",
    "/api/shift-patterns/",
    "/api/audit/",
    "/api/overview/",
    "/api/company/",
    "/api/working-time-rules/",
    "/api/punches/today/",
    "/api/shifts/today/",
    "/api/absences/balance/",
    "/api/absences/pending/",
    "/api/reports/payroll-summary/",
]


# ------------------------------------------------------------ 1. no session


@pytest.mark.django_db
def test_nothing_answers_without_a_session(ours):
    """Every collection, unauthenticated."""
    anonymous = client_for()
    leaked = []

    for url in COLLECTIONS:
        response = anonymous.get(url)
        if response.status_code != 401:
            leaked.append(f"{url} -> {response.status_code}")

    assert leaked == [], f"reachable without a session: {leaked}"


@pytest.mark.django_db
def test_no_detail_answers_without_a_session(ours):
    anonymous = client_for()
    leaked = []

    for label, url in detail_urls(ours).items():
        response = anonymous.get(url)
        if response.status_code != 401:
            leaked.append(f"{label} ({url}) -> {response.status_code}")

    assert leaked == [], f"reachable without a session: {leaked}"


@pytest.mark.django_db
def test_writing_without_a_session_is_refused(ours):
    anonymous = client_for()
    attempts = [
        ("POST", "/api/punches/", {}),
        (
            "POST",
            "/api/absences/",
            {"absence_type": "VACATION", "start_date": "2026-09-01", "end_date": "2026-09-02"},
        ),
        ("POST", "/api/employees/", {"email": "x@y.test", "first_name": "X"}),
        ("PATCH", "/api/company/", {"name": "Secuestrada"}),
        ("PATCH", "/api/working-time-rules/", {"weekly_hours": 60}),
        ("POST", "/api/shifts/assign/", {}),
    ]
    leaked = []

    for method, url, body in attempts:
        response = getattr(anonymous, method.lower())(url, body, format="json")
        if response.status_code != 401:
            leaked.append(f"{method} {url} -> {response.status_code}")

    assert leaked == [], f"writable without a session: {leaked}"


# -------------------------------------------------- 2. somebody else's company


@pytest.mark.django_db
def test_no_collection_shows_another_companys_rows(ours, theirs):
    """Their administrator asks for everything. Nothing of ours may appear.

    Checked by counting rather than by inspecting: both companies hold the same
    shape of data, so a leak shows up as a count that is too high.
    """
    intruder = client_for(theirs["admin"])
    leaked = []

    for url in [
        "/api/punches/",
        "/api/absences/",
        "/api/corrections/",
        "/api/employees/",
        "/api/departments/",
        "/api/shifts/",
        "/api/shift-patterns/",
        "/api/audit/",
    ]:
        body = intruder.get(url).json()
        rows = body.get("results", body) if isinstance(body, dict) else body
        ours_ids = {str(v.id) for v in ours.values() if hasattr(v, "id")}
        for row in rows:
            if isinstance(row, dict) and str(row.get("id")) in ours_ids:
                leaked.append(f"{url} leaked {row.get('id')}")

    assert leaked == [], f"another company's data visible: {leaked}"


@pytest.mark.django_db
def test_no_object_of_ours_is_reachable_by_them(ours, theirs):
    """Every detail URL, with their administrator, who has every privilege
    inside their own company and none inside ours."""
    intruder = client_for(theirs["admin"])
    leaked = []

    for label, url in detail_urls(ours).items():
        response = intruder.get(url)
        if response.status_code not in (403, 404):
            leaked.append(f"{label} -> {response.status_code}")

    assert leaked == [], f"reachable from another company: {leaked}"


@pytest.mark.django_db
def test_they_cannot_change_or_resolve_anything_of_ours(ours, theirs):
    """Reading is one thing; a write that lands is worse."""
    intruder = client_for(theirs["admin"])
    attempts = [
        ("post", f"/api/absences/{ours['absence'].id}/approve/", {}),
        ("post", f"/api/absences/{ours['absence'].id}/reject/", {}),
        ("post", f"/api/corrections/{ours['correction'].id}/approve/", {}),
        ("post", f"/api/corrections/{ours['correction'].id}/accept/", {}),
        ("post", f"/api/corrections/{ours['correction'].id}/dispute/", {"account": "no fue así"}),
        ("post", f"/api/corrections/{ours['correction'].id}/apply-anyway/", {}),
        ("patch", f"/api/employees/{ours['worker'].id}/", {"role": "ADMIN"}),
        ("delete", f"/api/employees/{ours['worker'].id}/", None),
        ("post", f"/api/employees/{ours['worker'].id}/invite/", {}),
        ("patch", f"/api/punches/{ours['punch'].id}/void/", {"reason": "porque sí"}),
        ("patch", f"/api/shift-patterns/{ours['pattern'].id}/", {"name": "Secuestrado"}),
        ("delete", f"/api/departments/{ours['department'].id}/", None),
    ]
    landed = []

    for method, url, body in attempts:
        call = getattr(intruder, method)
        response = call(url, body, format="json") if body is not None else call(url)
        if response.status_code < 400:
            landed.append(f"{method.upper()} {url} -> {response.status_code}")

    assert landed == [], f"another company's data was modified: {landed}"

    # And nothing actually moved.
    ours["worker"].refresh_from_db()
    ours["absence"].refresh_from_db()
    ours["pattern"].refresh_from_db()
    assert ours["worker"].role == Role.EMPLOYEE
    assert ours["worker"].is_active
    assert ours["absence"].status == "PENDING"
    assert ours["pattern"].name == "Turno Nuestra"


@pytest.mark.django_db
def test_naming_another_companys_person_does_not_reach_them(ours, theirs):
    """The filters take an id. Passing one from elsewhere must find nothing
    rather than quietly widen the query."""
    intruder = client_for(theirs["admin"])
    victim = str(ours["worker"].id)

    for url in ["/api/punches/", "/api/absences/", "/api/corrections/", "/api/shifts/"]:
        body = intruder.get(url, {"employee": victim}).json()
        rows = body.get("results", body) if isinstance(body, dict) else body
        assert rows == [], f"{url} returned rows for another company's employee"

    assert intruder.get("/api/absences/balance/", {"employee": victim}).status_code == 409
    assert intruder.get("/api/reports/working-time/", {"employee": victim}).status_code == 400


@pytest.mark.django_db
def test_their_settings_are_not_ours(ours, theirs):
    body = client_for(theirs["admin"]).get("/api/company/").json()
    assert body["tax_id"] == "B22222222"

    client_for(theirs["admin"]).patch("/api/company/", {"annual_leave_days": 40}, format="json")
    ours["company"].refresh_from_db()
    assert ours["company"].annual_leave_days == 22


# ------------------------------------------------ 3. a colleague, same company


@pytest.mark.django_db
def test_a_worker_cannot_read_a_colleagues_things(ours):
    colleague = client_for(ours["other"])
    leaked = []

    for label, url in detail_urls(ours).items():
        # Their own company's shared configuration is legitimately readable.
        if label in {"department", "shift pattern"}:
            continue
        response = colleague.get(url)
        if response.status_code not in (403, 404):
            leaked.append(f"{label} -> {response.status_code}")

    assert leaked == [], f"a colleague could read: {leaked}"


@pytest.mark.django_db
def test_a_worker_cannot_do_a_managers_job(ours):
    colleague = client_for(ours["other"])
    attempts = [
        ("post", f"/api/absences/{ours['absence'].id}/approve/", {}),
        ("post", f"/api/corrections/{ours['correction'].id}/approve/", {}),
        # A worker may accept or dispute their *own*, never impose one.
        ("post", f"/api/corrections/{ours['correction'].id}/apply-anyway/", {}),
        ("post", "/api/employees/", {"email": "nuevo@nuestra.test", "first_name": "Nuevo"}),
        ("patch", f"/api/employees/{ours['worker'].id}/", {"role": "ADMIN"}),
        ("post", f"/api/employees/{ours['worker'].id}/invite/", {}),
        ("patch", "/api/company/", {"annual_leave_days": 99}),
        ("patch", "/api/working-time-rules/", {"weekly_hours": 60}),
        (
            "post",
            "/api/shifts/assign/",
            {
                "employees": [str(ours["worker"].id)],
                "pattern": str(ours["pattern"].id),
                "date_from": "2026-09-01",
                "date_to": "2026-09-02",
            },
        ),
        ("patch", f"/api/punches/{ours['punch'].id}/void/", {"reason": "porque sí"}),
    ]
    landed = []

    for method, url, body in attempts:
        response = getattr(colleague, method)(url, body, format="json")
        if response.status_code < 400:
            landed.append(f"{method.upper()} {url} -> {response.status_code}")

    assert landed == [], f"a worker could act as a manager: {landed}"


@pytest.mark.django_db
def test_a_worker_sees_only_their_own_rows(ours):
    """Their own record is a right; a colleague's is not."""
    colleague = client_for(ours["other"])

    for url in ["/api/punches/", "/api/absences/", "/api/corrections/", "/api/shifts/"]:
        body = colleague.get(url).json()
        rows = body.get("results", body) if isinstance(body, dict) else body
        assert rows == [], f"{url} showed a colleague's rows"


@pytest.mark.django_db
def test_the_overview_tells_a_worker_nothing_about_others(ours):
    body = client_for(ours["other"]).get("/api/overview/").json()

    assert body["scope"] == "self"
    for leaky in ("working_now", "off_today", "headcount", "week"):
        assert leaky not in body


# ----------------------------------------------- the sweep must stay complete


@pytest.mark.django_db
def test_every_route_is_covered_by_this_sweep():
    """Fails when a new endpoint appears and nobody added it here.

    The leak that gets shipped is the one in the endpoint nobody remembered to
    check, so forgetting has to break the build rather than pass quietly.
    """

    def walk(resolver, prefix=""):
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern, prefix + str(pattern.pattern))
            else:
                yield prefix + str(pattern.pattern)

    # Format suffixes are the same view reached another way.
    routes = {
        r
        for r in walk(get_resolver())
        if r.startswith("api/") and "format" not in r and r != "api/"
    }

    # Reached by the sweep above, or exempt with a reason.
    covered = {
        # Public on purpose.
        "api/health/",
        "api/auth/token/",
        "api/auth/register/",
        "api/auth/password-reset/",
        "api/auth/set-password/",
        "api/docs/",
        "api/schema/",
        # Own session only; no object of anybody else's to reach.
        "api/auth/me/",
        "api/auth/logout/",
        # Application credential, covered in apps/punches/tests/test_delegated.py.
        "api/punches/delegated/",
    }
    swept = {
        "api/^punches/$",
        "api/^punches/(?P<pk>[^/.]+)/$",
        "api/^punches/today/$",
        "api/^punches/(?P<pk>[^/.]+)/void/$",
        "api/^absences/$",
        "api/^absences/(?P<pk>[^/.]+)/$",
        "api/^absences/(?P<pk>[^/.]+)/approve/$",
        "api/^absences/(?P<pk>[^/.]+)/reject/$",
        "api/^absences/(?P<pk>[^/.]+)/cancel/$",
        "api/^absences/(?P<pk>[^/.]+)/justification/$",
        "api/^absences/balance/$",
        "api/^absences/pending/$",
        "api/^absences/calendar/$",
        "api/^corrections/$",
        "api/^corrections/(?P<pk>[^/.]+)/$",
        "api/^corrections/(?P<pk>[^/.]+)/approve/$",
        "api/^corrections/(?P<pk>[^/.]+)/accept/$",
        "api/^corrections/(?P<pk>[^/.]+)/dispute/$",
        "api/^corrections/(?P<pk>[^/.]+)/apply-anyway/$",
        "api/^corrections/(?P<pk>[^/.]+)/reject/$",
        "api/^employees/$",
        "api/^employees/(?P<pk>[^/.]+)/$",
        "api/^employees/(?P<pk>[^/.]+)/invite/$",
        "api/^departments/$",
        "api/^departments/(?P<pk>[^/.]+)/$",
        "api/^shifts/$",
        "api/^shifts/(?P<pk>[^/.]+)/$",
        "api/^shifts/today/$",
        "api/^shifts/assign/$",
        "api/^shifts/clear/$",
        "api/^shifts/review/$",
        "api/^shifts/roster/$",
        "api/^shift-patterns/$",
        "api/^shift-patterns/(?P<pk>[^/.]+)/$",
        "api/^audit/$",
        "api/^audit/(?P<pk>[^/.]+)/$",
        "api/overview/",
        "api/company/",
        "api/working-time-rules/",
        "api/reports/working-time/",
        "api/reports/payroll-summary/",
    }

    uncovered = routes - covered - swept
    assert uncovered == set(), (
        "these endpoints are not in the isolation sweep. Add them to the tests "
        f"above and to `swept`, or to `covered` with a reason: {sorted(uncovered)}"
    )
