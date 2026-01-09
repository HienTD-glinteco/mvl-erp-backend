"""Tests for manager_grade_distribution field in DepartmentKPIAssessment."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)
from apps.payroll.utils.kpi_calculation import update_department_assessment_status

User = get_user_model()


@pytest.mark.django_db
class ManagerGradeDistributionModelTest(TestCase):
    """Test cases for manager_grade_distribution field in DepartmentKPIAssessment model."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department, employee):
        self.department = department
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 90, "max": 110, "possible_codes": ["A"], "default_code": "A"},
                    {"min": 80, "max": 90, "possible_codes": ["B"], "default_code": "B"},
                    {"min": 60, "max": 80, "possible_codes": ["C"], "default_code": "C"},
                    {"min": 0, "max": 60, "possible_codes": ["D"], "default_code": "D"},
                ],
                "unit_control": {
                    "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {}},
                    "B": {"A": {"max": 0.10}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {"min": 0.10}},
                    "C": {"A": {"max": 0.05}, "B": {"max": 0.20}, "C": {"max": 0.60}, "D": {"min": 0.15}},
                    "D": {"A": {"max": 0.05}, "B": {"max": 0.10}, "C": {"max": 0.65}, "D": {"min": 0.20}},
                },
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

    def test_manager_grade_distribution_field_exists(self):
        """Test that manager_grade_distribution field exists in model."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
            created_by=self.user,
        )

        self.assertTrue(hasattr(assessment, "manager_grade_distribution"))

    def test_manager_grade_distribution_default_value(self):
        """Test that manager_grade_distribution has default empty dict value."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
            created_by=self.user,
        )

        self.assertEqual(assessment.manager_grade_distribution, {})

    def test_manager_grade_distribution_can_store_data(self):
        """Test that manager_grade_distribution can store grade counts."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
            created_by=self.user,
            manager_grade_distribution={"A": 1, "B": 2, "C": 3, "D": 0},
        )

        assessment.refresh_from_db()
        self.assertEqual(assessment.manager_grade_distribution, {"A": 1, "B": 2, "C": 3, "D": 0})

    def test_update_grade_distribution_updates_manager_grades(self):
        """Test that update_grade_distribution method updates manager_grade_distribution."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="A",
            created_by=self.user,
        )

        # Create employee assessment with manager grade
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.employee,
            department_snapshot=self.department,
            grade_manager="A",
        )

        assessment.update_grade_distribution()
        assessment.refresh_from_db()

        self.assertEqual(assessment.manager_grade_distribution, {"A": 1, "B": 0, "C": 0, "D": 0})

    def test_update_department_assessment_status_calculates_manager_distribution(self):
        """Test that update_department_assessment_status calculates manager_grade_distribution."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="A",
            created_by=self.user,
        )

        # Create employee assessments with different manager grades
        # Test with different grade_manager vs grade_hrm
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.employee,
            department_snapshot=self.department,
            grade_manager="A",
            grade_hrm="B",
        )

        update_department_assessment_status(assessment)
        assessment.refresh_from_db()

        # Manager distribution should reflect grade_manager values
        self.assertEqual(assessment.manager_grade_distribution, {"A": 1, "B": 0, "C": 0, "D": 0})
        # Grade distribution should reflect final grades (grade_hrm > grade_manager)
        self.assertEqual(assessment.grade_distribution, {"A": 0, "B": 1, "C": 0, "D": 0})


@pytest.mark.django_db
class ManagerGradeDistributionSerializerTest(TestCase):
    """Test cases for manager_grade_distribution field in serializers."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department):
        self.department = department

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        import json

        content = json.loads(response.content.decode())
        return content

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
                "unit_control": {
                    "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {}},
                },
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=kpi_config.config,
        )

        self.assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="C",
            manager_grade_distribution={"A": 1, "B": 2, "C": 3, "D": 0},
        )

    def test_list_serializer_includes_manager_grade_distribution(self):
        """Test that list endpoint includes manager_grade_distribution."""
        response = self.client.get("/api/payroll/kpi-assessments/departments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertTrue(data["success"])
        self.assertGreater(data["data"]["count"], 0)

        first_result = data["data"]["results"][0]
        self.assertIn("manager_grade_distribution", first_result)

    def test_retrieve_serializer_includes_manager_grade_distribution(self):
        """Test that retrieve endpoint includes manager_grade_distribution."""
        response = self.client.get(f"/api/payroll/kpi-assessments/departments/{self.assessment.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertTrue(data["success"])
        self.assertIn("manager_grade_distribution", data["data"])
        self.assertEqual(data["data"]["manager_grade_distribution"], {"A": 1, "B": 2, "C": 3, "D": 0})

    def test_update_serializer_includes_manager_grade_distribution(self):
        """Test that update endpoint includes manager_grade_distribution in response."""
        update_data = {
            "grade": "A",
            "note": "Updated",
        }

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.assessment.id}/",
            update_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertTrue(data["success"])
        self.assertIn("manager_grade_distribution", data["data"])

    def test_manager_grade_distribution_is_read_only(self):
        """Test that manager_grade_distribution cannot be updated directly via API."""
        update_data = {
            "grade": "A",
            "manager_grade_distribution": {"A": 10, "B": 20, "C": 30, "D": 40},
        }

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.assessment.id}/",
            update_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assessment.refresh_from_db()
        # Manager grade distribution should not have changed
        self.assertEqual(self.assessment.manager_grade_distribution, {"A": 1, "B": 2, "C": 3, "D": 0})

    def test_serializer_provides_default_structure_when_empty(self):
        """Test that serializer provides default grade structure when manager_grade_distribution is empty."""
        # Create a new period to avoid unique constraint
        new_period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 11, 1),
            kpi_config_snapshot=self.period.kpi_config_snapshot,
        )

        assessment = DepartmentKPIAssessment.objects.create(
            period=new_period,
            department=self.department,
            grade="B",
        )

        response = self.client.get(f"/api/payroll/kpi-assessments/departments/{assessment.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["manager_grade_distribution"], {"A": 0, "B": 0, "C": 0, "D": 0})
