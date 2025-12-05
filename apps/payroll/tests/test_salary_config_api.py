import json

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.models import User
from apps.payroll.models import SalaryConfig


@pytest.mark.django_db
class SalaryConfigAPITest(APITestCase):
    """Test cases for SalaryConfig API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create a test user
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.valid_config = {
            "insurance_contributions": {
                "social_insurance": {"employee_rate": 0.08, "employer_rate": 0.17, "salary_ceiling": 46800000},
                "health_insurance": {"employee_rate": 0.015, "employer_rate": 0.03, "salary_ceiling": 46800000},
                "unemployment_insurance": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
                "union_fee": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
            },
            "personal_income_tax": {
                "standard_deduction": 11000000,
                "dependent_deduction": 4400000,
                "progressive_levels": [
                    {"up_to": 5000000, "rate": 0.05},
                    {"up_to": 10000000, "rate": 0.10},
                    {"up_to": 18000000, "rate": 0.15},
                    {"up_to": 32000000, "rate": 0.20},
                    {"up_to": 52000000, "rate": 0.25},
                    {"up_to": 80000000, "rate": 0.30},
                    {"up_to": None, "rate": 0.35},
                ],
            },
            "kpi_salary": {"grades": {"A": 0.10, "B": 0.05, "C": 0.00, "D": -0.05}},
            "business_progressive_salary": {
                "levels": {"M0": "base_salary", "M1": 7000000, "M2": 9000000, "M3": 11000000, "M4": 13000000}
            },
        }

    def test_get_current_config_success(self):
        """Test retrieving current salary configuration successfully"""
        config = SalaryConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:salary-config-current")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Parse JSON response
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        self.assertIsNotNone(response_data["data"])

        data = response_data["data"]
        self.assertEqual(data["version"], config.version)
        self.assertEqual(data["config"], self.valid_config)
        self.assertIn("insurance_contributions", data["config"])
        self.assertIn("personal_income_tax", data["config"])
        self.assertIn("kpi_salary", data["config"])
        self.assertIn("business_progressive_salary", data["config"])

    def test_get_current_config_no_config_exists(self):
        """Test retrieving config when none exists"""
        url = reverse("payroll:salary-config-current")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Parse JSON response
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertEqual(response_data["error"], "No salary configuration found")

    def test_get_latest_config_when_multiple_exist(self):
        """Test that the API returns the latest configuration"""
        SalaryConfig.objects.create(config=self.valid_config)
        SalaryConfig.objects.create(config=self.valid_config)
        latest = SalaryConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:salary-config-current")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Parse JSON response
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["version"], latest.version)

    def test_response_envelope_format(self):
        """Test that the response follows the envelope format"""
        SalaryConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:salary-config-current")
        response = self.client.get(url)

        # Parse JSON response
        response_data = json.loads(response.content)

        # Check envelope structure
        self.assertIn("success", response_data)
        self.assertIn("data", response_data)
        self.assertIn("error", response_data)

        # For success response
        self.assertTrue(response_data["success"])
        self.assertIsNotNone(response_data["data"])
        self.assertIsNone(response_data["error"])

    def test_config_structure_validation(self):
        """Test that returned config has correct structure"""
        SalaryConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:salary-config-current")
        response = self.client.get(url)

        # Parse JSON response
        response_data = json.loads(response.content)
        config = response_data["data"]["config"]

        # Validate insurance_contributions
        self.assertIn("insurance_contributions", config)
        insurance = config["insurance_contributions"]
        self.assertIn("social_insurance", insurance)
        self.assertIn("health_insurance", insurance)
        self.assertIn("unemployment_insurance", insurance)
        self.assertIn("union_fee", insurance)

        # Validate personal_income_tax
        self.assertIn("personal_income_tax", config)
        tax = config["personal_income_tax"]
        self.assertIn("standard_deduction", tax)
        self.assertIn("dependent_deduction", tax)
        self.assertIn("progressive_levels", tax)
        self.assertIsInstance(tax["progressive_levels"], list)

        # Validate kpi_salary
        self.assertIn("kpi_salary", config)
        kpi = config["kpi_salary"]
        self.assertIn("grades", kpi)

        # Validate business_progressive_salary
        self.assertIn("business_progressive_salary", config)
        business = config["business_progressive_salary"]
        self.assertIn("levels", business)

    def test_readonly_endpoint(self):
        """Test that only GET method is allowed (endpoint is read-only)"""
        SalaryConfig.objects.create(config=self.valid_config)
        url = reverse("payroll:salary-config-current")

        # Try POST
        response = self.client.post(url, data={"config": self.valid_config}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try PUT
        response = self.client.put(url, data={"config": self.valid_config}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try PATCH
        response = self.client.patch(url, data={"config": self.valid_config}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try DELETE
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
