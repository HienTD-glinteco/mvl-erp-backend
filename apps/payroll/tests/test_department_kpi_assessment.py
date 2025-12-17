"""Tests for DepartmentKPIAssessment model and API."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Department
from apps.payroll.models import (
    DepartmentKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class DepartmentKPIAssessmentModelTest(TestCase):
    """Test cases for DepartmentKPIAssessment model."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department):
        self.department = department

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
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
                "unit_control": {
                    "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50},
                },
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

    def test_create_department_assessment(self):
        """Test creating a department KPI assessment."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
            created_by=self.user,
        )

        self.assertIsNotNone(assessment.id)
        self.assertEqual(assessment.period, self.period)
        self.assertEqual(assessment.department, self.department)
        self.assertEqual(assessment.grade, "B")
        self.assertEqual(assessment.default_grade, "C")
        self.assertFalse(assessment.finalized)

    def test_unique_department_period(self):
        """Test that department+period combination is unique."""
        DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
        )

        with self.assertRaises(Exception):
            DepartmentKPIAssessment.objects.create(
                period=self.period,
                department=self.department,
                grade="C",
            )

    def test_str_representation(self):
        """Test string representation."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="A",
        )

        # String format: "{department.name} - {period.month:%Y-%m} - Grade: {grade}"
        expected = f"{self.department.name} - 2025-12 - Grade: A"
        self.assertEqual(str(assessment), expected)


@pytest.mark.django_db
class DepartmentKPIAssessmentAPITest(TestCase):
    """Test cases for DepartmentKPIAssessment API."""

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
                    "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50},
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
        )

    def test_list_assessments(self):
        """Test listing department KPI assessments."""
        response = self.client.get("/api/payroll/kpi/departments/assessments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertGreater(self.get_response_data(response)["data"]["count"], 0)

    def test_retrieve_assessment(self):
        """Test retrieving a specific assessment."""
        response = self.client.get(f"/api/payroll/kpi/departments/assessments/{self.assessment.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertEqual(self.get_response_data(response)["data"]["id"], self.assessment.id)

    def test_update_assessment(self):
        """Test updating an assessment."""
        data = {
            "grade": "A",
            "note": "Excellent performance",
        }

        response = self.client.patch(
            f"/api/payroll/kpi/departments/assessments/{self.assessment.id}/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)

        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.grade, "A")
        self.assertEqual(self.assessment.note, "Excellent performance")

    def test_generate_assessments(self):
        """Test generating department assessments."""
        # Create another department using same branch and block
        dept2 = Department.objects.create(
            name="HR Department",
            code="HRDEPT",
            branch=self.department.branch,
            block=self.department.block,
            is_active=True,
        )

        response = self.client.post(
            "/api/payroll/kpi/departments/assessments/generate/?month=2026-01",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertIn("created", response_data["data"])
        self.assertGreater(response_data["data"]["created"], 0)

    def test_finalize_assessment(self):
        """Test finalizing a department assessment."""
        response = self.client.post(f"/api/payroll/kpi/departments/assessments/{self.assessment.id}/finalize/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assessment.refresh_from_db()
        self.assertTrue(self.assessment.finalized)
