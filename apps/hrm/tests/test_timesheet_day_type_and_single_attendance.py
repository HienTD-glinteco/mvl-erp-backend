import uuid
from datetime import date, time
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import TimesheetStatus
from apps.hrm.models import Block, Branch, Department, Employee, TimeSheetEntry
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
    d = date(2025, 3, 3)

    # Single punch: only start_time
    ts = TimeSheetEntry.objects.create(employee=emp, date=d, check_in_time=combine_datetime(d, time(8, 0)))
    # After save/clean, real-time mode sets NOT_ON_TIME
    assert ts.status == TimesheetStatus.NOT_ON_TIME
    assert ts.working_days is None

    # Finalization mode
    from apps.hrm.services.timesheet_calculator import TimesheetCalculator

    TimesheetCalculator(ts).compute_all(is_finalizing=True)
    assert ts.status == TimesheetStatus.SINGLE_PUNCH
    assert ts.working_days == Decimal("0.50")

    # Single punch: only end_time
    ts2 = TimeSheetEntry.objects.create(employee=emp, date=d, check_out_time=combine_datetime(d, time(17, 0)))
    # After save/clean, real-time mode sets NOT_ON_TIME
    assert ts2.status == TimesheetStatus.NOT_ON_TIME
    assert ts2.working_days is None

    # Finalization mode
    TimesheetCalculator(ts2).compute_all(is_finalizing=True)
    assert ts2.status == TimesheetStatus.SINGLE_PUNCH
    assert ts2.working_days == Decimal("0.50")
