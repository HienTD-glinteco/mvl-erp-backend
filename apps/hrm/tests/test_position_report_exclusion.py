"""Tests to verify positions with include_in_employee_report=False are excluded from HR reports.

This module tests that employees whose position has include_in_employee_report=False
are properly excluded from StaffGrowthReport, EmployeeStatusBreakdownReport,
and EmployeeResignedReasonReport.
"""

from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
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
    _aggregate_staff_growth_for_date,
)


class TestPositionReportExclusion(TestCase):
    """Test cases for position-based exclusion from reports."""

    def setUp(self):
        """Set up test data."""
        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="BR01",
            name="Branch 1",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="BL01", name="Block 1", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="DP01",
            name="Department 1",
            block=self.block,
            branch=self.branch,
            function=Department.DepartmentFunction.BUSINESS,
        )

        # Create position included in reports
        self.included_position = Position.objects.create(
            code="POS01", name="Regular Position", include_in_employee_report=True
        )

        # Create position excluded from reports
        self.excluded_position = Position.objects.create(
            code="POS02", name="Excluded Position", include_in_employee_report=False
        )

        # Create employee with included position
        self.included_employee = Employee.objects.create(
            code="MV001",
            code_type=Employee.CodeType.MV,
            fullname="Included Employee",
            username="includeduser",
            email="included@example.com",
            phone="0123456789",
            citizen_id="001234567890",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.included_position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
            personal_email="included.personal@example.com",
        )

        # Create employee with excluded position
        self.excluded_employee = Employee.objects.create(
            code="MV002",
            code_type=Employee.CodeType.MV,
            fullname="Excluded Employee",
            username="excludeduser",
            email="excluded@example.com",
            phone="0987654321",
            citizen_id="009876543210",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.excluded_position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
            personal_email="excluded.personal@example.com",
        )

        self.report_date = date.today()

    def test_aggregate_staff_growth_excludes_position(self):
        """Test that staff growth aggregation excludes employees with position.include_in_employee_report=False."""
        # Create work history for included employee
        EmployeeWorkHistory.objects.create(
            employee=self.included_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create work history for excluded employee
        EmployeeWorkHistory.objects.create(
            employee=self.excluded_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - aggregate the report
        _aggregate_staff_growth_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - only included employee's resignation should be counted
        report = StaffGrowthReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.num_resignations, 1, "Should count only employee with included position")

    def test_aggregate_employee_status_excludes_position(self):
        """Test that employee status aggregation excludes employees with position.include_in_employee_report=False."""
        # Create work history for included employee
        EmployeeWorkHistory.objects.create(
            employee=self.included_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create work history for excluded employee
        EmployeeWorkHistory.objects.create(
            employee=self.excluded_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - aggregate the report
        _aggregate_employee_status_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - only included employee should be counted
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_active, 1, "Should count only employee with included position")
        self.assertEqual(report.total_not_resigned, 1, "Total should be 1 (included employee only)")

    def test_aggregate_resigned_reason_excludes_position(self):
        """Test that resigned reason aggregation excludes employees with position.include_in_employee_report=False."""
        # Create work history for included employee with resignation
        EmployeeWorkHistory.objects.create(
            employee=self.included_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_PERSONAL,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create work history for excluded employee with resignation
        EmployeeWorkHistory.objects.create(
            employee=self.excluded_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_PERSONAL,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - aggregate the report
        _aggregate_employee_resigned_reason_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - only included employee should be counted
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 1, "Should count only employee with included position")
        self.assertEqual(report.voluntary_personal, 1, "Should count resignation reason for included employee only")

    def test_multiple_employees_with_mixed_positions(self):
        """Test staff growth report with multiple employees having different position settings."""
        # Create another employee with included position
        another_included = Employee.objects.create(
            code="MV003",
            code_type=Employee.CodeType.MV,
            fullname="Another Included Employee",
            username="anotherincluded",
            email="anotherincluded@example.com",
            phone="0111222333",
            citizen_id="001112223334",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.included_position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
            personal_email="another.included.personal@example.com",
        )

        # Create work history for all three employees
        for employee in [self.included_employee, another_included, self.excluded_employee]:
            EmployeeWorkHistory.objects.create(
                employee=employee,
                date=self.report_date,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

        # Act - aggregate the report
        _aggregate_staff_growth_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - should count only employees with included positions
        report = StaffGrowthReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.num_resignations, 2, "Should count only employees with included positions")

    def test_employee_with_null_position(self):
        """Test that employees with null position are included in reports."""
        # Create employee with null position (position is nullable)
        null_position_employee = Employee.objects.create(
            code="MV004",
            code_type=Employee.CodeType.MV,
            fullname="Null Position Employee",
            username="nullposition",
            email="nullposition@example.com",
            phone="0444555666",
            citizen_id="004445556667",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=None,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
            personal_email="nullposition.personal@example.com",
        )

        # Create work history
        EmployeeWorkHistory.objects.create(
            employee=null_position_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - aggregate the report
        _aggregate_employee_status_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - employee with null position should be included
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        # Should count the null position employee
        self.assertGreaterEqual(report.count_active, 1, "Should include employee with null position")
