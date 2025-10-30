"""Tests for domain-specific email actions (Employee and Interview Schedule)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    Position,
)

User = get_user_model()


class EmployeeEmailActionTests(TestCase):
    """Test cases for Employee email actions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.staff_user = User.objects.create_superuser(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )

        # Create organizational hierarchy
        self.province = Province.objects.create(
            code="test", name="test", english_name="test", level="province", decree="", enabled=True
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="test",
            name="test",
            english_name="test",
            parent_province=self.province,
            level="district",
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Test Branch", code="TB", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block = Block.objects.create(name="Test Block", code="TBK", branch=self.branch, block_type="business")
        self.department = Department.objects.create(
            name="Test Department", code="TD", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(name="Test Position", code="TP")

        # Create a real employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            email="john.doe@example.com",
            username="johndoe",
            start_date=timezone.now().date(),
            is_onboarding_email_sent=False,
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
        )

    def test_welcome_email_preview(self):
        """Test preview welcome email for employee."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post(f"/api/hrm/employees/{self.employee.id}/welcome_email/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("html", data)
        self.assertIn("text", data)
        self.assertIn("John Doe", data["html"])

    @patch("apps.mailtemplates.views.send_email_job_task.delay")
    def test_welcome_email_send(self, mock_task):
        """Test send welcome email for employee."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post(f"/api/hrm/employees/{self.employee.id}/welcome_email/send/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        mock_task.assert_called_once_with(data["job_id"])

    def test_welcome_email_preview_with_custom_data(self):
        """Test preview with custom data override."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        custom_data = {
            "data": {
                "fullname": "Custom Name",
                "start_date": "2026-01-01",
            }
        }
        response = self.client.post(
            f"/api/hrm/employees/{self.employee.id}/welcome_email/preview/", custom_data, format="json"
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        # Should use custom data, not employee data
        self.assertIn("Custom Name", data["html"])
        self.assertNotIn("John Doe", data["html"])

    def test_welcome_email_requires_authentication(self):
        """Test welcome email actions require authentication."""
        # Act - No authentication
        response = self.client.post(f"/api/hrm/employees/{self.employee.id}/welcome_email/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
