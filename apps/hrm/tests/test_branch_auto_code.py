"""Tests for Branch API auto-code generation."""

import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Branch

User = get_user_model()


class BranchAutoCodeGenerationAPITest(TransactionTestCase):
    """Test cases for Branch API auto-code generation."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_create_branch_without_code_auto_generates(self):
        """Test creating a branch without code field auto-generates code."""
        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("CN"))

        # Verify in database
        branch = Branch.objects.first()
        self.assertIsNotNone(branch)
        self.assertEqual(branch.code, response_data["code"])

    def test_create_branch_with_code_ignores_provided_code(self):
        """Test that provided code is ignored and auto-generated code is used."""
        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "code": "MANUAL",  # This should be ignored
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify auto-generated code was used, not manual code
        self.assertNotEqual(response_data["code"], "MANUAL")
        self.assertTrue(response_data["code"].startswith("CN"))

    def test_auto_generated_code_format_single_digit(self):
        """Test auto-generated code format for first branch (CN001)."""
        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code format (should be at least 3 digits)
        branch = Branch.objects.first()
        self.assertEqual(branch.code, f"CN{branch.id:03d}")

    def test_auto_generated_code_multiple_branches(self):
        """Test auto-generated codes for multiple branches."""
        # Arrange
        url = reverse("hrm:branch-list")

        # Act - Create 3 branches
        for i in range(3):
            branch_data = {
                "name": f"Chi nhánh {i + 1}",
                "address": f"Địa chỉ {i + 1}",
            }
            response = self.client.post(url, branch_data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assert - Verify all branches have unique auto-generated codes
        branches = Branch.objects.all().order_by("id")
        self.assertEqual(branches.count(), 3)

        codes = [branch.code for branch in branches]
        # All codes should be unique
        self.assertEqual(len(codes), len(set(codes)))
        # All codes should start with CN
        for code in codes:
            self.assertTrue(code.startswith("CN"))

    def test_code_field_is_readonly_in_response(self):
        """Test that code field is included in response but not writable."""
        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
        }

        # Act - Create branch
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert - Response includes code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertIn("code", response_data)

        # Act - Try to update code
        branch = Branch.objects.first()
        update_url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        update_data = {"code": "NEWCODE"}
        update_response = self.client.patch(update_url, update_data, format="json")

        # Assert - Code should not be updated
        branch.refresh_from_db()
        self.assertNotEqual(branch.code, "NEWCODE")

    def test_branch_with_description(self):
        """Test creating a branch with description field."""
        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
            "description": "Branch description here",
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["description"], branch_data["description"])

        # Verify in database
        branch = Branch.objects.first()
        self.assertEqual(branch.description, branch_data["description"])
