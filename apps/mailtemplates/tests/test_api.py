"""Tests for mail template API views."""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Permission, Role, User
from apps.mailtemplates.models import EmailSendJob


class TemplateAPITestCase(TestCase):
    """Test cases for template API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create permissions
        self.perm_list = Permission.objects.create(code="mailtemplate.list", description="View mail template list")
        self.perm_retrieve = Permission.objects.create(
            code="mailtemplate.retrieve", description="View mail template details"
        )
        self.perm_update = Permission.objects.create(code="mailtemplate.update", description="Update mail template")
        self.perm_preview = Permission.objects.create(code="mailtemplate.preview", description="Preview mail template")
        self.perm_send = Permission.objects.create(code="mailtemplate.send", description="Send bulk emails")
        self.perm_job_status = Permission.objects.create(
            code="mailtemplate.job_status", description="View email send job status"
        )

        # Create role with all permissions
        self.role = Role.objects.create(code="MAIL_USER", name="Mail User")
        self.role.permissions.add(
            self.perm_list,
            self.perm_retrieve,
            self.perm_update,
            self.perm_preview,
            self.perm_send,
            self.perm_job_status,
        )

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.user.role = self.role
        self.user.save()

        self.staff_user = User.objects.create_superuser(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.staff_user.role = self.role
        self.staff_user.save()

    def test_list_templates_authenticated(self):
        """Test listing templates requires authentication."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json()["data"], list)
        self.assertGreater(len(response.json()["data"]), 0)

    def test_list_templates_unauthenticated(self):
        """Test listing templates requires authentication."""
        # Arrange & Act
        # Don't authenticate - make request as anonymous user
        response = self.client.get("/api/mailtemplates/")

        # Assert
        # RoleBasedPermission requires authentication for views with permission codes
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_template_detail(self):
        """Test getting template details."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/welcome/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["slug"], "welcome")
        self.assertEqual(response.json()["data"]["title"], "Welcome Email")

    def test_get_template_not_found(self):
        """Test getting non-existent template."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/mailtemplates/nonexistent/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.mailtemplates.views.save_template_content")
    def test_save_template_requires_permission(self, mock_save):
        """Test saving template requires mailtemplate.update permission."""
        # Arrange
        # Create a user without the required permission
        basic_user = User.objects.create_user(
            username="basicuser",
            email="basic@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=basic_user)
        data = {"content": "<html>Test</html>"}

        # Act
        response = self.client.put("/api/mailtemplates/welcome/", data, format="json")

        # Assert
        # User doesn't have mailtemplate.update permission, should get 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Ensure template was never actually saved
        mock_save.assert_not_called()

    def test_preview_template_sample_mode(self):
        """Test previewing template with sample data."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {"data": {"fullname": "John Doe", "start_date": "2025-11-01"}}

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("html", response.json()["data"])
        self.assertIn("text", response.json()["data"])
        self.assertIn("John", response.json()["data"]["html"])

    def test_preview_template_validation_error(self):
        """Test preview fails with invalid data."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {"data": {}}  # Missing required fields

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.mailtemplates.views.send_email_job_task")
    def test_send_bulk_email_requires_permission(self, mock_task):
        """Test sending bulk email requires mailtemplate.send permission."""
        # Arrange
        # Create a user without the required permission
        basic_user = User.objects.create_user(
            username="basicuser2",
            email="basic2@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=basic_user)
        data = {
            "subject": "Test",
            "recipients": [{"email": "test@example.com", "data": {"fullname": "John", "start_date": "2025-11-01"}}],
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/send/", data, format="json")

        # Assert
        # User doesn't have mailtemplate.send permission
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.mailtemplates.views.send_email_job_task")
    def test_send_bulk_email_staff_user(self, mock_task):
        """Test staff user can send bulk emails."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        data = {
            "subject": "Test Subject",
            "sender": "sender@example.com",
            "recipients": [
                {"email": "user1@example.com", "data": {"fullname": "John Doe", "start_date": "2025-11-01"}},
                {"email": "user2@example.com", "data": {"fullname": "Jane Doe", "start_date": "2025-11-02"}},
            ],
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/send/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("job_id", response.json()["data"])
        self.assertIn("detail", response.json()["data"])

        # Verify job was created
        job_id = response.json()["data"]["job_id"]
        job = EmailSendJob.objects.get(id=job_id)
        self.assertEqual(job.template_slug, "welcome")
        self.assertEqual(job.subject, "Test Subject")
        self.assertEqual(job.total, 2)
        self.assertEqual(job.recipients.count(), 2)

        # Verify task was called
        mock_task.delay.assert_called_once_with(job_id)

    def test_get_send_job_status(self):
        """Test getting send job status."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)
        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Test",
            sender="test@example.com",
            total=1,
            created_by=self.staff_user,
        )

        # Act
        response = self.client.get(f"/api/mailtemplates/job/{job.id}/status/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["id"], str(job.id))
        self.assertEqual(response.json()["data"]["status"], "pending")

    def test_get_send_job_status_unauthorized(self):
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
        response = self.client.get(f"/api/mailtemplates/job/{job.id}/status/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
