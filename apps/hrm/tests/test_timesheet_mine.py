import calendar
import uuid
from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Permission, Province, Role, User
from apps.hrm.models.employee import Employee
from apps.hrm.models.organization import Block, Branch, Department
from apps.hrm.models.timesheet import TimeSheetEntry

pytestmark = pytest.mark.django_db


def _create_employee():
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
    # Signal creates and links User; refresh from db to ensure user is attached
    emp.refresh_from_db()
    return emp


def test_mine_returns_400_when_user_has_no_employee():
    client = APIClient()
    user = User.objects.create_user(username="no_emp", email="noemp@example.com", password="p")
    # grant permission for timesheet.mine to this user via role
    perm = Permission.objects.create(code="timesheet.mine", name="Timesheet mine")
    role = Role.objects.create(code=f"TST{str(uuid.uuid4())[:4]}", name=f"TestRole-{uuid.uuid4()}")
    role.permissions.add(perm)
    user.role = role
    user.save()
    client.force_authenticate(user=user)

    resp = client.get("/api/hrm/timesheets/mine/")
    assert resp.status_code == 400
    resp_data = resp.json()
    assert resp_data.get("success") is False
    # error message is translated; assert substring to avoid strict match
    assert "not associated" in str(resp_data.get("error")).lower()


def test_mine_returns_timesheet_for_employee_with_entry():
    client = APIClient()
    emp = _create_employee()
    # Employee creation signal should have created a linked User
    user = emp.user
    assert user is not None

    # grant permission to employee's user so RoleBasedPermission allows access
    perm = Permission.objects.create(code="timesheet.mine", name="Timesheet mine")
    role = Role.objects.create(code=f"TST{str(uuid.uuid4())[:4]}", name=f"TestRole-{uuid.uuid4()}")
    role.permissions.add(perm)
    user.role = role
    user.save()

    # create a timesheet entry for today
    today = timezone.localdate()
    entry = TimeSheetEntry.objects.create(employee=emp, date=today)

    client.force_authenticate(user=user)
    resp = client.get("/api/hrm/timesheets/mine/")
    assert resp.status_code == 200

    resp_data = resp.json()
    assert resp_data.get("success") is True
    data = resp_data.get("data")
    # response is serialized EmployeeTimesheetSerializer
    assert data["employee"]["id"] == emp.id

    year = today.year
    month = today.month
    month_days = calendar.monthrange(year, month)[1]
    assert len(data["dates"]) == month_days

    # ensure created entry appears among dates (has an id)
    assert any(d.get("id") == entry.id for d in data["dates"]) is True
