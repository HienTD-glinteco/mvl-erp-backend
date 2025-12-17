import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalStatus, ProposalType, TimesheetReason, TimesheetStatus
from apps.hrm.models.employee import Employee
from apps.hrm.models.holiday import CompensatoryWorkday
from apps.hrm.models.organization import Block, Branch, Department
from apps.hrm.models.proposal import Proposal
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

pytestmark = pytest.mark.django_db


def make_datetime(d: date, t: time, tz: ZoneInfo | None = None):
    if tz is None:
        return timezone.make_aware(datetime.combine(d, t))
    # create aware in specified tz
    aware = datetime.combine(d, t).replace(tzinfo=tz)
    # normalize to Django's timezone (comparisons will work across tzinfos)
    return aware.astimezone(timezone.get_default_timezone())


def _create_employee():
    prov = Province.objects.create(
        code=str(uuid.uuid4())[:2], name="P", english_name="P", level=Province.ProvinceLevel.CENTRAL_CITY, enabled=True
    )
    admin = AdministrativeUnit.objects.create(
        code=str(uuid.uuid4())[:3],
        name="AU",
        parent_province=prov,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
        enabled=True,
    )
    branch = Branch.objects.create(name="B", code=str(uuid.uuid4())[:3], province=prov, administrative_unit=admin)
    block = Block.objects.create(
        name="BL", code=str(uuid.uuid4())[:3], block_type=Block.BlockType.SUPPORT, branch=branch
    )
    dept = Department.objects.create(name="D", code=str(uuid.uuid4())[:3], branch=branch, block=block)

    unique = str(uuid.uuid4())[:8]
    emp = Employee.objects.create(
        code=f"MV{unique}",
        fullname="TZ Employee",
        attendance_code="tz123",
        username=f"u_{unique}",
        email=f"{unique}@example.com",
        branch=branch,
        block=block,
        department=dept,
        start_date=date(2020, 1, 1),
        citizen_id=str(uuid.uuid4().int)[:12],
        phone="0123456789",
    )
    return emp


def _create_monday_schedule():
    return WorkSchedule.objects.create(
        weekday=2,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        noon_start_time=time(12, 0),
        noon_end_time=time(13, 0),
        afternoon_start_time=time(13, 0),
        afternoon_end_time=time(17, 0),
        allowed_late_minutes=5,
    )


def test_full_day_paid_leave_takes_precedence_over_compensatory(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)  # Monday

    # Create an approved full-day paid leave
    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.PAID_LEAVE,
        paid_leave_start_date=d,
        paid_leave_end_date=d,
    )

    # Also create a compensatory workday for the same date (should not override leave)
    # CompensatoryWorkday requires a Holiday FK
    holiday = __import__("apps.hrm.models.holiday", fromlist=["Holiday"]).Holiday.objects.create(
        name="H", start_date=d, end_date=d
    )
    CompensatoryWorkday.objects.create(holiday=holiday, date=d, session=CompensatoryWorkday.Session.FULL_DAY)

    ts = TimeSheetEntry(employee=emp, date=d)
    # Employee did punch in (but leave should still take precedence)
    ts.start_time = make_datetime(d, time(8, 0))
    ts.end_time = make_datetime(d, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ABSENT
    assert ts.absent_reason == TimesheetReason.PAID_LEAVE
    assert ts.count_for_payroll is False


def test_timezone_aware_start_times_respect_schedule(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)  # Monday

    # Asia/Ho_Chi_Minh is UTC+7. If default timezone is UTC, 08:00 UTC == 15:00 HCM.
    hcm = ZoneInfo("Asia/Ho_Chi_Minh")

    # Build times by converting from the default timezone to HCM so the
    # instants are exactly equivalent regardless of the test environment TZ.
    allowed_base = timezone.make_aware(datetime.combine(d, time(8, 0))) + timedelta(minutes=5)
    # 2 minutes before allowed => ON_TIME
    target_on = allowed_base - timedelta(minutes=2)
    start_on_hcm = target_on.astimezone(hcm)

    ts_on = TimeSheetEntry(employee=emp, date=d)
    ts_on.start_time = start_on_hcm
    ts_on.end_time = start_on_hcm.astimezone(timezone.get_default_timezone()).replace(hour=17, minute=0)
    TimesheetCalculator(ts_on).compute_status()
    assert ts_on.status == TimesheetStatus.ON_TIME
    # 1 minute after allowed => NOT_ON_TIME
    target_late = allowed_base + timedelta(minutes=1)
    start_late_hcm = target_late.astimezone(hcm)

    ts_late = TimeSheetEntry(employee=emp, date=d)
    ts_late.start_time = start_late_hcm
    ts_late.end_time = start_late_hcm.astimezone(timezone.get_default_timezone()).replace(hour=17, minute=0)
    TimesheetCalculator(ts_late).compute_status()
    assert ts_late.status == TimesheetStatus.NOT_ON_TIME
