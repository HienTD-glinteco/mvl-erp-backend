"""Comprehensive tests for mail templates including domain actions."""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import User
from apps.mailtemplates.models import EmailSendJob, EmailSendRecipient
from apps.mailtemplates.services import get_template_metadata, render_and_prepare_email


class MailTemplatesComprehensiveTest(TestCase):
    """Comprehensive test cases for all mail template functionality."""

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

    # ====== Template Listing Tests ======

    def test_list_templates_basic(self):
        """Test basic template listing."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["data"], list)
        self.assertGreater(len(data["data"]), 0)

        # Check template structure
        template = data["data"][0]
        self.assertIn("slug", template)
        self.assertIn("title", template)
        self.assertIn("description", template)
        self.assertIn("variables", template)
        self.assertIn("sample_data", template)

    def test_list_templates_with_preview(self):
        """Test template listing with sample preview."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/?include_preview=true")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]

        # Check preview fields are included
        template = data[0]
        self.assertIn("sample_preview_html", template)
        self.assertIn("sample_preview_text", template)

    def test_list_templates_unauthenticated(self):
        """Test unauthenticated access is denied."""
        # Act
        response = self.client.get("/api/mailtemplates/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ====== Template Detail Tests ======

    def test_get_template_detail(self):
        """Test getting specific template details."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/welcome/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["slug"], "welcome")
        self.assertEqual(data["title"], "Welcome Email")

    def test_get_template_with_content(self):
        """Test getting template with HTML content."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/welcome/?include_content=true")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("content", data)
        self.assertIn("<!DOCTYPE html>", data["content"])

    def test_get_nonexistent_template(self):
        """Test getting non-existent template returns 404."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/nonexistent/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ====== Template Save Tests ======

    @patch("apps.mailtemplates.views.save_template_content")
    def test_save_template_staff_only(self, mock_save):
        """Test only staff/users with mailtemplate.edit permission can save templates."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {"content": "<html><body>Test</body></html>"}

        # Act
        response = self.client.put("/api/mailtemplates/welcome/save/", data, format="json")

        # Assert
        # User doesn't have mailtemplate.edit permission, should get 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Ensure template was never actually saved
        mock_save.assert_not_called()

    @patch("apps.mailtemplates.views.save_template_content")
    def test_save_template_success(self, mock_save):
        """Test staff user can save template."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        data = {"content": "<html><body>Updated content</body></html>"}

        # Act
        response = self.client.put("/api/mailtemplates/welcome/save/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_save.called)
        result = response.json()["data"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["slug"], "welcome")

    # ====== Template Preview Tests ======

    def test_preview_template_sample_mode(self):
        """Test previewing template in sample mode."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {
            "data": {
                "fullname": "Jane Smith",
                "start_date": "2025-12-01",
            }
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["data"]
        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Jane Smith", result["html"])

    def test_preview_template_merges_sample_data(self):
        """Test preview merges request data with sample_data."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        # Only provide fullname, should get start_date from sample_data
        data = {"data": {"fullname": "Test User"}}

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["data"]
        # Should have both fullname from request and start_date from sample_data
        self.assertIn("Test User", result["html"])

    def test_preview_template_validation_error(self):
        """Test preview fails when required variables missing."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {"data": {}}  # Missing required fields

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ====== Bulk Send Tests ======

    @patch("apps.mailtemplates.views.send_email_job_task")
    def test_send_bulk_email_creates_job(self, mock_task):
        """Test bulk send creates job and enqueues task."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        data = {
            "subject": "Welcome to the team!",
            "sender": "hr@example.com",
            "recipients": [
                {
                    "email": "employee1@example.com",
                    "data": {"fullname": "John Doe", "start_date": "2025-11-01"},
                },
                {
                    "email": "employee2@example.com",
                    "data": {"fullname": "Jane Smith", "start_date": "2025-11-02"},
                },
            ],
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/send/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = response.json()["data"]
        self.assertIn("job_id", result)

        # Verify job created
        job = EmailSendJob.objects.get(id=result["job_id"])
        self.assertEqual(job.template_slug, "welcome")
        self.assertEqual(job.subject, "Welcome to the team!")
        self.assertEqual(job.total, 2)
        self.assertEqual(job.recipients.count(), 2)

        # Verify task enqueued
        mock_task.delay.assert_called_once_with(result["job_id"])

    @patch("apps.mailtemplates.tasks.send_email_job_task")
    def test_send_bulk_email_permission_required(self, mock_task):
        """Test bulk send requires staff permission."""
        # Arrange
        self.client.force_authenticate(user=self.user)  # Non-staff
        data = {
            "subject": "Test",
            "recipients": [{"email": "test@example.com", "data": {"fullname": "Test", "start_date": "2025-11-01"}}],
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/send/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ====== Job Status Tests ======

    def test_get_job_status_owner(self):
        """Test job owner can view status."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Test",
            sender="test@example.com",
            total=2,
            sent_count=1,
            failed_count=0,
            status="running",
            created_by=self.staff_user,
        )
        recipient = EmailSendRecipient.objects.create(
            job=job,
            email="test@example.com",
            data={"fullname": "Test", "start_date": "2025-11-01"},
            status="sent",
        )

        # Act
        response = self.client.get(f"/api/mailtemplates/send/{job.id}/status/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["id"], str(job.id))
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["sent_count"], 1)
        self.assertEqual(len(data["recipients_status"]), 1)

    def test_get_job_status_non_owner_forbidden(self):
        """Test non-owner cannot view job status."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Test",
            sender="test@example.com",
            total=1,
            created_by=self.staff_user,  # Different user
        )

        # Act
        response = self.client.get(f"/api/mailtemplates/send/{job.id}/status/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ====== Service Layer Tests ======

    def test_render_and_prepare_email_service(self):
        """Test the render_and_prepare_email service function."""
        # Arrange
        template_meta = get_template_metadata("welcome")
        data = {
            "fullname": "Service Test User",
            "start_date": "2025-11-15",
        }

        # Act
        result = render_and_prepare_email(template_meta, data)

        # Assert
        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Service Test User", result["html"])
        self.assertIn("2025-11-15", result["html"])
        # Check CSS was inlined
        self.assertIn("<style>", result["html"])

    def test_render_with_optional_variables(self):
        """Test rendering with optional variables works."""
        # Arrange
        template_meta = get_template_metadata("welcome")
        data = {
            "fullname": "Test User",
            "start_date": "2025-11-01",
            # position and department are optional
        }

        # Act
        result = render_and_prepare_email(template_meta, data, validate=False)

        # Assert
        self.assertIsNotNone(result["html"])
        self.assertIn("Test User", result["html"])
