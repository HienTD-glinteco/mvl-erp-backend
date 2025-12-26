"""Tests for ManagerAssessmentFilterSet."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.payroll.api.filtersets import ManagerAssessmentFilterSet
from apps.payroll.models import (
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.fixture
def kpi_config(db):
    """Create a KPI config for testing."""
    return KPIConfig.objects.create(
        config={
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {"min": 60, "max": 80, "possible_codes": ["C"], "label": "Average"},
                {"min": 80, "max": 90, "possible_codes": ["B"], "label": "Good"},
                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
            ]
        }
    )


@pytest.fixture
def period_dec_2025(db, kpi_config):
    """Create assessment period for December 2025."""
    return KPIAssessmentPeriod.objects.create(
        month=date(2025, 12, 1),
        kpi_config_snapshot=kpi_config.config,
    )


@pytest.fixture
def period_nov_2025(db, kpi_config):
    """Create assessment period for November 2025."""
    return KPIAssessmentPeriod.objects.create(
        month=date(2025, 11, 1),
        kpi_config_snapshot=kpi_config.config,
    )


@pytest.fixture
def manager(employee):
    """Use existing employee fixture as manager."""
    return employee


@pytest.fixture
def employee2(db, branch, block, department, position):
    """Create a second employee for testing."""
    from apps.payroll.tests.conftest import random_code, random_digits

    suffix = random_code(length=6)
    from apps.hrm.models import Employee

    return Employee.objects.create(
        code=f"E{suffix}",
        fullname="Jane Smith",
        username=f"emp{suffix}",
        email=f"emp{suffix}@example.com",
        status=Employee.Status.ACTIVE,
        code_type=Employee.CodeType.MV,
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2024, 1, 1),
        attendance_code=random_digits(6),
        citizen_id=random_digits(12),
        phone=f"09{random_digits(8)}",
    )


@pytest.fixture
def assessment1(db, employee2, manager, period_dec_2025):
    """Create first assessment."""
    return EmployeeKPIAssessment.objects.create(
        employee=employee2,
        manager=manager,
        period=period_dec_2025,
        total_possible_score=Decimal("100.00"),
        total_manager_score=Decimal("85.00"),
        grade_manager="B",
        finalized=False,
    )


@pytest.fixture
def assessment2(db, employee2, manager, period_nov_2025):
    """Create second assessment."""
    return EmployeeKPIAssessment.objects.create(
        employee=employee2,
        manager=manager,
        period=period_nov_2025,
        total_possible_score=Decimal("100.00"),
        total_manager_score=Decimal("92.00"),
        grade_manager="A",
        finalized=True,
    )


@pytest.mark.django_db
class TestManagerAssessmentFilterSet:
    """Test cases for ManagerAssessmentFilterSet."""

    def test_filter_by_employee_id(self, assessment1, assessment2, employee2):
        """Test filtering by employee ID."""
        filterset = ManagerAssessmentFilterSet(
            data={"employee": employee2.id}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_filter_by_employee_username(self, assessment1, assessment2, employee2):
        """Test filtering by employee username."""
        filterset = ManagerAssessmentFilterSet(
            data={"employee_username": employee2.username}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_filter_by_employee_code(self, assessment1, assessment2, employee2):
        """Test filtering by employee code."""
        filterset = ManagerAssessmentFilterSet(
            data={"employee_code": employee2.code}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_filter_by_period(self, assessment1, assessment2, period_dec_2025):
        """Test filtering by period ID."""
        filterset = ManagerAssessmentFilterSet(
            data={"period": period_dec_2025.id}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 1
        assert assessment1 in filterset.qs
        assert assessment2 not in filterset.qs

    def test_filter_by_month(self, assessment1, assessment2):
        """Test filtering by exact month date."""
        filterset = ManagerAssessmentFilterSet(
            data={"month": "2025-12-01"}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 1
        assert assessment1 in filterset.qs

    def test_filter_by_month_year(self, assessment1, assessment2):
        """Test filtering by month/year format (n/YYYY)."""
        filterset = ManagerAssessmentFilterSet(
            data={"month_year": "12/2025"}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 1
        assert assessment1 in filterset.qs
        assert assessment2 not in filterset.qs

    def test_filter_by_grade_manager(self, assessment1, assessment2):
        """Test filtering by manager grade."""
        filterset = ManagerAssessmentFilterSet(
            data={"grade_manager": "B"}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 1
        assert assessment1 in filterset.qs
        assert assessment2 not in filterset.qs

    def test_filter_by_finalized(self, assessment1, assessment2):
        """Test filtering by finalized status."""
        filterset = ManagerAssessmentFilterSet(data={"finalized": True}, queryset=EmployeeKPIAssessment.objects.all())
        assert filterset.is_valid()
        assert filterset.qs.count() == 1
        assert assessment2 in filterset.qs
        assert assessment1 not in filterset.qs

    def test_filter_by_branch(self, assessment1, assessment2, branch):
        """Test filtering by employee's branch."""
        filterset = ManagerAssessmentFilterSet(
            data={"branch": branch.id}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_filter_by_block(self, assessment1, assessment2, block):
        """Test filtering by employee's block."""
        filterset = ManagerAssessmentFilterSet(data={"block": block.id}, queryset=EmployeeKPIAssessment.objects.all())
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_filter_by_department(self, assessment1, assessment2, department):
        """Test filtering by employee's department."""
        filterset = ManagerAssessmentFilterSet(
            data={"department": department.id}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_filter_by_position(self, assessment1, assessment2, position):
        """Test filtering by employee's position."""
        filterset = ManagerAssessmentFilterSet(
            data={"position": position.id}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs

    def test_multiple_filters(self, assessment1, assessment2, employee2, period_dec_2025):
        """Test combining multiple filters."""
        filterset = ManagerAssessmentFilterSet(
            data={"employee": employee2.id, "period": period_dec_2025.id, "finalized": False},
            queryset=EmployeeKPIAssessment.objects.all(),
        )
        assert filterset.is_valid()
        assert filterset.qs.count() == 1
        assert assessment1 in filterset.qs
        assert assessment2 not in filterset.qs

    def test_no_filters(self, assessment1, assessment2):
        """Test with no filters returns all assessments."""
        filterset = ManagerAssessmentFilterSet(data={}, queryset=EmployeeKPIAssessment.objects.all())
        assert filterset.is_valid()
        assert filterset.qs.count() == 2

    def test_invalid_month_year_format(self, assessment1, assessment2):
        """Test invalid month_year format returns empty queryset."""
        filterset = ManagerAssessmentFilterSet(
            data={"month_year": "invalid"}, queryset=EmployeeKPIAssessment.objects.all()
        )
        assert filterset.is_valid()
        # Invalid format should return all items (no filtering applied)
        assert filterset.qs.count() == 2
        assert assessment1 in filterset.qs
        assert assessment2 in filterset.qs
