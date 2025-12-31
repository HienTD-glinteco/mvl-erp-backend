"""Tests for EmployeeKPIAssessment serializer new fields."""

from datetime import date
from decimal import Decimal

import pytest

from apps.payroll.api.serializers import (
    EmployeeKPIAssessmentListSerializer,
    EmployeeKPIAssessmentSerializer,
    EmployeeSelfAssessmentSerializer,
    ManagerAssessmentSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment, KPIAssessmentPeriod, KPIConfig, KPICriterion


@pytest.fixture
def kpi_config():
    """Create KPI config."""
    return KPIConfig.objects.create(
        config={
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {"min": 60, "max": 70, "possible_codes": ["C"], "label": "Average"},
                {"min": 70, "max": 90, "possible_codes": ["B"], "label": "Good"},
                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
            ],
            "ambiguous_assignment": "manual",
        }
    )


@pytest.fixture
def assessment_period(kpi_config):
    """Create assessment period."""
    return KPIAssessmentPeriod.objects.create(
        month=date(2025, 12, 1),
        kpi_config_snapshot=kpi_config.config,
    )


@pytest.fixture
def kpi_criteria():
    """Create test KPI criteria."""
    criterion1 = KPICriterion.objects.create(
        target="sales",
        evaluation_type="work_performance",
        criterion="Revenue Achievement",
        component_total_score=Decimal("70.00"),
        group_number=1,
        order=1,
        active=True,
    )
    criterion2 = KPICriterion.objects.create(
        target="sales",
        evaluation_type="discipline",
        criterion="Attendance",
        component_total_score=Decimal("30.00"),
        group_number=2,
        order=2,
        active=True,
    )
    return [criterion1, criterion2]


@pytest.mark.django_db
class TestEmployeeKPIAssessmentSerializerFields:
    """Test that serializers include employee organizational fields nested properly."""

    def test_list_serializer_includes_nested_fields(self, employee, assessment_period, kpi_criteria):
        """Test EmployeeKPIAssessmentListSerializer includes nested organizational fields."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=assessment_period,
            department_snapshot=employee.department,  # Set department snapshot
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        serializer = EmployeeKPIAssessmentListSerializer(assessment)
        data = serializer.data

        # Check that employee is nested with organizational fields
        assert "employee" in data, "employee field should be in serializer output"
        assert "department_snapshot" in data, "department_snapshot field should be in serializer output"

        employee_data = data["employee"]
        assert "block" in employee_data, "block field should be in employee data"
        assert "branch" in employee_data, "branch field should be in employee data"
        assert "department" in employee_data, "department field should be in employee data"
        assert "position" in employee_data, "position field should be in employee data"

        # Check nested structure (should have id, name, code)
        if employee_data["block"]:
            assert "id" in employee_data["block"]
            assert "name" in employee_data["block"]
            assert "code" in employee_data["block"]

        if employee_data["branch"]:
            assert "id" in employee_data["branch"]
            assert "name" in employee_data["branch"]
            assert "code" in employee_data["branch"]

        if employee_data["department"]:
            assert "id" in employee_data["department"]
            assert "name" in employee_data["department"]
            assert "code" in employee_data["department"]

    def test_detail_serializer_includes_nested_fields(self, employee, assessment_period, kpi_criteria):
        """Test EmployeeKPIAssessmentSerializer includes nested organizational fields."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=assessment_period,
            department_snapshot=employee.department,  # Set department snapshot
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        serializer = EmployeeKPIAssessmentSerializer(assessment)
        data = serializer.data

        # Check that employee is nested with organizational fields
        assert "employee" in data, "employee field should be in serializer output"
        assert "department_snapshot" in data, "department_snapshot field should be in serializer output"

        employee_data = data["employee"]
        assert "block" in employee_data, "block field should be in employee data"
        assert "branch" in employee_data, "branch field should be in employee data"
        assert "department" in employee_data, "department field should be in employee data"
        assert "position" in employee_data, "position field should be in employee data"

    def test_self_assessment_serializer_includes_nested_fields(self, employee, assessment_period, kpi_criteria):
        """Test EmployeeSelfAssessmentSerializer includes nested organizational fields."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=assessment_period,
            department_snapshot=employee.department,  # Set department snapshot
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        serializer = EmployeeSelfAssessmentSerializer(assessment)
        data = serializer.data

        # Check that employee is nested with organizational fields
        assert "employee" in data, "employee field should be in serializer output"
        assert "department_snapshot" in data, "department_snapshot field should be in serializer output"

        employee_data = data["employee"]
        assert "block" in employee_data, "block field should be in employee data"
        assert "branch" in employee_data, "branch field should be in employee data"
        assert "department" in employee_data, "department field should be in employee data"
        assert "position" in employee_data, "position field should be in employee data"

    def test_manager_assessment_serializer_includes_nested_fields(self, employee, assessment_period, kpi_criteria):
        """Test ManagerAssessmentSerializer includes nested organizational fields."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=assessment_period,
            department_snapshot=employee.department,  # Set department snapshot
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        serializer = ManagerAssessmentSerializer(assessment)
        data = serializer.data

        # Check that employee is nested with organizational fields
        assert "employee" in data, "employee field should be in serializer output"
        assert "department_snapshot" in data, "department_snapshot field should be in serializer output"

        employee_data = data["employee"]
        assert "block" in employee_data, "block field should be in employee data"
        assert "branch" in employee_data, "branch field should be in employee data"
        assert "department" in employee_data, "department field should be in employee data"
        assert "position" in employee_data, "position field should be in employee data"
