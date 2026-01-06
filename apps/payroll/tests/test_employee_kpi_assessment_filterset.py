"""Tests for EmployeeKPIAssessmentFilterSet."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.payroll.api.filtersets import EmployeeKPIAssessmentFilterSet
from apps.payroll.models import (
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class TestEmployeeKPIAssessmentFilterSet:
    """Test cases for EmployeeKPIAssessmentFilterSet."""

    @pytest.fixture(autouse=True)
    def setup(self, employee, position):
        """Set up test data."""
        self.employee = employee
        self.position = position

        # Create another employee with different position

        from apps.hrm.models import Employee, Position

        self.position2 = Position.objects.create(
            name="Manager",
            code="MGR",
        )
        self.employee2 = Employee.objects.create(
            code="E002",
            fullname="Jane Smith",
            username="emp002",
            email="emp002@example.com",
            employee_type="fulltime",
            branch=employee.branch,
            block=employee.block,
            department=employee.department,
            position=self.position2,
            start_date=date(2025, 1, 1),
            personal_email="emp002.personal@example.com",
        )

        # Create KPI config
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                    {"min": 60, "max": 80, "possible_codes": ["C"], "label": "Average"},
                    {"min": 80, "max": 90, "possible_codes": ["B"], "label": "Good"},
                    {"min": 90, "max": 100, "possible_codes": ["A"], "label": "Excellent"},
                ],
            }
        )

        # Create assessment period
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Create assessments with different grades
        self.assessment1 = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
            grade_manager="A",
            grade_hrm="A",
            total_possible_score=Decimal("100.00"),
            total_manager_score=Decimal("95.00"),
        )

        self.assessment2 = EmployeeKPIAssessment.objects.create(
            employee=self.employee2,
            period=self.period,
            grade_manager="B",
            grade_hrm="C",
            total_possible_score=Decimal("100.00"),
            total_manager_score=Decimal("85.00"),
        )

    def test_filter_by_employee_position(self):
        """Test filtering by employee position ID."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"employee_position": self.position.id},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().employee == self.employee

    def test_filter_by_employee_position_different_position(self):
        """Test filtering by different employee position ID."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"employee_position": self.position2.id},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().employee == self.employee2

    def test_filter_by_grade_manager_single_value(self):
        """Test filtering by grade_manager with single value."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_manager": "A"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().grade_manager == "A"

    def test_filter_by_grade_manager_multiple_values(self):
        """Test filtering by grade_manager with multiple values (comma-separated)."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_manager": "A,B"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 2
        grades = [assessment.grade_manager for assessment in result]
        assert "A" in grades
        assert "B" in grades

    def test_filter_by_grade_manager_multiple_values_with_spaces(self):
        """Test filtering by grade_manager with spaces around commas."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_manager": "A, B"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 2

    def test_filter_by_grade_hrm_single_value(self):
        """Test filtering by grade_hrm with single value."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_hrm": "A"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().grade_hrm == "A"

    def test_filter_by_grade_hrm_multiple_values(self):
        """Test filtering by grade_hrm with multiple values (comma-separated)."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_hrm": "A,C"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 2
        grades = [assessment.grade_hrm for assessment in result]
        assert "A" in grades
        assert "C" in grades

    def test_filter_by_grade_hrm_empty_value(self):
        """Test filtering by grade_hrm with empty value returns all."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_hrm": ""},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 2

    def test_filter_by_grade_manager_no_match(self):
        """Test filtering by grade_manager with no matching results."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"grade_manager": "D"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 0

    def test_combine_employee_position_and_grade_filters(self):
        """Test combining employee_position with grade filters."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={
                "employee_position": self.position.id,
                "grade_manager": "A",
            },
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().employee == self.employee
        assert result.first().grade_manager == "A"

    def test_filter_position_field_still_works(self):
        """Test that existing position filter still works (for backward compatibility)."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"position": self.position.id},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().employee == self.employee

    def test_filterset_with_all_filters(self):
        """Test using multiple filters together."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={
                "employee": self.employee.id,
                "employee_position": self.position.id,
                "grade_manager": "A",
                "grade_hrm": "A",
                "finalized": False,
            },
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first() == self.assessment1


@pytest.mark.django_db
class TestEmployeeKPIAssessmentFilterSetStatus:
    """Test cases for status filter in EmployeeKPIAssessmentFilterSet."""

    @pytest.fixture(autouse=True)
    def setup(self, employee, position):
        """Set up test data."""
        self.employee = employee
        self.position = position

        # Create KPI config
        from apps.payroll.models import KPIConfig

        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                    {"min": 60, "max": 80, "possible_codes": ["C"], "label": "Average"},
                    {"min": 80, "max": 90, "possible_codes": ["B"], "label": "Good"},
                    {"min": 90, "max": 100, "possible_codes": ["A"], "label": "Excellent"},
                ],
            }
        )

        # Create assessment period
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Create assessments with different statuses
        # Note: Status might auto-update based on assessment completion, so we test actual behavior
        self.assessment_new = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
            total_possible_score=Decimal("100.00"),
        )
        # Force status to NEW without triggering auto-updates
        EmployeeKPIAssessment.objects.filter(id=self.assessment_new.id).update(
            status=EmployeeKPIAssessment.StatusChoices.NEW
        )
        self.assessment_new.refresh_from_db()

        # Create another employee for additional test data
        from datetime import date as dt

        from apps.hrm.models import Employee

        self.employee2 = Employee.objects.create(
            code="E002",
            fullname="Jane Smith",
            username="emp002",
            email="emp002@example.com",
            employee_type="fulltime",
            branch=employee.branch,
            block=employee.block,
            department=employee.department,
            position=position,
            start_date=dt(2025, 1, 1),
            personal_email="emp002.status@example.com",
        )

        # Create another period for second assessment
        self.period2 = KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        self.assessment_waiting = EmployeeKPIAssessment.objects.create(
            employee=self.employee2,
            period=self.period2,
            total_possible_score=Decimal("100.00"),
        )
        # Force status to WAITING_MANAGER
        EmployeeKPIAssessment.objects.filter(id=self.assessment_waiting.id).update(
            status=EmployeeKPIAssessment.StatusChoices.WAITING_MANAGER
        )
        self.assessment_waiting.refresh_from_db()

        # Create third assessment with completed status
        self.assessment_completed = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period2,
            grade_manager="A",
            total_possible_score=Decimal("100.00"),
            total_manager_score=Decimal("90.00"),
        )
        # Force status to COMPLETED
        EmployeeKPIAssessment.objects.filter(id=self.assessment_completed.id).update(
            status=EmployeeKPIAssessment.StatusChoices.COMPLETED
        )
        self.assessment_completed.refresh_from_db()

    def test_filter_by_status_new(self):
        """Test filtering by status NEW."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"status": "new"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().status == EmployeeKPIAssessment.StatusChoices.NEW
        assert result.first() == self.assessment_new

    def test_filter_by_status_waiting_manager(self):
        """Test filtering by status WAITING_MANAGER."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"status": "waiting_manager"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().status == EmployeeKPIAssessment.StatusChoices.WAITING_MANAGER
        assert result.first() == self.assessment_waiting

    def test_filter_by_status_completed(self):
        """Test filtering by status COMPLETED."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"status": "completed"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().status == EmployeeKPIAssessment.StatusChoices.COMPLETED
        assert result.first() == self.assessment_completed

    def test_filter_by_status_invalid(self):
        """Test filtering by invalid status returns no results."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"status": "invalid_status"},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 0

    def test_filter_by_status_empty(self):
        """Test filtering by empty status returns all results."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"status": ""},
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 3

    def test_filter_by_status_combined_with_other_filters(self):
        """Test combining status filter with other filters."""
        # Update one assessment to have both NEW status and a grade
        EmployeeKPIAssessment.objects.filter(id=self.assessment_new.id).update(
            status=EmployeeKPIAssessment.StatusChoices.NEW, grade_manager="A"
        )
        self.assessment_new.refresh_from_db()

        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={
                "status": "new",
                "grade_manager": "A",
            },
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().status == EmployeeKPIAssessment.StatusChoices.NEW
        assert result.first().grade_manager == "A"

    def test_filter_by_status_with_employee_filter(self):
        """Test combining status filter with employee filter."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={
                "status": "completed",
                "employee": self.employee.id,
            },
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().status == EmployeeKPIAssessment.StatusChoices.COMPLETED
        assert result.first().employee == self.employee

    def test_status_filter_case_sensitive(self):
        """Test that status filter is case sensitive (should use exact lowercase)."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={"status": "NEW"},  # Uppercase should not match
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 0  # Case sensitive, should not match

    def test_filter_by_status_with_period(self):
        """Test combining status filter with period filter."""
        # Arrange
        queryset = EmployeeKPIAssessment.objects.all()
        filterset = EmployeeKPIAssessmentFilterSet(
            data={
                "status": "completed",
                "period": self.period2.id,
            },
            queryset=queryset,
        )

        # Act
        result = filterset.qs

        # Assert
        assert result.count() == 1
        assert result.first().status == EmployeeKPIAssessment.StatusChoices.COMPLETED
        assert result.first().period == self.period2
