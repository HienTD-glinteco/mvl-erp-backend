import uuid
from datetime import date, datetime, time

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import TimesheetDayType, TimesheetStatus
from apps.hrm.models.employee import Employee
from apps.hrm.models.holiday import CompensatoryWorkday, Holiday
from apps.hrm.models.organization import Block, Branch, Department
from apps.hrm.models.timesheet import TimeSheetEntry

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


def make_datetime(d: date, t: time):
    return timezone.make_aware(datetime.combine(d, t))


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

    # A normal date should be OFFICIAL
    ts_o = TimeSheetEntry(employee=emp, date=date(2025, 3, 11))
    ts_o.save()
    assert ts_o.day_type == TimesheetDayType.OFFICIAL


def test_single_attendance_status_for_single_punch():
    emp = _create_employee()
    d = date(2025, 3, 3)

    # Single punch: only start_time
    ts = TimeSheetEntry(employee=emp, date=d)
    ts.start_time = make_datetime(d, time(8, 0))
    ts.end_time = None
    ts.save()
    assert ts.status == TimesheetStatus.SINGLE_PUNCH

    # Single punch: only end_time
    ts2 = TimeSheetEntry(employee=emp, date=d)
    ts2.start_time = None
    ts2.end_time = make_datetime(d, time(17, 0))
    ts2.save()
    assert ts2.status == TimesheetStatus.SINGLE_PUNCH
