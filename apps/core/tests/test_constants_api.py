from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class ConstantsAPITestCase(TestCase):
    """Test case for Constants API endpoint"""

    def setUp(self):
        """Set up test client with authenticated user"""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("core:constants")

    def test_constants_endpoint_accessible(self):
        """Test that constants endpoint is accessible with authentication"""
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json(), dict)
        # Response is wrapped by middleware
        response_data = response.json()
        self.assertTrue(response_data.get("success"))
        self.assertIsNotNone(response_data.get("data"))

    def test_constants_returns_all_modules_by_default(self):
        """Test that constants endpoint returns data from all modules by default"""
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Should contain data (at least hrm module has enums)
        self.assertIsInstance(data, dict)

    def test_constants_contains_hrm_model_choices(self):
        """Test that constants endpoint returns HRM model choices"""
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Check for HRM module
        self.assertIn("hrm", data)
        hrm_constants = data["hrm"]

        # HRM should have model choices
        self.assertIsInstance(hrm_constants, dict)
        # Should contain at least one constant from models
        self.assertTrue(len(hrm_constants) > 0)

    def test_constants_choice_format(self):
        """Test that model choices are properly formatted"""
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Find any choice field to verify format
        found_choice = False
        for module_name, module_constants in data.items():
            for constant_name, constant_value in module_constants.items():
                if isinstance(constant_value, list) and len(constant_value) > 0:
                    # Check format of choice items - new format uses {value: label} pairs
                    choice_item = constant_value[0]
                    self.assertIsInstance(choice_item, dict)
                    # Each item should be a dict with one key-value pair (choice value -> label)
                    self.assertEqual(len(choice_item), 1)
                    # The dict should have a string value (the label)
                    for key, value in choice_item.items():
                        self.assertIsInstance(value, str)
                    found_choice = True
                    break
            if found_choice:
                break

        self.assertTrue(found_choice, "Should have at least one choice field")

    def test_constants_filter_by_single_module(self):
        """Test filtering constants by a single module"""
        # Act
        response = self.client.get(self.url, {"modules": "hrm"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Should only contain hrm module
        self.assertIn("hrm", data)
        # Should not contain other modules (if they exist)
        for module_name in data.keys():
            self.assertEqual(module_name, "hrm")

    def test_constants_filter_by_multiple_modules(self):
        """Test filtering constants by multiple modules"""
        # Act
        response = self.client.get(self.url, {"modules": "core,hrm"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Should contain only requested modules
        for module_name in data.keys():
            self.assertIn(module_name, ["core", "hrm"])

    def test_constants_filter_nonexistent_module(self):
        """Test filtering with a non-existent module name"""
        # Act
        response = self.client.get(self.url, {"modules": "nonexistent"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data")

        # Should return empty dict or None (middleware may convert empty dict to None)
        self.assertIn(data, [{}, None])

    def test_constants_endpoint_no_pagination(self):
        """Test that constants endpoint does not paginate results"""
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Should be a plain dict, not a paginated response
        self.assertIsInstance(data, dict)
        self.assertNotIn("count", data)
        self.assertNotIn("next", data)
        self.assertNotIn("previous", data)
        self.assertNotIn("results", data)

    def test_constants_block_type_choices(self):
        """Test that Block.BlockType choices are included"""
        # Act
        response = self.client.get(self.url, {"modules": "hrm"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Should have Block_BlockType constant
        hrm_constants = data.get("hrm", {})
        block_type_found = any("BlockType" in key for key in hrm_constants.keys())
        self.assertTrue(block_type_found, "Should contain Block BlockType choices")

    def test_constants_department_function_choices(self):
        """Test that Department.DepartmentFunction choices are included"""
        # Act
        response = self.client.get(self.url, {"modules": "hrm"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        data = response_data.get("data", {})

        # Should have Department_DepartmentFunction constant
        hrm_constants = data.get("hrm", {})
        dept_function_found = any("DepartmentFunction" in key for key in hrm_constants.keys())
        self.assertTrue(dept_function_found, "Should contain Department DepartmentFunction choices")
