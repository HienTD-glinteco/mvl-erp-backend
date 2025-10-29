"""Tests for domain-specific email actions (Employee and Interview Schedule)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import (
    Branch,
    Block,
    Department,
    Employee,
    InterviewCandidate,
    InterviewSchedule,
    Position,
    RecruitmentRequest,
)

User = get_user_model()


class EmployeeEmailActionTests(TestCase):
    """Test cases for Employee email actions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )
        
        # Create organizational hierarchy
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.block = Block.objects.create(name="Test Block", code="TBK", branch=self.branch)
        self.department = Department.objects.create(name="Test Department", code="TD", block=self.block)
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
        response = self.client.post(f"/api/employees/{self.employee.id}/welcome_email/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("html", data)
        self.assertIn("text", data)
        self.assertIn("John Doe", data["html"])

    @patch("apps.mailtemplates.tasks.send_email_job_task")
    def test_welcome_email_send(self, mock_task):
        """Test send welcome email for employee."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post(f"/api/employees/{self.employee.id}/welcome_email/send/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        self.assertTrue(mock_task.delay.called)

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
        response = self.client.post(f"/api/employees/{self.employee.id}/welcome_email/preview/", custom_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        # Should use custom data, not employee data
        self.assertIn("Custom Name", data["html"])
        self.assertNotIn("John Doe", data["html"])

    def test_welcome_email_requires_authentication(self):
        """Test welcome email actions require authentication."""
        # Act - No authentication
        response = self.client.post(f"/api/employees/{self.employee.id}/welcome_email/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class InterviewScheduleEmailActionTests(TestCase):
    """Test cases for Interview Schedule invitation email actions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )
        # Create a recruitment request
        self.recruitment = RecruitmentRequest.objects.create(
            position="Senior Developer",
            quantity=1,
        )
        # Create a real interview candidate
        self.candidate = InterviewCandidate.objects.create(
            fullname="Alice Johnson",
            email="alice@example.com",
            recruitment_request=self.recruitment,
        )
        # Create a real interview schedule
        self.schedule = InterviewSchedule.objects.create(
            candidate=self.candidate,
            time=timezone.now() + timezone.timedelta(days=7),
        )

    def test_interview_invite_preview(self):
        """Test preview interview invitation."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post(f"/api/interview-schedules/{self.schedule.id}/interview_invite/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("html", data)
        self.assertIn("Alice Johnson", data["html"])

    @patch("apps.mailtemplates.tasks.send_email_job_task")
    def test_interview_invite_send(self, mock_task):
        """Test send interview invitation."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post(f"/api/interview-schedules/{self.schedule.id}/interview_invite/send/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        self.assertTrue(mock_task.delay.called)

    def test_interview_invite_nonexistent_schedule(self):
        """Test interview invite for non-existent schedule returns 404."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post("/api/interview-schedules/999999/interview_invite/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_interview_invite_requires_authentication(self):
        """Test interview invite requires authentication."""
        # Act - No authentication
        response = self.client.post(f"/api/interview-schedules/{self.schedule.id}/interview_invite/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
