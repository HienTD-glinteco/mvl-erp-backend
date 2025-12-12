from datetime import date

from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    AttendanceDevice,
    AttendanceRecord,
    Block,
    Branch,
    Department,
    Employee,
    EmployeeMonthlyTimesheet,
    Position,
    TimeSheetEntry,
)


def test_attendance_record_create_updates_timesheet_and_monthly(db):
    province = Province.objects.create(name="Prov", code="P")
    admin_unit = AdministrativeUnit.objects.create(
        name="Unit", code="U", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )
    branch = Branch.objects.create(name="B", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Blk", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(name="Dept", branch=branch, block=block)
    position = Position.objects.create(name="Dev")

    emp = Employee.objects.create(
        code="MV002",
        fullname="Jane Doe",
        username="jane",
        email="jane@example.com",
        phone="0912300001",
        attendance_code="00002",
        citizen_id="000000000002",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    device = AttendanceDevice.objects.create(name="Dev1", ip_address="127.0.0.1", port=4370, is_enabled=True)

    d1 = timezone.datetime(2024, 6, 15, 8, 0, 0, tzinfo=timezone.get_current_timezone())
    d2 = timezone.datetime(2024, 6, 15, 17, 0, 0, tzinfo=timezone.get_current_timezone())
    _ = AttendanceRecord.objects.create(
        code="TEST001", biometric_device=device, attendance_code=emp.attendance_code, timestamp=d1
    )
    _ = AttendanceRecord.objects.create(
        code="TEST002", biometric_device=device, attendance_code=emp.attendance_code, timestamp=d2
    )

    # Entry should be created for today's date
    entry = TimeSheetEntry.objects.filter(employee=emp, date=timezone.datetime(2024, 6, 15).date()).first()
    assert entry is not None
    assert entry.start_time == d1
    assert entry.end_time == d2

    # Monthly timesheet must exist and be marked for refresh
    month_key = "202406"
    m = EmployeeMonthlyTimesheet.objects.filter(employee=emp, month_key=month_key).first()
    assert m is not None
    assert m.need_refresh is True
