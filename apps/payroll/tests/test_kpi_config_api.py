import json

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.models import User
from apps.payroll.models import KPIConfig


@pytest.mark.django_db
class KPIConfigAPITest(APITestCase):
    """Test cases for KPIConfig API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create a superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.valid_config = {
            "name": "Default KPI Config",
            "description": "Standard grading scale and unit control",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {
                    "min": 60,
                    "max": 70,
                    "possible_codes": ["C", "D"],
                    "default_code": "C",
                    "label": "Average or Poor",
                },
                {
                    "min": 70,
                    "max": 90,
                    "possible_codes": ["B", "C"],
                    "default_code": "B",
                    "label": "Good or Average",
                },
                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
            ],
            "unit_control": {
                "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {"min": None}},
                "B": {"A": {"max": 0.10}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {"min": 0.10}},
                "C": {"A": {"max": 0.05}, "B": {"max": 0.20}, "C": {"max": 0.60}, "D": {"min": 0.15}},
                "D": {"A": {"max": 0.05}, "B": {"max": 0.10}, "C": {"max": 0.65}, "D": {"min": 0.20}},
            },
            "meta": {},
        }

    def test_get_current_config_success(self):
        """Test retrieving current KPI configuration successfully"""
        config = KPIConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:kpi-config-current")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Parse JSON response
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        self.assertIsNotNone(response_data["data"])

        data = response_data["data"]
        self.assertEqual(data["version"], config.version)
        self.assertEqual(data["config"]["name"], "Default KPI Config")
        self.assertEqual(data["config"]["ambiguous_assignment"], "manual")
        self.assertEqual(len(data["config"]["grade_thresholds"]), 4)
        self.assertEqual(len(data["config"]["unit_control"]), 4)

    def test_get_current_config_no_config_exists(self):
        """Test retrieving config when none exists"""
        url = reverse("payroll:kpi-config-current")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Parse JSON response
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertIsInstance(response_data["error"], dict)
        self.assertEqual(response_data["error"]["detail"], "No KPI configuration found")

    def test_get_latest_config_when_multiple_exist(self):
        """Test that the API returns the latest configuration"""
        KPIConfig.objects.create(config=self.valid_config)
        KPIConfig.objects.create(config=self.valid_config)
        latest = KPIConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:kpi-config-current")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Parse JSON response
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["version"], latest.version)

    def test_response_envelope_format(self):
        """Test that the response follows the envelope format"""
        KPIConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:kpi-config-current")
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
        KPIConfig.objects.create(config=self.valid_config)

        url = reverse("payroll:kpi-config-current")
        response = self.client.get(url)

        # Parse JSON response
        response_data = json.loads(response.content)
        config = response_data["data"]["config"]

        # Validate required fields
        self.assertIn("name", config)
        self.assertIn("ambiguous_assignment", config)
        self.assertIn("grade_thresholds", config)
        self.assertIn("unit_control", config)

        # Validate grade_thresholds structure
        self.assertIsInstance(config["grade_thresholds"], list)
        for threshold in config["grade_thresholds"]:
            self.assertIn("min", threshold)
            self.assertIn("max", threshold)
            self.assertIn("possible_codes", threshold)
            self.assertIsInstance(threshold["possible_codes"], list)

        # Validate unit_control structure
        self.assertIsInstance(config["unit_control"], dict)
        for unit_type, control in config["unit_control"].items():
            self.assertIsInstance(control, dict)
            # Each unit_type has nested grade controls
            for grade in ["A", "B", "C", "D"]:
                self.assertIn(grade, control)

    def test_readonly_endpoint(self):
        """Test that only GET method is allowed (endpoint is read-only)"""
        KPIConfig.objects.create(config=self.valid_config)
        url = reverse("payroll:kpi-config-current")

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

    def test_config_with_all_optional_fields(self):
        """Test config with all optional fields populated"""
        full_config = self.valid_config.copy()
        full_config["meta"] = {"notes": "test notes", "version_info": "1.0"}

        config = KPIConfig.objects.create(config=full_config)

        url = reverse("payroll:kpi-config-current")
        response = self.client.get(url)

        response_data = json.loads(response.content)
        self.assertEqual(response_data["data"]["config"]["meta"]["notes"], "test notes")

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected"""
        KPIConfig.objects.create(config=self.valid_config)

        # Create a new client without authentication
        unauthenticated_client = APIClient()
        url = reverse("payroll:kpi-config-current")
        response = unauthenticated_client.get(url)

        # Should be 401 or 403 depending on permission configuration
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
