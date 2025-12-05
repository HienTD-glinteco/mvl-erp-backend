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

        # Create a superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.valid_config = {
            "insurance_contributions": {
                "social_insurance": {"employee_rate": 0.08, "employer_rate": 0.17, "salary_ceiling": 46800000},
                "health_insurance": {"employee_rate": 0.015, "employer_rate": 0.03, "salary_ceiling": 46800000},
                "unemployment_insurance": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
                "union_fee": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
                "accident_occupational_insurance": {
                    "employee_rate": 0.0,
                    "employer_rate": 0.005,
                    "salary_ceiling": 46800000,
                },
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
            "kpi_salary": {
                "apply_on": "base_salary",
                "tiers": [
                    {"code": "A", "percentage": 0.10, "description": "Excellent"},
                    {"code": "B", "percentage": 0.05, "description": "Good"},
                    {"code": "C", "percentage": 0.00, "description": "Average"},
                    {"code": "D", "percentage": -0.05, "description": "Below Average"},
                ],
            },
            "business_progressive_salary": {
                "apply_on": "base_salary",
                "tiers": [
                    {"code": "M0", "amount": 0, "criteria": []},
                    {
                        "code": "M1",
                        "amount": 7000000,
                        "criteria": [
                            {"name": "transaction_count", "min": 50},
                            {"name": "revenue", "min": 100000000},
                        ],
                    },
                    {
                        "code": "M2",
                        "amount": 9000000,
                        "criteria": [
                            {"name": "transaction_count", "min": 80},
                            {"name": "revenue", "min": 150000000},
                        ],
                    },
                ],
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
        self.assertIsInstance(response_data["error"], dict)
        self.assertEqual(response_data["error"]["detail"], "No salary configuration found")

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
        self.assertIn("apply_on", kpi)
        self.assertIn("tiers", kpi)
        self.assertIsInstance(kpi["tiers"], list)

        # Validate business_progressive_salary
        self.assertIn("business_progressive_salary", config)
        business = config["business_progressive_salary"]
        self.assertIn("apply_on", business)
        self.assertIn("tiers", business)
        self.assertIsInstance(business["tiers"], list)

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
