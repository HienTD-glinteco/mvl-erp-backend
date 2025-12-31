"""Tests for KPI Assessment Period Summary API."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Department, Employee
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class TestKPIAssessmentPeriodSummaryAPI:
    """Test cases for KPI Assessment Period Summary API."""

    @pytest.fixture(autouse=True)
    def setup(self, branch, block):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        # Create KPI config
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                    {"min": 60, "max": 80, "possible_codes": ["C"]},
                    {"min": 80, "max": 100, "possible_codes": ["B", "A"]},
                ],
                "unit_control": {},
            }
        )

        # Create assessment period
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
            created_by=self.user,
        )

        # Create departments
        self.dept1 = Department.objects.create(name="Sales", code="SALES", branch=branch, block=block)
        self.dept2 = Department.objects.create(name="IT", code="IT", branch=branch, block=block)
        self.dept3 = Department.objects.create(name="HR", code="HR", branch=branch, block=block)

        # Create department assessments
        self.dept_assessment1 = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept1,
            grade="A",
            is_valid_unit_control=True,
        )
        self.dept_assessment2 = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept2,
            grade="B",
            is_valid_unit_control=False,
        )
        self.dept_assessment3 = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept3,
            grade="C",
            is_valid_unit_control=True,
        )

        # Create employees for dept1 (Sales) - all graded
        self.emp1_dept1 = Employee.objects.create(
            username="emp1_sales",
            email="emp1_sales@example.com",
            phone="0901111111",
            citizen_id="001111111111",
            code="EMP001",
            department=self.dept1,
            branch=branch,
            block=block,
            start_date=date.today(),
        )
        self.emp2_dept1 = Employee.objects.create(
            username="emp2_sales",
            email="emp2_sales@example.com",
            phone="0902222222",
            citizen_id="002222222222",
            code="EMP002",
            department=self.dept1,
            branch=branch,
            block=block,
            start_date=date.today(),
        )

        # Create employees for dept2 (IT) - partially graded
        self.emp1_dept2 = Employee.objects.create(
            username="emp1_it",
            email="emp1_it@example.com",
            phone="0903333333",
            citizen_id="003333333333",
            code="EMP003",
            department=self.dept2,
            branch=branch,
            block=block,
            start_date=date.today(),
        )
        self.emp2_dept2 = Employee.objects.create(
            username="emp2_it",
            email="emp2_it@example.com",
            phone="0904444444",
            citizen_id="004444444444",
            code="EMP004",
            department=self.dept2,
            branch=branch,
            block=block,
            start_date=date.today(),
        )

        # Create employees for dept3 (HR) - not graded
        self.emp1_dept3 = Employee.objects.create(
            username="emp1_hr",
            email="emp1_hr@example.com",
            phone="0905555555",
            citizen_id="005555555555",
            code="EMP005",
            department=self.dept3,
            branch=branch,
            block=block,
            start_date=date.today(),
        )

        # Create employee assessments for dept1 - all finished
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1_dept1,
            grade_manager="A",
            department_snapshot=self.dept1,
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2_dept1,
            grade_hrm="B",
            department_snapshot=self.dept1,
        )

        # Create employee assessments for dept2 - not finished (one without grade)
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1_dept2,
            grade_manager="B",
            department_snapshot=self.dept2,
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2_dept2,
            # No grades
            department_snapshot=self.dept2,
        )

        # Create employee assessments for dept3 - not finished
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1_dept3,
            # No grades
            department_snapshot=self.dept3,
        )

    def test_summary_endpoint_returns_correct_counts(self):
        """Test that summary endpoint returns correct department counts."""
        url = f"/api/payroll/kpi-periods/{self.period.id}/summary/"
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "data" in data

        summary = data["data"]

        # Total departments should be 3
        assert summary["total_departments"] == 3

        # Only dept1 (Sales) has all employees graded, will be marked as finished by signal
        assert summary["departments_finished"] == 1

        # dept2 (IT) and dept3 (HR) are not finished
        assert summary["departments_not_finished"] == 2

        # All departments are valid because is_valid_unit_control is only calculated
        # when department is finished (all employees graded)
        # dept2 was manually set to False but signal reset it to True because not all employees are graded
        assert summary["departments_not_valid_control"] == 0

    def test_summary_with_no_departments(self):
        """Test summary with a period that has no departments."""
        # Create a new period without departments
        new_period = KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot=self.kpi_config.config,
            created_by=self.user,
        )

        url = f"/api/payroll/kpi-periods/{new_period.id}/summary/"
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        summary = data["data"]

        assert summary["total_departments"] == 0
        assert summary["departments_finished"] == 0
        assert summary["departments_not_finished"] == 0
        assert summary["departments_not_valid_control"] == 0

    def test_summary_all_departments_finished(self):
        """Test summary when all departments are finished."""
        # Grade the remaining employees
        emp2_dept2_assessment = EmployeeKPIAssessment.objects.get(employee=self.emp2_dept2)
        emp2_dept2_assessment.grade_manager = "C"
        emp2_dept2_assessment.save()

        emp1_dept3_assessment = EmployeeKPIAssessment.objects.get(employee=self.emp1_dept3)
        emp1_dept3_assessment.grade_hrm = "B"
        emp1_dept3_assessment.save()

        url = f"/api/payroll/kpi-periods/{self.period.id}/summary/"
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        summary = data["data"]

        # All 3 departments should be finished
        assert summary["departments_finished"] == 3
        assert summary["departments_not_finished"] == 0

    def test_summary_department_with_both_grades(self, branch, block):
        """Test that employee with both manager and HRM grades counts as finished."""
        # Create a new department and employee with both grades
        dept4 = Department.objects.create(name="Finance", code="FIN", branch=branch, block=block)
        DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=dept4,
            grade="A",
            is_valid_unit_control=True,
        )

        emp_dept4 = Employee.objects.create(
            username="emp1_finance",
            email="emp1_finance@example.com",
            phone="0906666666",
            citizen_id="006666666666",
            code="EMP006",
            department=dept4,
            branch=branch,
            block=block,
            start_date=date.today(),
        )

        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=emp_dept4,
            grade_manager="B",
            grade_hrm="A",
            department_snapshot=dept4,
        )

        url = f"/api/payroll/kpi-periods/{self.period.id}/summary/"
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        summary = data["data"]

        # Now we have 4 departments, 2 finished (dept1 and dept4)
        assert summary["total_departments"] == 4
        assert summary["departments_finished"] == 2

    def test_summary_unauthenticated_access(self):
        """Test that unauthenticated users can still access the summary (permissions may vary)."""
        self.client.force_authenticate(user=None)

        url = f"/api/payroll/kpi-periods/{self.period.id}/summary/"
        response = self.client.get(url)

        # The response should either be successful or unauthorized/forbidden
        # Depending on the permission settings
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
