"""Tests for domain-specific email actions (Employee, Interview Schedule)."""

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import User
from apps.hrm.models import Employee, InterviewSchedule, InterviewCandidate, RecruitmentRequest


class EmployeeEmailActionTests(TestCase):
    """Test cases for Employee welcome email actions."""

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
        # Create a real employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            email="john@example.com",
            user=self.user,
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
        response = self.client.post("/api/employees/1/welcome_email/preview/", {}, format="json")

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

    @patch("apps.hrm.models.InterviewSchedule")
    @patch("apps.hrm.models.InterviewCandidate")
    def test_interview_invite_preview(self, mock_candidate_model, mock_schedule_model):
        """Test preview interview invitation."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        
        # Mock candidate
        mock_candidate = mock_candidate_model.return_value
        mock_candidate.fullname = "Alice Johnson"
        mock_candidate.email = "alice@example.com"
        
        # Mock schedule
        mock_schedule = mock_schedule_model.return_value
        mock_schedule.candidate = mock_candidate
        mock_schedule.position = "Senior Developer"
        mock_schedule.interview_date = "2025-11-15"
        mock_schedule.interview_time = "14:00"
        mock_schedule.location = "Office Building A"

        # Act
        with patch("apps.hrm.api.views.interview_schedule.InterviewSchedule.objects.get", return_value=mock_schedule):
            response = self.client.post("/api/interview-schedules/1/interview_invite/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("html", data)
        self.assertIn("Alice Johnson", data["html"])
        self.assertIn("Senior Developer", data["html"])

    @patch("apps.hrm.models.InterviewSchedule")
    @patch("apps.hrm.models.InterviewCandidate")
    @patch("apps.mailtemplates.tasks.send_email_job_task")
    def test_interview_invite_send(self, mock_task, mock_candidate_model, mock_schedule_model):
        """Test send interview invitation."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        
        # Mock candidate
        mock_candidate = mock_candidate_model.return_value
        mock_candidate.fullname = "Bob Williams"
        mock_candidate.email = "bob@example.com"
        mock_candidate.email_sent_at = None
        mock_candidate.save = lambda **kwargs: None
        
        # Mock schedule
        mock_schedule = mock_schedule_model.return_value
        mock_schedule.candidate = mock_candidate
        mock_schedule.position = "DevOps Engineer"
        mock_schedule.interview_date = "2025-12-01"
        mock_schedule.interview_time = "10:00"

        # Act
        with patch("apps.hrm.api.views.interview_schedule.InterviewSchedule.objects.get", return_value=mock_schedule):
            response = self.client.post("/api/interview-schedules/1/interview_invite/send/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        self.assertTrue(mock_task.delay.called)

    @patch("apps.hrm.models.InterviewSchedule")
    def test_interview_invite_nonexistent_schedule(self, mock_schedule_model):
        """Test interview invite for non-existent schedule returns 404."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        
        # Mock DoesNotExist exception
        from django.core.exceptions import ObjectDoesNotExist
        mock_schedule_model.objects.get.side_effect = ObjectDoesNotExist

        # Act
        response = self.client.post("/api/interview-schedules/999/interview_invite/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_interview_invite_requires_permission(self):
        """Test interview invite requires proper permissions."""
        # Arrange
        self.client.force_authenticate(user=self.user)  # Non-staff user

        # Act
        response = self.client.post("/api/interview-schedules/1/interview_invite/send/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CallbackFunctionalityTests(TestCase):
    """Test callback execution after successful email sends."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )

    @patch("apps.hrm.callbacks.mark_employee_onboarding_email_sent")
    @patch("apps.hrm.models.Employee")
    @patch("apps.mailtemplates.tasks.send_email_job_task")
    def test_callback_registered_on_send(self, mock_task, mock_employee_model, mock_callback):
        """Test callback is registered when sending email."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        
        mock_employee = mock_employee_model.return_value
        mock_employee.fullname = "Callback Test"
        mock_employee.email = "callback@example.com"
        mock_employee.start_date = "2025-11-01"

        # Act
        with patch("apps.hrm.api.views.employee.Employee.objects.get", return_value=mock_employee):
            response = self.client.post("/api/employees/1/welcome_email/send/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        
        # Verify job has callback data
        from apps.mailtemplates.models import EmailSendJob
        job_id = response.json()["data"]["job_id"]
        job = EmailSendJob.objects.get(id=job_id)
        self.assertIsNotNone(job.callback_data)
        self.assertIn("callback", job.callback_data)
