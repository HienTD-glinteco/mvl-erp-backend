"""Tests to verify positions with include_in_employee_report=False are excluded from HR reports.

This module tests that employees whose position has include_in_employee_report=False
are properly excluded from StaffGrowthReport, EmployeeStatusBreakdownReport,
and EmployeeResignedReasonReport via signal-based event processing.
"""

from datetime import date

import pytest

from apps.hrm.models import (
    Employee,
    EmployeeResignedReasonReport,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    Position,
    StaffGrowthReport,
)
from apps.hrm.tasks.reports_hr.helpers import (
    _aggregate_employee_resigned_reason_for_date,
    _aggregate_employee_status_for_date,
)


@pytest.mark.django_db
class TestPositionReportExclusion:
    """Test cases for position-based exclusion from reports."""

    @pytest.fixture(autouse=True)
    def enable_celery_eager(self, settings):
        """Enable eager execution for Celery tasks."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

    @pytest.fixture
    def excluded_position(self):
        """Create a position excluded from reports."""
        return Position.objects.create(
            code="POS_EXCLUDED",
            name="Excluded Position",
            include_in_employee_report=False,
        )

    @pytest.fixture
    def setup_data(self, branch, block, department, position):
        """Set up common test data."""
        return {
            "branch": branch,
            "block": block,
            "department": department,
            "position": position,  # included position from conftest
        }

    @pytest.fixture
    def included_employee(self, employee_factory, setup_data):
        """Create an employee with included position."""
        return employee_factory(
            code="MV_INCLUDED",
            fullname="Included Employee",
            branch=setup_data["branch"],
            block=setup_data["block"],
            department=setup_data["department"],
            position=setup_data["position"],
        )

    @pytest.fixture
    def excluded_employee(self, employee_factory, setup_data, excluded_position):
        """Create an employee with excluded position."""
        return employee_factory(
            code="MV_EXCLUDED",
            fullname="Excluded Employee",
            branch=setup_data["branch"],
            block=setup_data["block"],
            department=setup_data["department"],
            position=excluded_position,
        )

    def test_signal_excludes_position_from_staff_growth(self, setup_data, included_employee, excluded_employee):
        """Test that signal-triggered processing excludes employees with excluded positions."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]

        # Create work history for included employee (triggers signal)
        EmployeeWorkHistory.objects.create(
            employee=included_employee,
            date=date(2026, 1, 15),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=branch,
            block=block,
            department=dept,
        )

        # Create work history for excluded employee (triggers signal but should be skipped)
        EmployeeWorkHistory.objects.create(
            employee=excluded_employee,
            date=date(2026, 1, 15),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=branch,
            block=block,
            department=dept,
        )

        # Check monthly report - should only count included employee
        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=dept,
        )
        assert report.num_resignations == 1, "Should count only employee with included position"

    def test_aggregate_employee_status_excludes_position(self, setup_data, included_employee, excluded_employee):
        """Test that employee status aggregation excludes employees with excluded positions."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]
        report_date = date(2026, 1, 15)

        # Create work history for both employees
        for emp in [included_employee, excluded_employee]:
            EmployeeWorkHistory.objects.create(
                employee=emp,
                date=report_date,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.ACTIVE,
                branch=branch,
                block=block,
                department=dept,
            )

        # Aggregate the report
        _aggregate_employee_status_for_date(report_date, branch, block, dept)

        # Should only count included employee
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=report_date,
            branch=branch,
            block=block,
            department=dept,
        )
        assert report.count_active == 1, "Should count only employee with included position"

    def test_aggregate_resigned_reason_excludes_position(self, setup_data, included_employee, excluded_employee):
        """Test that resigned reason aggregation excludes employees with excluded positions."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]
        report_date = date(2026, 1, 15)

        # Create work history for both employees with resignation
        for emp in [included_employee, excluded_employee]:
            EmployeeWorkHistory.objects.create(
                employee=emp,
                date=report_date,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                resignation_reason=Employee.ResignationReason.VOLUNTARY_PERSONAL,
                branch=branch,
                block=block,
                department=dept,
            )

        # Aggregate the report
        _aggregate_employee_resigned_reason_for_date(report_date, branch, block, dept)

        # Should only count included employee
        report = EmployeeResignedReasonReport.objects.get(
            report_date=report_date,
            branch=branch,
            block=block,
            department=dept,
        )
        assert report.count_resigned == 1, "Should count only employee with included position"
        assert report.voluntary_personal == 1

    def test_multiple_employees_with_mixed_positions(
        self, setup_data, included_employee, excluded_employee, employee_factory
    ):
        """Test staff growth with multiple employees having different position settings."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]

        # Create another included employee
        another_included = employee_factory(
            code="MV_INCLUDED2",
            fullname="Another Included Employee",
            branch=branch,
            block=block,
            department=dept,
            position=setup_data["position"],
        )

        # Create work history for all three
        for emp in [included_employee, another_included, excluded_employee]:
            EmployeeWorkHistory.objects.create(
                employee=emp,
                date=date(2026, 1, 15),
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                branch=branch,
                block=block,
                department=dept,
            )

        # Should count only employees with included positions
        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=dept,
        )
        assert report.num_resignations == 2, "Should count only employees with included positions"

    def test_employee_with_null_position_included(self, setup_data, employee_factory):
        """Test that employees with null position are included in reports."""
        dept = setup_data["department"]
        branch = setup_data["branch"]
        block = setup_data["block"]
        report_date = date(2026, 1, 15)

        # Create employee with null position
        null_position_employee = employee_factory(
            code="MV_NULLPOS",
            fullname="Null Position Employee",
            branch=branch,
            block=block,
            department=dept,
            position=None,
        )

        # Create work history
        EmployeeWorkHistory.objects.create(
            employee=null_position_employee,
            date=report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=branch,
            block=block,
            department=dept,
        )

        # Aggregate the report
        _aggregate_employee_status_for_date(report_date, branch, block, dept)

        # Should include employee with null position
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=report_date,
            branch=branch,
            block=block,
            department=dept,
        )
        assert report.count_active >= 1, "Should include employee with null position"
