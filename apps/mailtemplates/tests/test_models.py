"""Tests for mail template models."""

from django.test import TestCase

from apps.core.models import User
from apps.mailtemplates.models import EmailSendJob, EmailSendRecipient


class EmailSendJobModelTestCase(TestCase):
    """Test cases for EmailSendJob model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_create_email_send_job(self):
        """Test creating an email send job."""
        # Arrange & Act
        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Welcome!",
            sender="noreply@example.com",
            total=5,
            created_by=self.user,
        )

        # Assert
        self.assertEqual(job.template_slug, "welcome")
        self.assertEqual(job.subject, "Welcome!")
        self.assertEqual(job.total, 5)
        self.assertEqual(job.sent_count, 0)
        self.assertEqual(job.failed_count, 0)
        self.assertEqual(job.status, EmailSendJob.Status.PENDING)
        self.assertEqual(job.created_by, self.user)
        self.assertIsNotNone(job.id)

    def test_email_send_job_str(self):
        """Test string representation of EmailSendJob."""
        # Arrange
        job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Test",
            sender="test@example.com",
            total=1,
        )

        # Act
        result = str(job)

        # Assert
        self.assertIn("welcome", result)
        self.assertIn("pending", result)


class EmailSendRecipientModelTestCase(TestCase):
    """Test cases for EmailSendRecipient model."""

    def setUp(self):
        """Set up test data."""
        self.job = EmailSendJob.objects.create(
            template_slug="welcome",
            subject="Welcome",
            sender="noreply@example.com",
            total=1,
        )

    def test_create_email_send_recipient(self):
        """Test creating an email send recipient."""
        # Arrange & Act
        recipient = EmailSendRecipient.objects.create(
            job=self.job,
            email="recipient@example.com",
            data={"first_name": "John", "start_date": "2025-11-01"},
        )

        # Assert
        self.assertEqual(recipient.job, self.job)
        self.assertEqual(recipient.email, "recipient@example.com")
        self.assertEqual(recipient.data["first_name"], "John")
        self.assertEqual(recipient.status, EmailSendRecipient.Status.PENDING)
        self.assertEqual(recipient.attempts, 0)
        self.assertIsNotNone(recipient.id)

    def test_email_send_recipient_str(self):
        """Test string representation of EmailSendRecipient."""
        # Arrange
        recipient = EmailSendRecipient.objects.create(
            job=self.job,
            email="test@example.com",
            data={},
        )

        # Act
        result = str(recipient)

        # Assert
        self.assertIn("test@example.com", result)
        self.assertIn("pending", result)

    def test_recipient_status_update(self):
        """Test updating recipient status."""
        # Arrange
        recipient = EmailSendRecipient.objects.create(
            job=self.job,
            email="test@example.com",
            data={},
        )

        # Act
        recipient.status = EmailSendRecipient.Status.SENT
        recipient.attempts = 1
        recipient.save()

        # Assert
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, EmailSendRecipient.Status.SENT)
        self.assertEqual(recipient.attempts, 1)
