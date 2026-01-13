import pytest
from datetime import date
from django.utils import timezone
from apps.hrm.models import (
    Employee,
    StaffGrowthReport,
    StaffGrowthEventLog,
    EmployeeWorkHistory,
    Branch,
    Block,
    Department
)
from apps.core.models import Province, AdministrativeUnit
from apps.hrm.tasks.reports_hr.helpers import _record_staff_growth_event

@pytest.mark.django_db
class TestStaffGrowthReportDistinctCount:
    """Test that event counts are distinct per employee per timeframe."""

    @pytest.fixture
    def org_structure(self, db):
        province = Province.objects.create(
            name="Hanoi",
            code="HNO",
            # country_id=1,
            level=Province.ProvinceLevel.CENTRAL_CITY
        )
        province_unit = AdministrativeUnit.objects.create(
            name="Hanoi",
            code="HNO",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            parent_province=province,
        )

        branch = Branch.objects.create(
            name="Test Branch",
            code="TB",
            province=province,
            administrative_unit=province_unit,
        )
        block = Block.objects.create(
            name="Test Block",
            branch=branch,
            code="TBL",
            block_type=Block.BlockType.BUSINESS
        )
        department = Department.objects.create(
            name="Test Dept",
            block=block,
            branch=branch,
            code="TD",
            function=Department.DepartmentFunction.BUSINESS
        )
        return branch, block, department

    @pytest.fixture
    def employee(self, db, org_structure):
        branch, block, department = org_structure
        return Employee.objects.create(
            fullname="Test Employee",
            code="MV000001",
            username="testuser", # Added username
            email="testuser@example.com", # Added email
            personal_email="personal@example.com", # Added personal_email
            phone="0900000001", # Added phone
            citizen_id="001000000001", # Added citizen_id
            branch=branch,
            block=block,
            department=department,
            start_date=date(2025, 1, 1),
            gender=Employee.Gender.MALE
        )

    def test_same_employee_multiple_resignations_counted_once(self, db, org_structure, employee):
        """Employee with 2 resignations in same month counted once."""
        branch, block, department = org_structure

        # Simulate 2 resignation events in same month
        _record_staff_growth_event(
            employee, "resignation", date(2026, 1, 5),
            branch, block, department
        )

        # Check intermediate state
        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
        )
        assert report.num_resignations == 1

        # Second event
        _record_staff_growth_event(
            employee, "resignation", date(2026, 1, 10),
            branch, block, department
        )

        # Check monthly report
        report.refresh_from_db()
        assert report.num_resignations == 1  # Still 1!

        # Verify Logs
        assert StaffGrowthEventLog.objects.filter(
            report=report, employee=employee, event_type="resignation"
        ).count() == 1

    def test_different_employees_counted_separately(self, db, org_structure):
        """Different employees counted separately."""
        branch, block, department = org_structure

        emp1 = Employee.objects.create(
            fullname="Emp 1", code="MV001",
            username="user1", email="user1@example.com",
            personal_email="personal1@example.com", phone="0900000002", citizen_id="001000000002",
            branch=branch, block=block, department=department, start_date=date(2025,1,1)
        )
        emp2 = Employee.objects.create(
            fullname="Emp 2", code="MV002",
            username="user2", email="user2@example.com",
            personal_email="personal2@example.com", phone="0900000003", citizen_id="001000000003",
            branch=branch, block=block, department=department, start_date=date(2025,1,1)
        )

        _record_staff_growth_event(emp1, "resignation", date(2026, 1, 5), branch, block, department)
        _record_staff_growth_event(emp2, "resignation", date(2026, 1, 10), branch, block, department)

        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
        )
        assert report.num_resignations == 2

    def test_same_employee_different_months_counted_separately(self, db, org_structure, employee):
        """Same employee in different months counted in each month."""
        branch, block, department = org_structure

        _record_staff_growth_event(employee, "resignation", date(2026, 1, 5), branch, block, department)
        _record_staff_growth_event(employee, "resignation", date(2026, 2, 5), branch, block, department)

        jan_report = StaffGrowthReport.objects.get(timeframe_key="01/2026", timeframe_type="month")
        feb_report = StaffGrowthReport.objects.get(timeframe_key="02/2026", timeframe_type="month")

        assert jan_report.num_resignations == 1
        assert feb_report.num_resignations == 1

    def test_weekly_and_monthly_updated_together(self, db, org_structure, employee):
        """Both weekly and monthly reports updated for each event."""
        branch, block, department = org_structure
        event_date = date(2026, 1, 5) # Week 2 of 2026 (ISO)

        _record_staff_growth_event(employee, "resignation", event_date, branch, block, department)

        # ISO Calendar: 2026-01-05 is Monday.
        # Week 1 2026 starts Dec 29 2025.
        # 2026-01-05 is in Week 2.
        week_key = f"W{event_date.isocalendar()[1]:02d}-{event_date.year}"

        weekly = StaffGrowthReport.objects.filter(timeframe_type="week", timeframe_key=week_key)
        monthly = StaffGrowthReport.objects.filter(timeframe_type="month", timeframe_key="01/2026")

        assert weekly.exists()
        assert monthly.exists()

        assert weekly.first().num_resignations == 1
        assert monthly.first().num_resignations == 1

    def test_deduplication_across_event_types(self, db, org_structure, employee):
        """Different event types for same employee are counted independently."""
        branch, block, department = org_structure

        # Employee transfers AND resigns in same month (unlikely but possible sequence: transfer -> resign)
        _record_staff_growth_event(employee, "transfer", date(2026, 1, 5), branch, block, department)
        _record_staff_growth_event(employee, "resignation", date(2026, 1, 10), branch, block, department)

        report = StaffGrowthReport.objects.get(timeframe_key="01/2026", timeframe_type="month")

        assert report.num_transfers == 1
        assert report.num_resignations == 1

        # Verify logs
        assert StaffGrowthEventLog.objects.filter(report=report, employee=employee).count() == 2
