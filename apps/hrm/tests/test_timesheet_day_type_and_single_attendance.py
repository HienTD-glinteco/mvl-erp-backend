import uuid
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import TimesheetStatus
from apps.hrm.models import Block, Branch, Department, Employee, TimeSheetEntry
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from libs.datetimes import combine_datetime

pytestmark = pytest.mark.django_db


def _create_employee():
    prov = Province.objects.create(code=str(uuid.uuid4())[:2], name="P", english_name="P", enabled=True)
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
        personal_email=f"{unique}.personal@example.com",
        branch=branch,
        block=block,
        department=dept,
        start_date=date(2020, 1, 1),
        citizen_id=str(uuid.uuid4().int)[:12],
        phone="0123456789",
    )
    return emp


def test_single_attendance_status_for_single_punch():
    emp = _create_employee()

    # Use a future Monday so is_finalizing=False for preview mode
    today = timezone.localdate()
    days_until_monday = (7 - today.weekday()) % 7 + 7  # Next Monday
    future_monday = today + timedelta(days=days_until_monday)

    # Single punch: only start_time (on-time check-in at 8:00)
    ts = TimeSheetEntry.objects.create(
        employee=emp, date=future_monday, check_in_time=combine_datetime(future_monday, time(8, 0))
    )
    # After save/clean, real-time mode with on-time check-in shows ON_TIME
    assert ts.status == TimesheetStatus.ON_TIME
    assert ts.working_days is None

    # Finalization mode
    TimesheetCalculator(ts).compute_all(is_finalizing=True)
    assert ts.status == TimesheetStatus.SINGLE_PUNCH
    assert ts.working_days == Decimal("0.50")

    # Single punch: only end_time (can't determine lateness, so ON_TIME by default)
    ts2 = TimeSheetEntry.objects.create(
        employee=emp, date=future_monday, check_out_time=combine_datetime(future_monday, time(17, 0))
    )
    # After save/clean, real-time mode with only end_time (no late/early penalty)
    assert ts2.status == TimesheetStatus.ON_TIME
    assert ts2.working_days is None

    # Finalization mode
    TimesheetCalculator(ts2).compute_all(is_finalizing=True)
    assert ts2.status == TimesheetStatus.SINGLE_PUNCH
    assert ts2.working_days == Decimal("0.50")
