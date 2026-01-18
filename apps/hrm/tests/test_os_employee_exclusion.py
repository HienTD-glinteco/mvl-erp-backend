"""Tests to verify OS employees are excluded from HR reports.

This module tests that employees with code_type="OS" are properly excluded
from StaffGrowthReport and EmployeeStatusBreakdownReport via signal-based
event processing.
"""

from datetime import date

import pytest

from apps.hrm.models import (
    Employee,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    StaffGrowthReport,
)
from apps.hrm.tasks.reports_hr.helpers import (
    _aggregate_employee_status_for_date,
    _increment_staff_growth,
)


@pytest.mark.django_db
class TestOSEmployeeExclusion:
    """Test cases for OS employee exclusion from reports."""

    @pytest.fixture(autouse=True)
    def enable_celery_eager(self, settings):
        """Enable eager execution for Celery tasks."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

    @pytest.fixture
    def setup_data(self, branch, block, department, position):
        """Set up common test data."""
        return {
            "branch": branch,
            "block": block,
            "department": department,
            "position": position,
        }

    @pytest.fixture
    def mv_employee(self, employee_factory, setup_data):
        """Create a regular MV employee."""
        return employee_factory(
            code="MV001",
            code_type=Employee.CodeType.MV,
            fullname="MV Employee",
            branch=setup_data["branch"],
            block=setup_data["block"],
            department=setup_data["department"],
            position=setup_data["position"],
        )

    @pytest.fixture
    def os_employee(self, employee_factory, setup_data):
        """Create an OS employee."""
        return employee_factory(
            code="OS001",
            code_type=Employee.CodeType.OS,
            fullname="OS Employee",
            branch=setup_data["branch"],
            block=setup_data["block"],
            department=setup_data["department"],
            position=setup_data["position"],
        )

    def test_signal_excludes_os_employee_from_staff_growth(self, setup_data, mv_employee, os_employee):
        """Test that signal-triggered processing excludes OS employees from StaffGrowthReport."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]

        # Create work history for MV employee (triggers signal)
        EmployeeWorkHistory.objects.create(
            employee=mv_employee,
            date=date(2026, 1, 15),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=branch,
            block=block,
            department=dept,
        )

        # Create work history for OS employee (triggers signal but should be skipped)
        EmployeeWorkHistory.objects.create(
            employee=os_employee,
            date=date(2026, 1, 15),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=branch,
            block=block,
            department=dept,
        )

        # Check monthly report - should only count MV employee
        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=dept,
        )
        assert report.num_resignations == 1, "Should count only MV employee resignation"

    def test_aggregate_employee_status_excludes_os_employees(self, setup_data, mv_employee, os_employee):
        """Test that employee status aggregation excludes OS employees."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]
        report_date = date(2026, 1, 15)

        # Create work history for MV employee
        EmployeeWorkHistory.objects.create(
            employee=mv_employee,
            date=report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=branch,
            block=block,
            department=dept,
        )

        # Create work history for OS employee
        EmployeeWorkHistory.objects.create(
            employee=os_employee,
            date=report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=branch,
            block=block,
            department=dept,
        )

        # Aggregate the report
        _aggregate_employee_status_for_date(report_date, branch, block, dept)

        # Should only count MV employee
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=report_date,
            branch=branch,
            block=block,
            department=dept,
        )
        assert report.count_active == 1, "Should count only MV employee as active"

    def test_increment_staff_growth_skips_os_employees(self, setup_data, os_employee):
        """Test that _increment_staff_growth skips OS employees."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]

        # Create snapshot with OS employee
        snapshot = {
            "previous": None,
            "current": {
                "id": 1,
                "date": date(2026, 1, 15),
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "branch_id": branch.id,
                "block_id": block.id,
                "department_id": dept.id,
                "status": Employee.Status.RESIGNED,
                "previous_data": {},
                "employee_code_type": Employee.CodeType.OS,
                "employee_id": os_employee.id,
            },
        }

        # This should not create any report
        _increment_staff_growth("create", snapshot)

        # No report should be created for OS employee
        assert not StaffGrowthReport.objects.filter(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=dept,
        ).exists(), "Should not create report for OS employee"

    def test_increment_staff_growth_processes_mv_employees(self, setup_data, mv_employee):
        """Test that _increment_staff_growth processes MV employees."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]

        # Create snapshot with MV employee
        snapshot = {
            "previous": None,
            "current": {
                "id": 1,
                "date": date(2026, 1, 15),
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "branch_id": branch.id,
                "block_id": block.id,
                "department_id": dept.id,
                "status": Employee.Status.RESIGNED,
                "previous_data": {},
                "employee_code_type": Employee.CodeType.MV,
                "employee_id": mv_employee.id,
            },
        }

        # This should create a report
        _increment_staff_growth("create", snapshot)

        # Report should be created for MV employee
        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=dept,
        )
        assert report.num_resignations == 1, "Should count MV employee resignation"

    def test_multiple_code_types_mixed(self, setup_data, mv_employee, os_employee, employee_factory):
        """Test staff growth report with multiple employee types."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]

        # Create CTV employee
        ctv_employee = employee_factory(
            code="CTV001",
            code_type=Employee.CodeType.CTV,
            fullname="CTV Employee",
            branch=branch,
            block=block,
            department=dept,
        )

        # Create work history for all three (via signals)
        for emp in [mv_employee, ctv_employee, os_employee]:
            EmployeeWorkHistory.objects.create(
                employee=emp,
                date=date(2026, 1, 15),
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                branch=branch,
                block=block,
                department=dept,
            )

        # Should count MV and CTV but not OS
        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=dept,
        )
        assert report.num_resignations == 2, "Should count MV and CTV resignations only"
