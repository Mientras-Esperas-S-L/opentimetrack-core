"""The minimum content the pending royal decree asks of a record (art. 3).

Every test here names the paragraph it covers, because the point is not that
the code works but that it records the specific things the norm lists. Half of
these existed nowhere in the system a day ago.

The one that carries the most weight is the arithmetic: a break and a stretch
of waiting time are recorded **precisely because they are not working time**,
so a system that added them to the total would be producing a bigger number
than the one it can defend.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone, translation
from freezegun import freeze_time

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import (
    CURRENT_HASH_VERSION,
    FlexibilityMeasure,
    HoursNature,
    OvertimeSettlement,
    PunchInterval,
    WorkMode,
)
from apps.punches.services import build_day_status, register_punch
from apps.reports.services import build_report
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def worker(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Ana",
            last_name="Ruiz",
            employee_id="EMP-1",
        )


def punch(company, worker, **kw):
    return register_punch(employee=worker, company=company, **kw)


# ------------------------------------------------- 3.d: breaks are not work


@pytest.mark.django_db
def test_a_break_does_not_count_as_working_time(company, worker):
    """The arithmetic that matters. Eight hours with one hour of break is seven
    hours worked, and a system that said eight would be defending a number it
    cannot support."""
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker)  # in
        with freeze_time("2026-09-01 10:00:00"):
            punch(company, worker, interval=PunchInterval.BREAK)  # break starts
        with freeze_time("2026-09-01 11:00:00"):
            punch(company, worker, interval=PunchInterval.BREAK)  # break ends
        with freeze_time("2026-09-01 14:00:00"):
            punch(company, worker)  # out

        with freeze_time("2026-09-01 15:00:00"):
            status = build_day_status(worker, company)

    assert status.worked_seconds == 7 * 3600
    assert status.break_seconds == 3600
    assert status.state == "OFF"


@pytest.mark.django_db
def test_starting_a_break_does_not_close_the_working_day(company, worker):
    """They nest. A single cursor would read the break as the end of the day,
    which is a different fact and a shorter one."""
    with tenant_context(company.id), freeze_time("2026-09-01 06:00:00"):
        punch(company, worker)
        punch(company, worker, interval=PunchInterval.BREAK)
        status = build_day_status(worker, company)

    assert status.state == "ON_BREAK"


@pytest.mark.django_db
def test_a_break_cannot_start_outside_a_working_day(company, worker):
    """A break floating in the middle of nothing is something no reader can
    interpret and no inspector should have to."""
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        punch(company, worker, interval=PunchInterval.BREAK)

    assert caught.value.code == "not_working"


@pytest.mark.django_db
def test_the_break_start_and_end_are_both_in_the_report(company, worker):
    """3.d asks for the specific start and end time of each one, not a total."""
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 10:00:00"):
            punch(company, worker, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-01 10:30:00"):
            punch(company, worker, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-01 14:00:00"):
            punch(company, worker)

        report = build_report(
            employee=worker,
            company=company,
            date_from=timezone.datetime(2026, 9, 1).date(),
            date_to=timezone.datetime(2026, 9, 1).date(),
        )

    row = report.rows[0]
    assert len(row.breaks) == 1
    start, end = row.breaks[0]
    assert (start.hour, start.minute) == (12, 0)  # 10:00 UTC in Madrid
    assert (end.hour, end.minute) == (12, 30)
    assert row.break_seconds == 1800
    assert row.seconds == 7 * 3600 + 1800  # 8 h minus the half hour


# ------------------------------------------------ 3.g: waiting time apart


@pytest.mark.django_db
def test_waiting_time_is_recorded_and_kept_out_of_the_hours(company, worker):
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 08:00:00"):
            punch(company, worker, interval=PunchInterval.STANDBY)
        with freeze_time("2026-09-01 09:00:00"):
            punch(company, worker, interval=PunchInterval.STANDBY)
        with freeze_time("2026-09-01 14:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 15:00:00"):
            status = build_day_status(worker, company)

    assert status.standby_seconds == 3600
    # Recorded alongside, not deducted: unlike a break it is not carved out of
    # the day, and whether it counts is a question for the agreement.
    assert status.worked_seconds == 8 * 3600


# ------------------------------------------------------- 3.e: on site or remote


@pytest.mark.django_db
def test_the_mode_travels_with_the_span_not_the_person(company, worker):
    """3.e says "the day **or part of it**". A morning at home and an afternoon
    on site is two spans with different answers."""
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker, work_mode=WorkMode.REMOTE)
        with freeze_time("2026-09-01 10:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 12:00:00"):
            punch(company, worker, work_mode=WorkMode.ONSITE)
        with freeze_time("2026-09-01 16:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 17:00:00"):
            status = build_day_status(worker, company)

    modes = [s.work_mode for s in status.segments]
    assert modes == [WorkMode.REMOTE, WorkMode.ONSITE]


@pytest.mark.django_db
def test_the_persons_usual_mode_is_the_default(company, worker):
    with tenant_context(company.id):
        worker.default_work_mode = "REMOTE"
        worker.save(update_fields=["default_work_mode"])
        event = punch(company, worker)

    assert event.work_mode == WorkMode.REMOTE


# ------------------------------------- 3.f: ordinary, overtime, complementary


@pytest.mark.django_db
def test_overtime_must_say_how_it_settles(company, worker):
    """3.f asks whether it is rested or paid. Recording overtime without saying
    is recording half the fact."""
    with tenant_context(company.id), pytest.raises(BusinessRuleError) as caught:
        punch(company, worker, hours_nature=HoursNature.OVERTIME)

    assert caught.value.code == "overtime_settlement_required"


@pytest.mark.django_db
def test_overtime_is_counted_apart_from_ordinary_hours(company, worker):
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 14:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 15:00:00"):
            punch(
                company,
                worker,
                hours_nature=HoursNature.OVERTIME,
                overtime_settlement=OvertimeSettlement.PAID,
            )
        with freeze_time("2026-09-01 17:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 18:00:00"):
            status = build_day_status(worker, company)

    assert status.worked_seconds == 10 * 3600
    assert status.overtime_seconds == 2 * 3600


@pytest.mark.django_db
def test_force_majeure_hours_are_distinguishable(company, worker):
    """Art. 35.3 ET: hours worked to repair urgent damage do not count towards
    the annual overtime limit, so they cannot be indistinguishable."""
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            event = punch(
                company,
                worker,
                hours_nature=HoursNature.OVERTIME,
                overtime_settlement=OvertimeSettlement.PAID,
                force_majeure=True,
            )
        with freeze_time("2026-09-01 10:00:00"):
            punch(company, worker)

        report = build_report(
            employee=worker,
            company=company,
            date_from=timezone.datetime(2026, 9, 1).date(),
            date_to=timezone.datetime(2026, 9, 1).date(),
        )

    assert event.force_majeure
    assert report.rows[0].force_majeure_seconds == 4 * 3600


# ------------------------------------------------------- 3.i: arrangements


@pytest.mark.django_db
def test_the_arrangement_is_named(company, worker):
    """3.i wants the specific measure, not just that there was one."""
    with tenant_context(company.id):
        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker, flexibility_measure=FlexibilityMeasure.CARE)
        with freeze_time("2026-09-01 10:00:00"):
            punch(company, worker)

        report = build_report(
            employee=worker,
            company=company,
            date_from=timezone.datetime(2026, 9, 1).date(),
            date_to=timezone.datetime(2026, 9, 1).date(),
        )

    assert report.rows[0].arrangements  # named, not a boolean


# --------------------------------------------------------- 3.b and 3.j


@pytest.mark.django_db
def test_the_agreed_regime_reaches_the_report(company, worker):
    """3.b: full or part time, the agreed hours, and the percentage."""
    with tenant_context(company.id):
        worker.regime = "PART_TIME"
        worker.contracted_hours = 20
        worker.contracted_schedule = "L-V 09:00-13:00"
        worker.save(update_fields=["regime", "contracted_hours", "contracted_schedule"])

        # In English so the assertion is about the content reaching the report
        # rather than about which catalogue is compiled. The report itself does
        # render the label translated, which is what an inspection should read.
        with translation.override("en"):
            report = build_report(
                employee=worker,
                company=company,
                date_from=timezone.datetime(2026, 9, 1).date(),
                date_to=timezone.datetime(2026, 9, 1).date(),
            )

    # Art. 3.b: the regime and the agreed hours, with the share of a full day
    # worked out rather than typed --- 20 of the company's 40 is half.
    assert report.regime == "Part time"
    assert report.contracted_hours == "20 h a week (50 %)"
    assert report.contracted_schedule == "L-V 09:00-13:00"


@pytest.mark.django_db
def test_the_report_totals_by_month(company, worker):
    """3.j asks for a daily **and monthly** total."""
    with tenant_context(company.id):
        for day, hour_in, hour_out in [
            ("2026-09-30", 6, 14),
            ("2026-10-01", 6, 14),
            ("2026-10-02", 6, 10),
        ]:
            with freeze_time(f"{day} {hour_in:02d}:00:00"):
                punch(company, worker)
            with freeze_time(f"{day} {hour_out:02d}:00:00"):
                punch(company, worker)

        report = build_report(
            employee=worker,
            company=company,
            date_from=timezone.datetime(2026, 9, 30).date(),
            date_to=timezone.datetime(2026, 10, 2).date(),
        )

    assert report.monthly_seconds["2026-09"] == 8 * 3600
    assert report.monthly_seconds["2026-10"] == 12 * 3600
    assert report.total_seconds == 20 * 3600


# ------------------------------------------------------------ the seal


@pytest.mark.django_db
def test_the_new_fields_are_sealed_into_the_hash(company, worker):
    """Otherwise somebody could turn overtime into a break, or remote into on
    site, without the seal noticing."""
    with tenant_context(company.id):
        event = punch(
            company,
            worker,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
        )

    assert event.hash_version == CURRENT_HASH_VERSION
    assert event.verify_hash()

    for field, value in [
        ("interval", PunchInterval.BREAK),
        ("work_mode", WorkMode.REMOTE),
        ("hours_nature", HoursNature.ORDINARY),
        ("overtime_settlement", OvertimeSettlement.REST),
        ("force_majeure", True),
        ("flexibility_measure", FlexibilityMeasure.CARE),
    ]:
        event.refresh_from_db()
        setattr(event, field, value)
        assert not event.verify_hash(), f"changing {field} did not break the seal"


@pytest.mark.django_db
def test_events_recorded_before_all_this_still_verify(company, worker):
    """Version 2 events predate these fields. Their seal was computed without
    them and must keep holding: rehashing to fit a new payload is exactly the
    manipulation the seal exists to reveal."""
    from apps.punches.models import Punch

    with tenant_context(company.id):
        old = Punch(
            tenant=company,
            employee=worker,
            punch_type="IN",
            timestamp=timezone.now() - timedelta(days=30),
        )
        old.hash_version = 2
        old.hash_integrity = old.compute_hash()
        old.save()

        old.refresh_from_db()
        # A field it never knew about does not affect its seal.
        old.work_mode = WorkMode.REMOTE

    assert old.verify_hash()


# ------------------------------------------- found in the legal re-read of 12/08


@pytest.mark.django_db
def test_the_break_counts_when_the_agreement_says_so(company, worker):
    """Art. 34.4 ET makes the fifteen-minute break working time **only when the
    agreement or the contract says so** --- and a good many agreements do.

    Until this was fixed the deduction was unconditional, which in those
    companies took roughly fifty-five hours a year off every worker, quietly and
    in the direction that favours the employer.
    """
    from apps.tenants.rules import WorkingTimeRules

    with tenant_context(company.id):
        rules = WorkingTimeRules.for_company(company)
        rules.break_counts_as_work = True
        rules.save(update_fields=["break_counts_as_work"])

        with freeze_time("2026-09-01 06:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 10:00:00"):
            punch(company, worker, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-01 10:15:00"):
            punch(company, worker, interval=PunchInterval.BREAK)
        with freeze_time("2026-09-01 14:00:00"):
            punch(company, worker)
        with freeze_time("2026-09-01 15:00:00"):
            status = build_day_status(worker, company)

    # Eight hours, break included, because that is what this company agreed.
    assert status.worked_seconds == 8 * 3600
    # And it is still recorded as a break: art. 3.d wants it visible either way.
    assert status.break_seconds == 15 * 60


@pytest.mark.django_db
def test_part_time_work_admits_no_overtime(company, worker):
    """Art. 12.4.c ET, literal: «Los trabajadores a tiempo parcial no podrán
    realizar horas extraordinarias, salvo en los supuestos a los que se refiere
    el artículo 35.3». What they have instead is complementary hours."""
    with tenant_context(company.id):
        worker.regime = "PART_TIME"
        worker.contracted_hours = 20
        worker.save(update_fields=["regime", "contracted_hours"])

        with pytest.raises(BusinessRuleError) as caught:
            punch(
                company,
                worker,
                hours_nature=HoursNature.OVERTIME,
                overtime_settlement=OvertimeSettlement.PAID,
            )

    assert caught.value.code == "overtime_not_available_part_time"


@pytest.mark.django_db
def test_part_time_work_does_admit_the_force_majeure_exception(company, worker):
    """The «salvo» of art. 12.4.c: hours worked to prevent or repair urgent
    damage (art. 35.3) are open to everybody."""
    with tenant_context(company.id):
        worker.regime = "PART_TIME"
        worker.contracted_hours = 20
        worker.save(update_fields=["regime", "contracted_hours"])

        event = punch(
            company,
            worker,
            hours_nature=HoursNature.OVERTIME,
            overtime_settlement=OvertimeSettlement.PAID,
            force_majeure=True,
        )

    assert event.hours_nature == HoursNature.OVERTIME
    assert event.force_majeure


@pytest.mark.django_db
def test_part_time_work_admits_complementary_hours(company, worker):
    """Which is the mechanism art. 12.5 gives them instead."""
    with tenant_context(company.id):
        worker.regime = "PART_TIME"
        worker.contracted_hours = 20
        worker.save(update_fields=["regime", "contracted_hours"])
        event = punch(company, worker, hours_nature=HoursNature.COMPLEMENTARY)

    assert event.hours_nature == HoursNature.COMPLEMENTARY
