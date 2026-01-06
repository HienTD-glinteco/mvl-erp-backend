from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.core.cache import cache
from django.db.models.signals import post_save
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import TimesheetStatus
from apps.hrm.models import Block, Branch, Department, Employee, Position, WorkSchedule
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.services.timesheets import create_entries_for_employee_month


def test_list_timesheets_returns_entries_and_aggregates(db, api_client):
    client = api_client

    # Create organizational structure for employee
    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit",
        code="TU",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer")

    # Create employee using required related fields
    emp = Employee.objects.create(
        code="MV001",
        fullname="John Doe",
        username="user_mv001",
        email="mv001@example.com",
        phone="0900100001",
        attendance_code="00001",
        citizen_id="000000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    # Month for testing
    year = 2025
    month = 3
    first_day = date(year, month, 1)

    # Create two timesheet entries
    TimeSheetEntry.objects.create(employee=emp, date=first_day, morning_hours=4, afternoon_hours=4)
    TimeSheetEntry.objects.create(employee=emp, date=date(year, month, 2), morning_hours=8, afternoon_hours=0)

    # Refresh monthly timesheet
    EmployeeMonthlyTimesheet.refresh_for_employee_month(emp.id, year, month, fields=[])

    # Call API list endpoint
    url = reverse("hrm:employee-timesheet-list")
    resp = client.get(url, {"month": "03/2025"})

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    results = data["data"]["results"]

    assert len(results) >= 1
    item = next((i for i in results if i["employee"]["id"] == emp.id), None)
    assert item is not None
    assert "dates" in item
    assert len(item["dates"]) >= 2
    # Check that aggregate fields are present
    assert "total_work_days" in item
    assert "total_work_days" in item
    assert "remaining_leave_balance" in item


def test_bulk_create_past_entries_finalized(db):
    """Test that entries created via bulk_create for past dates are properly finalized.

    This regression test ensures that working_days and status are computed
    for past entries even when created via bulk_create (which skips clean()).
    """
    # Create work schedules for weekdays (Mon-Fri)
    cache.clear()  # Clear cache to ensure schedules are picked up
    for weekday in [
        WorkSchedule.Weekday.MONDAY,
        WorkSchedule.Weekday.TUESDAY,
        WorkSchedule.Weekday.WEDNESDAY,
        WorkSchedule.Weekday.THURSDAY,
        WorkSchedule.Weekday.FRIDAY,
    ]:
        WorkSchedule.objects.create(
            weekday=weekday,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )

    # Create organizational structure for employee
    province = Province.objects.create(name="Test Province Finalize", code="TPF")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit Finalize",
        code="TUF",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch Finalize",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block Finalize", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept Finalize", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer Finalize")

    emp = Employee.objects.create(
        code="MVFIN",
        fullname="Finalize Tester",
        username="finalize_tester",
        email="finalize@example.com",
        phone="0900100099",
        attendance_code="00099",
        citizen_id="000000000099",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    # Create entries for a past month (October 2025)
    # As of January 2026, all October 2025 dates are in the past
    year, month = 2025, 10
    created = create_entries_for_employee_month(emp.id, year, month)

    # Verify entries were created
    assert len(created) == 31  # October has 31 days

    # Verify past WEEKDAY entries have status=ABSENT and working_days=0
    # Weekend entries (no schedule) will have status=None
    for entry in created:
        weekday = entry.date.isoweekday()  # 1=Mon, 7=Sun
        is_weekday = weekday <= 5

        if is_weekday:
            # Weekday: should be ABSENT with working_days = 0
            assert entry.status == TimesheetStatus.ABSENT, f"Entry {entry.date} (weekday) should be ABSENT"
            assert entry.working_days == Decimal("0.00"), f"Entry {entry.date} should have 0 working_days"
        else:
            # Weekend: should have working_days set (even if status is None)
            assert entry.working_days is not None, f"Entry {entry.date} (weekend) should have working_days set"


def test_create_empty_entries_for_month_and_refresh(db):
    # Ensure the manager method will create timesheet entries for an employee
    province = Province.objects.create(name="Test Province 2", code="TP2")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit 2", code="TU2", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )
    branch = Branch.objects.create(name="Test Branch 2", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Test Block 2", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept 2", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer 2")

    emp = Employee.objects.create(
        code="MV003",
        fullname="John Smith",
        username="johnsmith",
        email="johnsmith@example.com",
        phone="0900100003",
        attendance_code="00003",
        citizen_id="000000000003",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    year = 2025
    month = 4
    # create empty entries for employee month via service
    from apps.hrm.services.timesheets import create_entries_for_employee_month

    created = create_entries_for_employee_month(emp.id, year, month)
    assert created
    assert len(created) == 30  # April 2025 has 30 days

    # call prepare task for the employee
    from apps.hrm.tasks.timesheets import prepare_monthly_timesheets

    result = prepare_monthly_timesheets(employee_id=emp.id, year=year, month=month)
    assert result["success"]


def test_list_timesheets_returns_full_month_dates_nov_2025(db, api_client):
    client = api_client

    province = Province.objects.create(name="Prov A", code="PA")
    admin_unit = AdministrativeUnit.objects.create(
        name="Unit A", code="UA", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )
    branch = Branch.objects.create(name="Branch A", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Block A", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Dept A", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Dev A")

    emp = Employee.objects.create(
        code="MV100",
        fullname="Full Month User",
        username="fullmonth",
        email="fullmonth@example.com",
        phone="0900100100",
        attendance_code="100",
        citizen_id="000000000100",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    url = reverse("hrm:employee-timesheet-list")
    resp = client.get(url, {"month": "11/2025"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    results = data["data"]["results"]

    item = next((i for i in results if i["employee"]["id"] == emp.id), None)
    assert item is not None
    dates = item["dates"]
    assert len(dates) == 30
    assert dates[0]["date"] == "2025-11-01"
    assert dates[-1]["date"] == "2025-11-30"


def test_month_filter_future_disallowed_raises_400(db, api_client):
    client = api_client
    url = reverse("hrm:employee-timesheet-list")
    resp = client.get(url, {"month": "01/2099"})
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    content = resp.json()
    # Ensure message is present somewhere in error payload
    assert "Month filter cannot be in the future" in str(content)


def test_retrieve_employee_timesheet_not_found(db, api_client):
    """Test that retrieve returns 404 for non-existent employee."""
    client = api_client
    url = reverse("hrm:employee-timesheet-detail", args=[99999])
    resp = client.get(url)

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_create_entries_for_employee_month_sends_post_save(db):
    """Test that create_entries_for_employee_month sends post_save signals since it uses bulk_create with manual signal dispatch."""
    province = Province.objects.create(name="Test Province Sig", code="TPS")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit Sig", code="TUS", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )
    branch = Branch.objects.create(name="Test Branch Sig", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Test Block Sig", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept Sig", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer Sig")

    emp = Employee.objects.create(
        code="MV999",
        fullname="Signal Tester",
        username="signaltester",
        email="signaltester@example.com",
        phone="0900100999",
        attendance_code="00999",
        citizen_id="000000000999",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    year = 2025
    month = 5  # May has 31 days

    # Mock the signal receiver
    handler = MagicMock()
    post_save.connect(handler, sender=TimeSheetEntry)

    try:
        from apps.hrm.services.timesheets import create_entries_for_employee_month

        created = create_entries_for_employee_month(emp.id, year, month)
    finally:
        post_save.disconnect(handler, sender=TimeSheetEntry)

    assert len(created) == 31
    # Check that signal was sent 31 times
    assert handler.call_count == 31

    # Verify call args for one of them
    call_args = handler.call_args_list[0]
    kwargs = call_args[1]
    assert kwargs["sender"] == TimeSheetEntry
    assert kwargs["created"] is True
    assert isinstance(kwargs["instance"], TimeSheetEntry)
