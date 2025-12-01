from datetime import date

from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, Position
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry


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
