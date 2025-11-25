"""Tests for mailtemplate enhancements: subject preview, multi-recipient, per-recipient callbacks, bulk send."""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Permission, Role, User
from apps.mailtemplates.models import EmailSendJob, EmailSendRecipient
from apps.mailtemplates.services import get_template_metadata


class SubjectPreviewTestCase(TestCase):
    """Test cases for subject in preview response."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create permissions
        perm_preview = Permission.objects.create(code="mailtemplate.preview", description="Preview mail template")

        # Create role with preview permission
        role = Role.objects.create(code="MAIL_USER", name="Mail User")
        role.permissions.add(perm_preview)

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.user.role = role
        self.user.save()

    def test_preview_includes_subject_from_data(self):
        """TC1: Preview returns subject from data when provided."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {
            "data": {
                "fullname": "John Doe",
                "start_date": "2025-11-01",
                "subject": "Custom Welcome Subject",
            }
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["data"]
        self.assertIn("subject", result)
        self.assertEqual(result["subject"], "Custom Welcome Subject")

    def test_preview_includes_default_subject_when_not_in_data(self):
        """TC2: Preview returns default_subject from TEMPLATE_REGISTRY when data has no subject."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {
            "data": {
                "employee_fullname": "John Doe",
                "employee_email": "john.doe@example.com",
                "employee_username": "john.doe",
                "employee_start_date": "2025-11-01",
                "employee_code": "MVL001",
                "employee_department_name": "Sales",
                "new_password": "Abc12345",
                "logo_image_url": "/static/img/email_logo.png",
            }
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["data"]
        self.assertIn("subject", result)
        # Should use default_subject from TEMPLATE_REGISTRY
        template_meta = get_template_metadata("welcome")
        self.assertEqual(result["subject"], template_meta["default_subject"])

    def test_preview_includes_subject_when_no_data_provided(self):
        """TC3: Preview returns default_subject when no data provided (sample mode)."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {}

        # Act
        response = self.client.post("/api/mailtemplates/welcome/preview/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["data"]
        self.assertIn("subject", result)
        template_meta = get_template_metadata("welcome")
        self.assertEqual(result["subject"], template_meta["default_subject"])


class MultiRecipientTestCase(TestCase):
    """Test cases for multi-recipient support via get_recipients hook."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create permission and role
        perm_send = Permission.objects.create(code="mailtemplate.send", description="Send bulk emails")
        role = Role.objects.create(code="MAIL_USER", name="Mail User")
        role.permissions.add(perm_send)

        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.user.role = role
        self.user.save()

    @patch("apps.mailtemplates.views.send_email_job_task")
    def test_send_with_multiple_recipients_from_request(self, mock_task):
        """TC5: Multiple recipients results in correct job.total."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {
            "subject": "Test Subject",
            "recipients": [
                {
                    "email": "user1@example.com",
                    "data": {
                        "employee_fullname": "User 1",
                        "employee_email": "user1@example.com",
                        "employee_username": "user1",
                        "employee_start_date": "2025-11-01",
                        "employee_code": "MVL001",
                        "employee_department_name": "Sales",
                        "new_password": "Abc12345",
                        "logo_image_url": "/static/img/email_logo.png",
                    },
                },
                {
                    "email": "user2@example.com",
                    "data": {
                        "employee_fullname": "User 2",
                        "employee_email": "user2@example.com",
                        "employee_username": "user2",
                        "employee_start_date": "2025-11-02",
                        "employee_code": "MVL002",
                        "employee_department_name": "Sales",
                        "new_password": "Abc12345",
                        "logo_image_url": "/static/img/email_logo.png",
                    },
                },
                {
                    "email": "user3@example.com",
                    "data": {
                        "employee_fullname": "User 3",
                        "employee_email": "user3@example.com",
                        "employee_username": "user3",
                        "employee_start_date": "2025-11-03",
                        "employee_code": "MVL003",
                        "employee_department_name": "Sales",
                        "new_password": "Abc12345",
                        "logo_image_url": "/static/img/email_logo.png",
                    },
                },
            ],
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/send/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = response.json()["data"]
        self.assertIn("job_id", result)
        self.assertEqual(result["total_recipients"], 3)

        # Verify job and recipients
        job = EmailSendJob.objects.get(id=result["job_id"])
        self.assertEqual(job.total, 3)
        self.assertEqual(job.recipients.count(), 3)

        # Verify recipient emails
        emails = [r.email for r in job.recipients.all()]
        self.assertIn("user1@example.com", emails)
        self.assertIn("user2@example.com", emails)
        self.assertIn("user3@example.com", emails)


class PerRecipientCallbackTestCase(TestCase):
    """Test cases for per-recipient callback_data."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create permission and role
        perm_send = Permission.objects.create(code="mailtemplate.send", description="Send bulk emails")
        role = Role.objects.create(code="MAIL_USER", name="Mail User")
        role.permissions.add(perm_send)

        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.user.role = role
        self.user.save()

    @patch("apps.mailtemplates.views.send_email_job_task")
    def test_recipient_callback_data_is_saved(self, mock_task):
        """TC6: Recipient callback_data is stored in EmailSendRecipient."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        data = {
            "subject": "Test Subject",
            "recipients": [
                {
                    "email": "user1@example.com",
                    "data": {
                        "employee_fullname": "User 1",
                        "employee_email": "user.1@example.com",
                        "employee_username": "user.1",
                        "employee_start_date": "2025-11-01",
                        "employee_code": "MVL01",
                        "employee_department_name": "Sales",
                        "new_password": "Abc12345",
                        "logo_image_url": "/static/img/email_logo.png",
                    },
                    "callback_data": {"candidate_id": 123, "action": "mark_invited"},
                },
                {
                    "email": "user2@example.com",
                    "data": {
                        "employee_fullname": "User 2",
                        "employee_email": "user.2@example.com",
                        "employee_username": "user.2",
                        "employee_start_date": "2025-11-02",
                        "employee_code": "MVL02",
                        "employee_department_name": "Sales",
                        "new_password": "Abc12345",
                        "logo_image_url": "/static/img/email_logo.png",
                    },
                    "callback_data": {"candidate_id": 456, "action": "mark_invited"},
                },
            ],
        }

        # Act
        response = self.client.post("/api/mailtemplates/welcome/send/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job_id = response.json()["data"]["job_id"]
        job = EmailSendJob.objects.get(id=job_id)

        # Verify callback_data is stored
        recipients = job.recipients.all().order_by("email")
        self.assertEqual(recipients[0].callback_data, {"candidate_id": 123, "action": "mark_invited"})
        self.assertEqual(recipients[1].callback_data, {"candidate_id": 456, "action": "mark_invited"})

    @patch("apps.mailtemplates.tasks.EmailMultiAlternatives")
    def test_per_recipient_callback_executed(self, mock_email):
        """TC8: Per-recipient callback is executed after successful send."""
        # Arrange
        from apps.mailtemplates.tasks import send_single_email

        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Test",
            sender="test@example.com",
            total=1,
        )
        recipient = EmailSendRecipient.objects.create(
            job=job,
            email="test@example.com",
            data={
                "employee_fullname": "Test User",
                "employee_email": "test.user@example.com",
                "employee_username": "test.user",
                "employee_start_date": "2025-11-01",
                "employee_code": "MVL01",
                "employee_department_name": "Sales",
                "new_password": "Abc12345",
                "logo_image_url": "/static/img/email_logo.png",
            },
            callback_data={
                "path": "apps.mailtemplates.tests.test_enhancements.dummy_callback",
                "app_label": "core",
                "model_name": "User",
                "object_id": self.user.id,
            },
        )

        # Mock email send
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance

        template_meta = get_template_metadata("welcome")

        # Act
        with patch("apps.mailtemplates.tasks.execute_callback") as mock_callback:
            result = send_single_email(recipient, job, template_meta, max_attempts=1)

        # Assert
        self.assertTrue(result)
        mock_callback.assert_called_once()
        # Verify callback was called with recipient's callback_data
        callback_data = mock_callback.call_args[0][0]
        self.assertEqual(callback_data["path"], "apps.mailtemplates.tests.test_enhancements.dummy_callback")


class SubjectPriorityTestCase(TestCase):
    """Test cases for subject priority in email sending."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @patch("apps.mailtemplates.tasks.EmailMultiAlternatives")
    def test_subject_priority_recipient_data(self, mock_email):
        """TC7: Subject from recipient.data has highest priority."""
        # Arrange
        from apps.mailtemplates.tasks import send_single_email

        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Job Level Subject",
            sender="test@example.com",
            total=1,
        )
        recipient = EmailSendRecipient.objects.create(
            job=job,
            email="test@example.com",
            data={
                "employee_fullname": "Test User",
                "employee_email": "test.user@example.com",
                "employee_username": "test.user",
                "employee_start_date": "2025-11-01",
                "employee_code": "MVL001",
                "employee_department_name": "Sales",
                "new_password": "Abc12345",
                "logo_image_url": "/static/img/email_logo.png",
                "subject": "Recipient Level Subject",
            },
        )

        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance

        template_meta = get_template_metadata("welcome")

        # Act
        send_single_email(recipient, job, template_meta, max_attempts=1)

        # Assert
        # Check that email was created with recipient-level subject
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args[1]
        self.assertEqual(call_kwargs["subject"], "Recipient Level Subject")

    @patch("apps.mailtemplates.tasks.EmailMultiAlternatives")
    def test_subject_priority_job_level(self, mock_email):
        """TC7: Subject from job is used when recipient.data has no subject."""
        # Arrange
        from apps.mailtemplates.tasks import send_single_email

        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Job Level Subject",
            sender="test@example.com",
            total=1,
        )
        recipient = EmailSendRecipient.objects.create(
            job=job,
            email="test@example.com",
            data={
                "employee_fullname": "Test User",
                "employee_email": "test.user@example.com",
                "employee_username": "test.user",
                "employee_start_date": "2025-11-01",
                "employee_code": "MVL01",
                "employee_department_name": "Sales",
                "new_password": "Abc12345",
                "logo_image_url": "/static/img/email_logo.png",
            },
        )

        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance

        template_meta = get_template_metadata("welcome")

        # Act
        send_single_email(recipient, job, template_meta, max_attempts=1)

        # Assert
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args[1]
        self.assertEqual(call_kwargs["subject"], "Job Level Subject")

    @patch("apps.mailtemplates.tasks.EmailMultiAlternatives")
    def test_subject_priority_template_default(self, mock_email):
        """TC7: Template default_subject is used when job has no subject."""
        # Arrange
        from apps.mailtemplates.tasks import send_single_email

        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="",  # Empty subject
            sender="test@example.com",
            total=1,
        )
        recipient = EmailSendRecipient.objects.create(
            job=job,
            email="test@example.com",
            data={
                "employee_fullname": "Test User",
                "employee_email": "test.user@example.com",
                "employee_username": "test.user",
                "employee_start_date": "2025-11-01",
                "employee_code": "MVL01",
                "employee_department_name": "Sales",
                "new_password": "Abc12345",
                "logo_image_url": "/static/img/email_logo.png",
            },
        )

        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance

        template_meta = get_template_metadata("welcome")

        # Act
        send_single_email(recipient, job, template_meta, max_attempts=1)

        # Assert
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args[1]
        self.assertEqual(call_kwargs["subject"], template_meta["default_subject"])


class SendFailureTestCase(TestCase):
    """Test cases for send failures."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @patch("apps.mailtemplates.tasks.EmailMultiAlternatives")
    def test_send_failure_increments_attempts(self, mock_email):
        """TC9: Failed send increments attempts and sets status to FAILED."""
        # Arrange
        from apps.mailtemplates.tasks import send_single_email

        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Test",
            sender="test@example.com",
            total=1,
        )
        recipient = EmailSendRecipient.objects.create(
            job=job,
            email="test@example.com",
            data={
                "employee_fullname": "Test User",
                "employee_email": "test.user@example.com",
                "employee_username": "test.user",
                "employee_start_date": "2025-11-01",
                "employee_code": "MVL01",
                "employee_department_name": "Sales",
                "new_password": "Abc12345",
                "logo_image_url": "/static/img/email_logo.png",
            },
        )

        # Mock email to raise exception
        mock_email_instance = MagicMock()
        mock_email_instance.send.side_effect = Exception("Send failed")
        mock_email.return_value = mock_email_instance

        template_meta = get_template_metadata("welcome")

        # Act
        result = send_single_email(recipient, job, template_meta, max_attempts=2)

        # Assert
        self.assertFalse(result)
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, EmailSendRecipient.Status.FAILED)
        self.assertEqual(recipient.attempts, 2)
        self.assertIn("Send failed", recipient.last_error)


# Dummy callback for testing
def dummy_callback(instance, recipient, **kwargs):
    """Dummy callback function for testing."""
    pass
