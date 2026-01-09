"""Tests for department assessment auto-update functionality."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from apps.hrm.models import Department, Employee
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class TestDepartmentAssessmentAutoUpdate:
    """Test automatic updates of department assessment status."""

    @pytest.fixture(autouse=True)
    def setup(self, branch, block):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create KPI config with unit control rules
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                    {"min": 60, "max": 80, "possible_codes": ["C"]},
                    {"min": 80, "max": 100, "possible_codes": ["B", "A"]},
                ],
                "unit_control": {
                    "B": {
                        "A": {"max": 0.20},  # Max 20% can get A
                        "B": {"max": 0.30},  # Max 30% can get B
                        "C": {},
                        "D": {"min": 0},
                    }
                },
            }
        )

        # Create assessment period
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
            created_by=self.user,
        )

        # Create department
        self.dept = Department.objects.create(name="Sales", code="SALES", branch=branch, block=block)

        # Create department assessment with grade B
        self.dept_assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept,
            grade="B",
        )

        # Create 5 employees
        self.employees = []
        for i in range(5):
            emp = Employee.objects.create(
                username=f"emp{i}",
                email=f"emp{i}@example.com",
                phone=f"090{i:07d}",
                citizen_id=f"00{i:010d}",
                code=f"EMP{i:03d}",
                department=self.dept,
                branch=branch,
                block=block,
                start_date=date.today(),
                personal_email=f"emp{i}.personal@example.com",
            )
            self.employees.append(emp)

        # Create employee assessments
        self.emp_assessments = []
        for emp in self.employees:
            assessment = EmployeeKPIAssessment.objects.create(
                period=self.period,
                employee=emp,
                department_snapshot=self.dept,  # Set department snapshot
            )
            self.emp_assessments.append(assessment)

    def test_department_not_finished_initially(self):
        """Test that department is not finished when employees have no grades."""
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is False
        assert self.dept_assessment.is_valid_unit_control is True

    def test_department_finished_when_all_employees_graded(self):
        """Test that department becomes finished when all employees get grades."""
        # Grade all employees
        for assessment in self.emp_assessments:
            assessment.grade_manager = "B"
            assessment.save()

        # Check department status updated
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True

    def test_unit_control_validation_when_finished(self):
        """Test that unit control is validated when department finishes."""
        # Give 2 employees grade A (40% - violates max 20%)
        self.emp_assessments[0].grade_manager = "A"
        self.emp_assessments[0].save()

        self.emp_assessments[1].grade_manager = "A"
        self.emp_assessments[1].save()

        # Give rest grade C
        for i in range(2, 5):
            self.emp_assessments[i].grade_manager = "C"
            self.emp_assessments[i].save()

        # Check department status
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True
        # Should be invalid because 40% got A (exceeds 20% max)
        assert self.dept_assessment.is_valid_unit_control is False

    def test_unit_control_valid_when_within_limits(self):
        """Test that unit control is valid when grades are within limits."""
        # Give 1 employee grade A (20% - within max 20%)
        self.emp_assessments[0].grade_manager = "A"
        self.emp_assessments[0].save()

        # Give 1 employee grade B (20% - within max 30%)
        self.emp_assessments[1].grade_manager = "B"
        self.emp_assessments[1].save()

        # Give rest grade C
        for i in range(2, 5):
            self.emp_assessments[i].grade_manager = "C"
            self.emp_assessments[i].save()

        # Check department status
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True
        assert self.dept_assessment.is_valid_unit_control is True

    def test_department_becomes_unfinished_when_grade_removed(self):
        """Test that department becomes unfinished when a grade is removed."""
        # First, grade all employees
        for assessment in self.emp_assessments:
            assessment.grade_manager = "B"
            assessment.save()

        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True

        # Now remove one employee's grade
        self.emp_assessments[0].grade_manager = None
        self.emp_assessments[0].save()

        # Should become unfinished
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is False

    def test_uses_hrm_grade_if_no_manager_grade(self):
        """Test that HRM grade is counted if manager grade is not set."""
        # Give employees HRM grades - mix of grades within unit control limits
        # For dept grade B: max 20% A, max 30% B
        self.emp_assessments[0].grade_hrm = "A"  # 20% (1/5)
        self.emp_assessments[0].save()

        self.emp_assessments[1].grade_hrm = "B"  # 20% (1/5)
        self.emp_assessments[1].save()

        # Give rest grade C (60%)
        for i in range(2, 5):
            self.emp_assessments[i].grade_hrm = "C"
            self.emp_assessments[i].save()

        # Check department status
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True
        assert self.dept_assessment.is_valid_unit_control is True

    def test_prefers_hrm_grade_over_manager_grade(self):
        """Test that manager_grade is used for unit control validation (not HRM grade)."""
        # Give 3 employees grade_hrm = C, but grade_manager = A
        # Manager grade (A) will be used for validation, causing violation
        for i in range(3):
            self.emp_assessments[i].grade_manager = "A"  # 60% A violates max 20%
            self.emp_assessments[i].grade_hrm = "C"  # This is for grade_distribution only
            self.emp_assessments[i].save()

        # Give rest grade C
        for i in range(3, 5):
            self.emp_assessments[i].grade_manager = "C"
            self.emp_assessments[i].grade_hrm = "C"
            self.emp_assessments[i].save()

        # Should be INVALID based on manager_grade_counts (60% A > 20% max)
        # grade_distribution uses hrm priority: {"A": 0, "B": 0, "C": 5, "D": 0}
        # manager_grade_distribution: {"A": 3, "B": 0, "C": 2, "D": 0}
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True
        assert self.dept_assessment.is_valid_unit_control is False  # Changed from True
        assert self.dept_assessment.grade_distribution == {"A": 0, "B": 0, "C": 5, "D": 0}

    def test_uses_manager_grade_when_hrm_grade_not_set(self):
        """Test that manager grade is used as fallback when HRM grade is not set."""
        # Give 3 employees only manager grade A (no HRM grade)
        # This should violate unit control (60% A > 20% max for grade B dept)
        for i in range(3):
            self.emp_assessments[i].grade_manager = "A"
            self.emp_assessments[i].grade_hrm = None
            self.emp_assessments[i].save()

        # Give rest grade C (manager only)
        for i in range(3, 5):
            self.emp_assessments[i].grade_manager = "C"
            self.emp_assessments[i].grade_hrm = None
            self.emp_assessments[i].save()

        # Should be INVALID based on manager_grade (60% A > 20% max)
        # grade_distribution should be: {"A": 3, "B": 0, "C": 2, "D": 0}
        self.dept_assessment.refresh_from_db()
        assert self.dept_assessment.is_finished is True
        assert self.dept_assessment.is_valid_unit_control is False
        assert self.dept_assessment.grade_distribution == {"A": 3, "B": 0, "C": 2, "D": 0}
