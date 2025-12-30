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
