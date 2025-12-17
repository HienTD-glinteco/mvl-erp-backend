"""Tests for KPIAssessmentPeriod model and API."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.payroll.models import KPIAssessmentPeriod, KPIConfig

User = get_user_model()


@pytest.mark.django_db
class KPIAssessmentPeriodModelTest(TestCase):
    """Test cases for KPIAssessmentPeriod model."""

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
                    {"min": 60, "max": 80, "possible_codes": ["C"]},
                    {"min": 80, "max": 100, "possible_codes": ["B"]},
                ],
            }
        )

    def test_create_period(self):
        """Test creating a KPI assessment period."""
        period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
            created_by=self.user,
        )

        self.assertIsNotNone(period.id)
        self.assertEqual(period.month, date(2025, 12, 1))
        self.assertEqual(period.kpi_config_snapshot, self.kpi_config.config)
        self.assertFalse(period.finalized)

    def test_unique_month(self):
        """Test that month must be unique."""
        KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        with self.assertRaises(Exception):
            KPIAssessmentPeriod.objects.create(
                month=date(2025, 12, 1),
                kpi_config_snapshot=self.kpi_config.config,
            )

    def test_str_representation(self):
        """Test string representation."""
        period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        expected = "KPI Period 2025-12 - Open"
        self.assertEqual(str(period), expected)

    def test_str_representation_finalized(self):
        """Test string representation for finalized period."""
        period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
            finalized=True,
        )

        expected = "KPI Period 2025-12 - Finalized"
        self.assertEqual(str(period), expected)


@pytest.mark.django_db
class KPIAssessmentPeriodAPITest(TestCase):
    """Test cases for KPIAssessmentPeriod API."""

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

        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

    def test_list_periods(self):
        """Test listing KPI assessment periods."""
        response = self.client.get("/api/payroll/kpi-periods/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertGreater(self.get_response_data(response)["data"]["count"], 0)

    def test_retrieve_period(self):
        """Test retrieving a specific period."""
        response = self.client.get(f"/api/payroll/kpi-periods/{self.period.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertEqual(self.get_response_data(response)["data"]["id"], self.period.id)

    def test_generate_period(self):
        """Test generating assessments for a new period."""
        data = {"month": "2026-01"}

        response = self.client.post("/api/payroll/kpi-periods/generate/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertIn("period_id", self.get_response_data(response)["data"])

    def test_finalize_period(self):
        """Test finalizing a period."""
        response = self.client.post(f"/api/payroll/kpi-periods/{self.period.id}/finalize/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify period is finalized
        self.period.refresh_from_db()
        self.assertTrue(self.period.finalized)
