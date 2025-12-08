"""Tests to verify OS employees are excluded from HR reports.

This module tests that employees with code_type="OS" are properly excluded
from StaffGrowthReport and EmployeeStatusBreakdownReport.
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    Position,
    StaffGrowthReport,
)
from apps.hrm.tasks.reports_hr.helpers import (
    _aggregate_employee_status_for_date,
    _aggregate_staff_growth_for_date,
    _increment_employee_status,
    _increment_staff_growth,
)


class TestOSEmployeeExclusion(TestCase):
    """Test cases for OS employee exclusion from reports."""

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
        self.position = Position.objects.create(code="POS01", name="Position 1")

        # Create regular employee (MV)
        self.mv_employee = Employee.objects.create(
            code="MV001",
            code_type=Employee.CodeType.MV,
            fullname="MV Employee",
            username="mvuser",
            email="mv@example.com",
            phone="0123456789",
            citizen_id="001234567890",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
        )

        # Create OS employee
        self.os_employee = Employee.objects.create(
            code="OS001",
            code_type=Employee.CodeType.OS,
            fullname="OS Employee",
            username="osuser",
            email="os@example.com",
            phone="0987654321",
            citizen_id="009876543210",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
        )

        self.report_date = date.today()

    def test_aggregate_staff_growth_excludes_os_employees(self):
        """Test that batch aggregation excludes OS employees from StaffGrowthReport."""
        # Create work history for MV employee
        EmployeeWorkHistory.objects.create(
            employee=self.mv_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create work history for OS employee
        EmployeeWorkHistory.objects.create(
            employee=self.os_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - aggregate the report
        _aggregate_staff_growth_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - only MV employee's resignation should be counted
        report = StaffGrowthReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.num_resignations, 1, "Should count only MV employee resignation")

    def test_aggregate_employee_status_excludes_os_employees(self):
        """Test that batch aggregation excludes OS employees from EmployeeStatusBreakdownReport."""
        # Create work history for MV employee
        EmployeeWorkHistory.objects.create(
            employee=self.mv_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create work history for OS employee
        EmployeeWorkHistory.objects.create(
            employee=self.os_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - aggregate the report
        _aggregate_employee_status_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - only MV employee should be counted
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_active, 1, "Should count only MV employee as active")
        self.assertEqual(report.total_not_resigned, 1, "Total should be 1 (MV employee only)")

    @patch("apps.hrm.tasks.reports_hr.helpers._process_staff_growth_change")
    def test_increment_staff_growth_skips_os_employees(self, mock_process):
        """Test that incremental update skips OS employees in staff growth."""
        # Arrange - snapshot with OS employee
        snapshot = {
            "previous": None,
            "current": {
                "date": self.report_date,
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
                "status": Employee.Status.RESIGNED,
                "previous_data": {},
                "employee_code_type": Employee.CodeType.OS,
            },
        }

        # Act
        _increment_staff_growth("create", snapshot)

        # Assert - should not process OS employee
        mock_process.assert_not_called()

    @patch("apps.hrm.tasks.reports_hr.helpers._process_staff_growth_change")
    def test_increment_staff_growth_processes_mv_employees(self, mock_process):
        """Test that incremental update processes MV employees in staff growth."""
        # Arrange - snapshot with MV employee
        snapshot = {
            "previous": None,
            "current": {
                "date": self.report_date,
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
                "status": Employee.Status.RESIGNED,
                "previous_data": {},
                "employee_code_type": Employee.CodeType.MV,
            },
        }

        # Act
        _increment_staff_growth("create", snapshot)

        # Assert - should process MV employee
        mock_process.assert_called_once()

    @patch("apps.hrm.tasks.reports_hr.helpers._aggregate_employee_status_for_date")
    def test_increment_employee_status_skips_os_employees(self, mock_aggregate):
        """Test that incremental update skips OS employees in status breakdown."""
        # Arrange - snapshot with OS employee
        snapshot = {
            "previous": None,
            "current": {
                "date": self.report_date,
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
                "status": Employee.Status.ACTIVE,
                "previous_data": {},
                "employee_code_type": Employee.CodeType.OS,
            },
        }

        # Act
        _increment_employee_status("create", snapshot)

        # Assert - should not aggregate for OS employee
        mock_aggregate.assert_not_called()

    @patch("apps.hrm.tasks.reports_hr.helpers._aggregate_employee_status_for_date")
    def test_increment_employee_status_processes_mv_employees(self, mock_aggregate):
        """Test that incremental update processes MV employees in status breakdown."""
        # Arrange - snapshot with MV employee
        snapshot = {
            "previous": None,
            "current": {
                "date": self.report_date,
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
                "status": Employee.Status.ACTIVE,
                "previous_data": {},
                "employee_code_type": Employee.CodeType.MV,
            },
        }

        # Act
        _increment_employee_status("create", snapshot)

        # Assert - should aggregate for MV employee
        mock_aggregate.assert_called_once()

    def test_multiple_code_types_in_staff_growth_report(self):
        """Test staff growth report with multiple employee types (MV, CTV, OS)."""
        # Create CTV employee
        ctv_employee = Employee.objects.create(
            code="CTV001",
            code_type=Employee.CodeType.CTV,
            fullname="CTV Employee",
            username="ctvuser",
            email="ctv@example.com",
            phone="0111222333",
            citizen_id="001112223334",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
        )

        # Create work history for all three types
        for employee in [self.mv_employee, ctv_employee, self.os_employee]:
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

        # Assert - should count MV and CTV but not OS
        report = StaffGrowthReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.num_resignations, 2, "Should count MV and CTV resignations only, not OS")

    def test_multiple_code_types_in_employee_status_report(self):
        """Test employee status report with multiple employee types (MV, CTV, OS)."""
        # Create CTV employee
        ctv_employee = Employee.objects.create(
            code="CTV001",
            code_type=Employee.CodeType.CTV,
            fullname="CTV Employee",
            username="ctvuser",
            email="ctv@example.com",
            phone="0111222333",
            citizen_id="001112223334",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now().date(),
        )

        # Create work history for all three types
        for employee in [self.mv_employee, ctv_employee, self.os_employee]:
            EmployeeWorkHistory.objects.create(
                employee=employee,
                date=self.report_date,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.ACTIVE,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

        # Act - aggregate the report
        _aggregate_employee_status_for_date(self.report_date, self.branch, self.block, self.department)

        # Assert - should count MV and CTV but not OS
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_active, 2, "Should count MV and CTV as active, not OS")
        self.assertEqual(report.total_not_resigned, 2, "Total should be 2 (MV and CTV only)")
