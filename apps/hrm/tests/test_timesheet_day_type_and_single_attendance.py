import uuid
from datetime import date, time

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import TimesheetDayType, TimesheetStatus
from apps.hrm.models import Block, Branch, CompensatoryWorkday, Department, Employee, Holiday, TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
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


def test_day_type_holiday_and_compensatory_and_official():
    emp = _create_employee()

    # Create a holiday covering March 10
    h = Holiday.objects.create(name="H", start_date=date(2025, 3, 10), end_date=date(2025, 3, 10))

    # Holiday date should mark day_type HOLIDAY
    ts_h = TimeSheetEntry(employee=emp, date=date(2025, 3, 10))
    ts_h.save()
    assert ts_h.day_type == TimesheetDayType.HOLIDAY

    # Create a compensatory day for March 16 (outside holiday range)
    comp = CompensatoryWorkday.objects.create(
        holiday=h, date=date(2025, 3, 16), session=CompensatoryWorkday.Session.FULL_DAY
    )

    ts_c = TimeSheetEntry(employee=emp, date=date(2025, 3, 16))
    ts_c.save()
    assert ts_c.day_type == TimesheetDayType.COMPENSATORY

    # A normal date WITHOUT WorkSchedule should be None
    ts_none = TimeSheetEntry(employee=emp, date=date(2025, 3, 11))
    ts_none.save()
    assert ts_none.day_type is None

    # Create WorkSchedule for Tuesday (2025-03-11 is Tuesday -> Weekday 3)
    WorkSchedule.objects.create(
        weekday=WorkSchedule.Weekday.TUESDAY,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        afternoon_start_time=time(13, 0),
        afternoon_end_time=time(17, 0),
    )

    # Now create another entry for a Tuesday, should be OFFICIAL
    # Using 2025-03-18 (Tuesday)
    ts_o = TimeSheetEntry(employee=emp, date=date(2025, 3, 18))
    ts_o.save()
    assert ts_o.day_type == TimesheetDayType.OFFICIAL


def test_single_attendance_status_for_single_punch():
    emp = _create_employee()
    d = date(2025, 3, 3)

    # Single punch: only start_time
    ts = TimeSheetEntry.objects.create(employee=emp, date=d, check_in_time=combine_datetime(d, time(8, 0)))
    assert ts.status == TimesheetStatus.SINGLE_PUNCH

    # Single punch: only end_time
    ts2 = TimeSheetEntry.objects.create(employee=emp, date=d, check_out_time=combine_datetime(d, time(17, 0)))
    assert ts2.status == TimesheetStatus.SINGLE_PUNCH
