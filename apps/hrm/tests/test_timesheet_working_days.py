import uuid
from datetime import date, time
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models.employee import Employee
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.organization import Block, Branch, Department
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from libs.decimals import quantize_decimal

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


def test_monthly_aggregates_sum_working_days():
    # Ensure work schedules exist for the days tested
    # 2025-03-03 is Monday, 03-04 is Tuesday
    WorkSchedule.objects.create(
        weekday=WorkSchedule.Weekday.MONDAY,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        afternoon_start_time=time(13, 0),
        afternoon_end_time=time(17, 0),
    )
    WorkSchedule.objects.create(
        weekday=WorkSchedule.Weekday.TUESDAY,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        afternoon_start_time=time(13, 0),
        afternoon_end_time=time(17, 0),
    )

    emp = _create_employee()
    year = 2025
    month = 3

    # Day 1: full day (8h -> 1.00)
    ts1 = TimeSheetEntry.objects.create(employee=emp, date=date(year, month, 3))
    TimeSheetEntry.objects.filter(pk=ts1.pk).update(
        morning_hours=Decimal("4.00"),
        afternoon_hours=Decimal("4.00"),
        official_hours=Decimal("8.00"),
        working_days=Decimal("1.00"),
        is_full_salary=True,
    )

    # Day 2: half day (4h -> 0.50)
    ts2 = TimeSheetEntry.objects.create(employee=emp, date=date(year, month, 4))
    TimeSheetEntry.objects.filter(pk=ts2.pk).update(
        morning_hours=Decimal("2.00"),
        afternoon_hours=Decimal("2.00"),
        official_hours=Decimal("4.00"),
        working_days=Decimal("0.50"),
        is_full_salary=True,
    )

    aggs = EmployeeMonthlyTimesheet.compute_aggregates(emp.id, year, month)

    # total_working_days should be 1.50
    assert quantize_decimal(aggs["total_working_days"]) == Decimal("1.50")
    # official_working_days should equal probation_working_days + official_working_days depending on is_full_salary (default True)
    assert quantize_decimal(aggs["official_working_days"]) == Decimal("1.50")
