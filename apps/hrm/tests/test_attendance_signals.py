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
    block = Block.objects.create(name="Blk", branch=branch)
    department = Department.objects.create(name="Dept", branch=branch, block=block)
    position = Position.objects.create(name="Dev")

    emp = Employee.objects.create(
        code="MV002",
        fullname="Jane Doe",
        username="jane",
        email="jane@example.com",
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

    now = timezone.now()
    rec = AttendanceRecord.objects.create(
        code="TEST001", device=device, attendance_code=emp.attendance_code, timestamp=now
    )

    # Entry should be created for today's date
    entry = TimeSheetEntry.objects.filter(employee=emp, date=now.date()).first()
    assert entry is not None
    assert entry.start_time is not None
    assert entry.end_time is not None

    # Monthly timesheet must exist and be marked for refresh
    month_key = f"{now.year:04d}{now.month:02d}"
    m = EmployeeMonthlyTimesheet.objects.filter(employee=emp, month_key=month_key).first()
    assert m is not None
    assert m.need_refresh is True
