from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.hrm.constants import AttendanceType, TimesheetStatus
from apps.hrm.models import (
    AttendanceDailyReport,
    AttendanceGeolocation,
    AttendanceRecord,
    Block,
    Branch,
    Department,
    Employee,
    TimeSheetEntry,
)
from apps.hrm.services.attendance_report import aggregate_attendance_daily_report
from apps.hrm.tasks.attendance_report import recalculate_daily_attendance_reports_task
from apps.realestate.models import Project


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    from apps.core.models import User

    return User.objects.create_superuser(username="test_user", email="test_user@example.com", password="password")


@pytest.fixture
def organization_structure(db):
    # Create required foreign keys for Branch
    from apps.core.models import AdministrativeUnit, Province

    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit", code="TU", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )

    branch = Branch.objects.create(name="Test Branch", code="TB", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Test Block", code="TBL", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept", code="TD", block=block, branch=branch, function=Department.DepartmentFunction.BUSINESS
    )
    return branch, block, department


@pytest.fixture
def employee(db, organization_structure):
    branch, block, department = organization_structure
    return Employee.objects.create(
        code="MV001",
        fullname="Test Employee",
        username="test_employee",
        email="test@example.com",
        personal_email="testemployee.personal@example.com",
        phone="0901234567",
        branch=branch,
        block=block,
        department=department,
        start_date=date.today(),
        attendance_code="123",
    )


@pytest.fixture
def project(db):
    return Project.objects.create(name="Test Project", code="TP")


@pytest.fixture
def attendance_geolocation(db, project, user):
    return AttendanceGeolocation.objects.create(
        name="Test Geo",
        code="TG",
        project=project,
        latitude=Decimal("10.0"),
        longitude=Decimal("100.0"),
        radius_m=100,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
class TestAttendanceReportService:
    def test_aggregate_attendance_daily_report_create(self, employee, attendance_geolocation):
        report_date = date.today()
        timestamp = timezone.now()

        # Create attendance record
        record = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timestamp,
            attendance_type=AttendanceType.GEOLOCATION,
            attendance_geolocation=attendance_geolocation,
            is_valid=True,
            code="REC001",
        )

        aggregate_attendance_daily_report(employee.id, report_date)

        report = AttendanceDailyReport.objects.get(employee=employee, report_date=report_date)
        assert report.branch_id == employee.branch_id
        assert report.block_id == employee.block_id
        assert report.department_id == employee.department_id
        assert report.project_id == attendance_geolocation.project_id
        assert report.attendance_method == AttendanceType.GEOLOCATION
        assert report.attendance_record_id == record.id

    def test_aggregate_attendance_daily_report_update(self, employee, attendance_geolocation):
        report_date = date.today()
        timestamp = timezone.now()

        # Create initial report
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            attendance_method=AttendanceType.WIFI,  # Different method
        )

        # Create attendance record (should override existing report)
        record = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timestamp,
            attendance_type=AttendanceType.GEOLOCATION,
            attendance_geolocation=attendance_geolocation,
            is_valid=True,
            code="REC002",
        )

        aggregate_attendance_daily_report(employee.id, report_date)

        report = AttendanceDailyReport.objects.get(employee=employee, report_date=report_date)
        assert report.attendance_method == AttendanceType.GEOLOCATION
        assert report.attendance_record_id == record.id

    def test_aggregate_attendance_daily_report_delete(self, employee):
        report_date = date.today()

        # Create existing report
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            attendance_method=AttendanceType.WIFI,
        )

        # Run aggregation with no attendance records
        aggregate_attendance_daily_report(employee.id, report_date)

        assert not AttendanceDailyReport.objects.filter(employee=employee, report_date=report_date).exists()


@pytest.mark.django_db
class TestAttendanceReportTasks:
    def test_recalculate_daily_attendance_reports_task(self, employee, attendance_geolocation):
        report_date = date.today()
        timestamp = timezone.now()

        # Create attendance record
        AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timestamp,
            attendance_type=AttendanceType.GEOLOCATION,
            attendance_geolocation=attendance_geolocation,
            is_valid=True,
            code="REC003",
        )

        recalculate_daily_attendance_reports_task(report_date.strftime("%Y-%m-%d"))

        report = AttendanceDailyReport.objects.get(employee=employee, report_date=report_date)
        assert report.project_id == attendance_geolocation.project_id
        assert report.attendance_method == AttendanceType.GEOLOCATION


@pytest.mark.django_db
class TestAttendanceReportViewSet:
    def test_by_method_action(self, api_client, employee, user):
        api_client.force_authenticate(user=user)
        # Setup data
        report_date = date.today()
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            attendance_method=AttendanceType.BIOMETRIC_DEVICE,
        )

        # Create TimeSheetEntry for total employee count
        TimeSheetEntry.objects.create(employee=employee, date=report_date, status=TimesheetStatus.ON_TIME)

        url = "/api/hrm/attendance-reports/by-method/"
        response = api_client.get(url, {"attendance_date": report_date.strftime("%Y-%m-%d")})

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["absolute"]["total_employee"] == "1.00"
        assert data["absolute"]["has_attendance"] == "1.00"
        assert data["absolute"]["method_breakdown"]["device"] == "1.00"

    def test_by_project_action(self, api_client, employee, project, user):
        api_client.force_authenticate(user=user)
        report_date = date.today()
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            project=project,
            attendance_method=AttendanceType.GEOLOCATION,
        )

        url = "/api/hrm/attendance-reports/by-project/"
        response = api_client.get(url, {"attendance_date": report_date.strftime("%Y-%m-%d")})

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert len(data["projects"]) == 1
        assert data["projects"][0]["project"]["id"] == project.id
        assert data["projects"][0]["count"] == 1

    def test_by_project_organization_action(self, api_client, employee, user):
        api_client.force_authenticate(user=user)
        report_date = date.today()
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            attendance_method=AttendanceType.BIOMETRIC_DEVICE,
        )

        url = "/api/hrm/attendance-reports/by-project-organization/"
        response = api_client.get(url, {"attendance_date": report_date.strftime("%Y-%m-%d")})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["total"] == 1
        assert len(data["children"]) == 1
        branch_node = data["children"][0]
        assert branch_node["id"] == employee.branch_id
        assert branch_node["count"] == 1

    def test_by_method_envelope_and_percentage(self, api_client, employee, user):
        api_client.force_authenticate(user=user)
        report_date = date.today()
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            attendance_method=AttendanceType.WIFI,
        )
        TimeSheetEntry.objects.create(employee=employee, date=report_date, status=TimesheetStatus.ON_TIME)

        url = "/api/hrm/attendance-reports/by-method/"
        response = api_client.get(url, {"attendance_date": report_date.strftime("%Y-%m-%d")})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["percentage"]["total_employee"] == "100.00"
        assert data["percentage"]["has_attendance"] == "100.00"
        assert data["percentage"]["method_breakdown"]["wifi"] == "100.00"

    def test_by_project_filter_block_type_support(self, api_client, organization_structure, project, user):
        api_client.force_authenticate(user=user)
        branch, block_business, department_business = organization_structure
        # Create a support block and department under the same branch
        support_block = Block.objects.create(
            name="Support Block",
            code="SUP1",
            branch=branch,
            block_type=Block.BlockType.SUPPORT,
        )
        support_department = Department.objects.create(
            name="Support Dept",
            code="SUPD1",
            block=support_block,
            branch=branch,
            function=Department.DepartmentFunction.HR_ADMIN,
        )
        report_date = date.today()
        # Create employees for each block
        from apps.hrm.models import Employee as Emp

        emp_business = Emp.objects.create(
            code="MV_BUS1",
            fullname="Business Emp",
            username="bus_emp",
            email="bus@example.com",
            personal_email="bus.personal@example.com",
            phone="0900000001",
            branch=branch,
            block=block_business,
            department=department_business,
            start_date=report_date,
            attendance_code="BUS001",
            citizen_id="123456789001",
        )
        emp_support = Emp.objects.create(
            code="MV_SUP1",
            fullname="Support Emp",
            username="sup_emp",
            email="sup@example.com",
            personal_email="sup.personal@example.com",
            phone="0900000002",
            branch=branch,
            block=support_block,
            department=support_department,
            start_date=report_date,
            attendance_code="SUP001",
            citizen_id="123456789002",
        )
        # One attendance in business block
        AttendanceDailyReport.objects.create(
            employee=emp_business,
            report_date=report_date,
            branch_id=branch.id,
            block_id=block_business.id,
            department_id=department_business.id,
            project=project,
            attendance_method=AttendanceType.GEOLOCATION,
        )
        # One attendance in support block
        AttendanceDailyReport.objects.create(
            employee=emp_support,
            report_date=report_date,
            branch_id=branch.id,
            block_id=support_block.id,
            department_id=support_department.id,
            project=project,
            attendance_method=AttendanceType.GEOLOCATION,
        )

        url = "/api/hrm/attendance-reports/by-project/"
        response = api_client.get(
            url,
            {"attendance_date": report_date.strftime("%Y-%m-%d"), "block_type": Block.BlockType.SUPPORT},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["total"] == 1
        assert len(data["projects"]) == 1
        assert data["projects"][0]["count"] == 1

    def test_by_project_invalid_block_type_returns_400_envelope(self, api_client, user):
        api_client.force_authenticate(user=user)
        url = "/api/hrm/attendance-reports/by-project/"
        response = api_client.get(url, {"block_type": "invalid"})
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] is not None

    def test_by_project_organization_with_project_filter(self, api_client, employee, project, user):
        api_client.force_authenticate(user=user)
        report_date = date.today()
        # Two reports for two different projects using different employees to avoid unique constraint
        other_project = Project.objects.create(name="Other Project", code="OP")
        AttendanceDailyReport.objects.create(
            employee=employee,
            report_date=report_date,
            branch_id=employee.branch_id,
            block_id=employee.block_id,
            department_id=employee.department_id,
            project=project,
            attendance_method=AttendanceType.GEOLOCATION,
        )
        # Create another employee in same org
        from apps.hrm.models import Employee as Emp

        other_employee = Emp.objects.create(
            code="MV_OTHER_ATT",
            fullname="Other Attendance Emp",
            username="other_att",
            email="other_att@example.com",
            personal_email="other_att.personal@example.com",
            phone="0900000003",
            branch=employee.branch,
            block=employee.block,
            department=employee.department,
            start_date=report_date,
            attendance_code="OA001",
            citizen_id="123456789003",
        )
        AttendanceDailyReport.objects.create(
            employee=other_employee,
            report_date=report_date,
            branch_id=other_employee.branch_id,
            block_id=other_employee.block_id,
            department_id=other_employee.department_id,
            project=other_project,
            attendance_method=AttendanceType.GEOLOCATION,
        )

        url = "/api/hrm/attendance-reports/by-project-organization/"
        response = api_client.get(url, {"attendance_date": report_date.strftime("%Y-%m-%d"), "project": project.id})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["total"] == 1
        assert len(data["children"]) == 1
        assert data["children"][0]["count"] == 1
