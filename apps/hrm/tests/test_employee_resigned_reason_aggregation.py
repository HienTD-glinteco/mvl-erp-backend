"""Tests for EmployeeResignedReasonReport aggregation logic.

These tests verify the aggregation functions that populate the
EmployeeResignedReasonReport model from EmployeeWorkHistory events.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.test import TestCase, TransactionTestCase, override_settings

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeResignedReasonReport,
    EmployeeWorkHistory,
    Position,
)
from apps.hrm.tasks.reports_hr.helpers import (
    _aggregate_employee_resigned_reason_for_date,
    _get_resignation_reason_field_name,
    _increment_employee_resigned_reason,
)


@pytest.mark.django_db
class TestGetResignationReasonFieldName(TestCase):
    """Test cases for _get_resignation_reason_field_name helper function."""

    def test_maps_all_resignation_reasons(self):
        """Test that all resignation reason enums map to field names."""
        # Arrange & Act & Assert
        for reason in Employee.ResignationReason:
            field_name = _get_resignation_reason_field_name(reason)
            self.assertIsNotNone(field_name, f"Reason {reason} should have a field mapping")
            self.assertIsInstance(field_name, str)
            # Field name should be snake_case
            self.assertTrue(field_name.islower())

    def test_agreement_termination_maps_correctly(self):
        """Test specific mapping for AGREEMENT_TERMINATION."""
        # Act
        field_name = _get_resignation_reason_field_name(Employee.ResignationReason.AGREEMENT_TERMINATION)
        
        # Assert
        self.assertEqual(field_name, "agreement_termination")

    def test_voluntary_career_change_maps_correctly(self):
        """Test specific mapping for VOLUNTARY_CAREER_CHANGE."""
        # Act
        field_name = _get_resignation_reason_field_name(Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE)
        
        # Assert
        self.assertEqual(field_name, "voluntary_career_change")


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestAggregateEmployeeResignedReasonForDate(TransactionTestCase):
    """Test cases for _aggregate_employee_resigned_reason_for_date function."""

    def setUp(self):
        """Set up test data."""
        # Clean up existing data
        EmployeeResignedReasonReport.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()

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

        self.report_date = date(2025, 11, 15)

    def test_aggregates_single_resignation_with_reason(self):
        """Test aggregation counts a single resignation with reason."""
        # Arrange
        employee = Employee.objects.create(
            code="EMP001",
            code_type=Employee.CodeType.MV,
            fullname="Test Employee",
            username="testuser1",
            email="test1@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            start_date=date(2025, 1, 1),
        )

        EmployeeWorkHistory.objects.create(
            employee=employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 1)
        self.assertEqual(report.voluntary_career_change, 1)
        self.assertEqual(report.voluntary_personal, 0)
        self.assertEqual(report.probation_fail, 0)

    def test_aggregates_multiple_resignations_same_reason(self):
        """Test aggregation counts multiple resignations with same reason."""
        # Arrange
        for i in range(3):
            employee = Employee.objects.create(
                code=f"EMP00{i+1}",
                code_type=Employee.CodeType.MV,
                fullname=f"Test Employee {i+1}",
                username=f"testuser{i+1}",
                email=f"test{i+1}@example.com",
                phone=f"012345678{i}",
                branch=self.branch,
                block=self.block,
                department=self.department,
                position=self.position,
                status=Employee.Status.RESIGNED,
                resignation_reason=Employee.ResignationReason.PROBATION_FAIL,
                start_date=date(2025, 1, 1),
            )

            EmployeeWorkHistory.objects.create(
                employee=employee,
                date=self.report_date,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                resignation_reason=Employee.ResignationReason.PROBATION_FAIL,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

        # Act
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 3)
        self.assertEqual(report.probation_fail, 3)
        self.assertEqual(report.voluntary_career_change, 0)

    def test_aggregates_multiple_resignations_different_reasons(self):
        """Test aggregation counts multiple resignations with different reasons."""
        # Arrange
        reasons = [
            Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            Employee.ResignationReason.VOLUNTARY_PERSONAL,
            Employee.ResignationReason.PROBATION_FAIL,
            Employee.ResignationReason.CONTRACT_EXPIRED,
        ]

        for i, reason in enumerate(reasons):
            employee = Employee.objects.create(
                code=f"EMP00{i+1}",
                code_type=Employee.CodeType.MV,
                fullname=f"Test Employee {i+1}",
                username=f"testuser{i+1}",
                email=f"test{i+1}@example.com",
                phone=f"012345678{i}",
                branch=self.branch,
                block=self.block,
                department=self.department,
                position=self.position,
                status=Employee.Status.RESIGNED,
                resignation_reason=reason,
                start_date=date(2025, 1, 1),
            )

            EmployeeWorkHistory.objects.create(
                employee=employee,
                date=self.report_date,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                resignation_reason=reason,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )

        # Act
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 4)
        self.assertEqual(report.voluntary_career_change, 1)
        self.assertEqual(report.voluntary_personal, 1)
        self.assertEqual(report.probation_fail, 1)
        self.assertEqual(report.contract_expired, 1)

    def test_excludes_os_employees(self):
        """Test that employees with code_type=OS are excluded from aggregation."""
        # Arrange - Create MV employee
        mv_employee = Employee.objects.create(
            code="EMP001",
            code_type=Employee.CodeType.MV,
            fullname="MV Employee",
            username="mvuser",
            email="mv@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            start_date=date(2025, 1, 1),
        )

        EmployeeWorkHistory.objects.create(
            employee=mv_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create OS employee
        os_employee = Employee.objects.create(
            code="EMP002",
            code_type=Employee.CodeType.OS,
            fullname="OS Employee",
            username="osuser",
            email="os@example.com",
            phone="0123456788",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.PROBATION_FAIL,
            start_date=date(2025, 1, 1),
        )

        EmployeeWorkHistory.objects.create(
            employee=os_employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.PROBATION_FAIL,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert - Only MV employee should be counted
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 1)
        self.assertEqual(report.voluntary_career_change, 1)
        self.assertEqual(report.probation_fail, 0)  # OS employee not counted

    def test_only_counts_resignations_on_report_date(self):
        """Test that only resignations on the specific report_date are counted."""
        # Arrange - Create resignation on different date
        employee = Employee.objects.create(
            code="EMP001",
            code_type=Employee.CodeType.MV,
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            start_date=date(2025, 1, 1),
        )

        # Create work history for different date
        different_date = date(2025, 11, 10)
        EmployeeWorkHistory.objects.create(
            employee=employee,
            date=different_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act - Aggregate for report_date (different from resignation date)
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert - No resignations should be counted
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 0)
        self.assertEqual(report.voluntary_career_change, 0)

    def test_creates_new_report_if_not_exists(self):
        """Test that aggregation creates a new report if one doesn't exist."""
        # Arrange
        employee = Employee.objects.create(
            code="EMP001",
            code_type=Employee.CodeType.MV,
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            start_date=date(2025, 1, 1),
        )

        EmployeeWorkHistory.objects.create(
            employee=employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Assert - No report exists yet
        self.assertEqual(
            EmployeeResignedReasonReport.objects.filter(
                report_date=self.report_date,
                branch=self.branch,
                block=self.block,
                department=self.department,
            ).count(),
            0,
        )

        # Act
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert - Report should be created
        self.assertEqual(
            EmployeeResignedReasonReport.objects.filter(
                report_date=self.report_date,
                branch=self.branch,
                block=self.block,
                department=self.department,
            ).count(),
            1,
        )

    def test_updates_existing_report(self):
        """Test that aggregation updates an existing report."""
        # Arrange - Create existing report
        EmployeeResignedReasonReport.objects.create(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=5,
            voluntary_career_change=5,
        )

        # Create new resignation
        employee = Employee.objects.create(
            code="EMP001",
            code_type=Employee.CodeType.MV,
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.PROBATION_FAIL,
            start_date=date(2025, 1, 1),
        )

        EmployeeWorkHistory.objects.create(
            employee=employee,
            date=self.report_date,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.PROBATION_FAIL,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act
        _aggregate_employee_resigned_reason_for_date(
            self.report_date, self.branch, self.block, self.department
        )

        # Assert - Report should be updated (not old values)
        report = EmployeeResignedReasonReport.objects.get(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_resigned, 1)  # Re-aggregated, not 5+1
        self.assertEqual(report.probation_fail, 1)
        self.assertEqual(report.voluntary_career_change, 0)  # Reset


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestIncrementEmployeeResignedReason(TransactionTestCase):
    """Test cases for _increment_employee_resigned_reason function."""

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

        self.report_date = date(2025, 11, 15)

    @patch("apps.hrm.tasks.reports_hr.helpers._aggregate_employee_resigned_reason_for_date")
    def test_calls_aggregation_for_create_event(self, mock_aggregate):
        """Test that create event calls aggregation function."""
        # Arrange
        snapshot = {
            "current": {
                "date": self.report_date,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
            },
            "previous": None,
        }

        # Act
        _increment_employee_resigned_reason("create", snapshot)

        # Assert
        mock_aggregate.assert_called_once_with(
            self.report_date, self.branch, self.block, self.department
        )

    @patch("apps.hrm.tasks.reports_hr.helpers._aggregate_employee_resigned_reason_for_date")
    def test_calls_aggregation_for_update_event(self, mock_aggregate):
        """Test that update event calls aggregation function."""
        # Arrange
        snapshot = {
            "current": {
                "date": self.report_date,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
            },
            "previous": {
                "date": self.report_date,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
            },
        }

        # Act
        _increment_employee_resigned_reason("update", snapshot)

        # Assert
        mock_aggregate.assert_called_once()

    @patch("apps.hrm.tasks.reports_hr.helpers._aggregate_employee_resigned_reason_for_date")
    def test_calls_aggregation_for_delete_event(self, mock_aggregate):
        """Test that delete event calls aggregation function."""
        # Arrange
        snapshot = {
            "current": None,
            "previous": {
                "date": self.report_date,
                "branch_id": self.branch.id,
                "block_id": self.block.id,
                "department_id": self.department.id,
            },
        }

        # Act
        _increment_employee_resigned_reason("delete", snapshot)

        # Assert
        mock_aggregate.assert_called_once_with(
            self.report_date, self.branch, self.block, self.department
        )

    def test_handles_missing_org_units_gracefully(self):
        """Test that function handles missing organizational units gracefully."""
        # Arrange - Use non-existent IDs
        snapshot = {
            "current": {
                "date": self.report_date,
                "branch_id": 99999,
                "block_id": 99999,
                "department_id": 99999,
            },
            "previous": None,
        }

        # Act & Assert - Should not raise exception
        try:
            _increment_employee_resigned_reason("create", snapshot)
        except Exception as e:
            self.fail(f"Function should handle missing org units gracefully, but raised: {e}")
