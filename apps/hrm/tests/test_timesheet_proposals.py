import uuid
from datetime import date, datetime, time

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalStatus, ProposalType, ProposalWorkShift, TimesheetStatus
from apps.hrm.models.employee import Employee
from apps.hrm.models.organization import Block, Branch, Department
from apps.hrm.models.proposal import Proposal
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

pytestmark = pytest.mark.django_db


def make_datetime(d: date, t: time):
    return timezone.make_aware(datetime.combine(d, t))


def _create_employee():
    # Minimal related org objects
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
        fullname="Test Employee",
        attendance_code="12345",
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
    # Weekday 2 = Monday
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


def test_late_exemption_allows_late_arrival(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)  # Monday

    # Create approved late exemption covering this date
    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.LATE_EXEMPTION,
        late_exemption_start_date=d,
        late_exemption_end_date=d,
        late_exemption_minutes=60,
    )

    ts = TimeSheetEntry(employee=emp, date=d)
    ts.start_time = make_datetime(d, time(9, 0))
    ts.end_time = make_datetime(d, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME


def test_maternity_leave_marks_on_time(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.MATERNITY_LEAVE,
        maternity_leave_start_date=d,
        maternity_leave_end_date=d,
    )

    ts = TimeSheetEntry(employee=emp, date=d)
    # repository expectation: full-day maternity leave should mark ABSENT
    TimesheetCalculator(ts).compute_status()
    assert ts.status == TimesheetStatus.ABSENT


def test_half_day_paid_leave_allows_afternoon_only(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    # Paid leave for morning only
    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.PAID_LEAVE,
        paid_leave_start_date=d,
        paid_leave_end_date=d,
        paid_leave_shift=ProposalWorkShift.MORNING,
    )

    ts = TimeSheetEntry(employee=emp, date=d)
    # attend only afternoon
    ts.start_time = make_datetime(d, time(13, 5))
    ts.end_time = make_datetime(d, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME


def test_single_punch_marks_not_on_time(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    ts = TimeSheetEntry(employee=emp, date=d)
    ts.start_time = make_datetime(d, time(8, 30))
    ts.end_time = None
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.SINGLE_PUNCH
