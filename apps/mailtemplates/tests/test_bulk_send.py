"""Tests for bulk_send_template_mail functionality."""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.core.models import User
from apps.mailtemplates.models import EmailSendJob
from apps.mailtemplates.view_mixins import EmailTemplateActionMixin


def wrap_request(factory_request, user):
    """Helper to wrap Django request in DRF Request."""
    from rest_framework.parsers import JSONParser

    factory_request.user = user
    return Request(factory_request, parsers=[JSONParser()])


class MockInstance:
    """Mock instance for testing."""

    def __init__(self, pk, email, name):
        self.pk = pk
        self.id = pk
        self.email = email
        self.name = name


class MockViewSet(EmailTemplateActionMixin):
    """Mock ViewSet with EmailTemplateActionMixin for testing."""

    def get_queryset(self):
        """Return mock queryset."""
        return self._mock_queryset

    def get_object(self):
        """Return mock object."""
        return self._mock_object

    def get_template_action_data(self, instance, template_slug):
        """Extract data from mock instance."""
        return {
            "fullname": instance.name,
            "start_date": "2025-11-01",
        }

    def get_template_action_email(self, instance, template_slug):
        """Get email from mock instance."""
        return instance.email


class BulkSendTemplateMailTestCase(TestCase):
    """Test cases for bulk_send_template_mail method."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.viewset = MockViewSet()

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_bulk_send_with_object_ids(self, mock_task):
        """TC10a: Bulk send with object_ids creates single job with all recipients."""
        # Arrange
        mock_instances = [
            MockInstance(1, "user1@example.com", "User 1"),
            MockInstance(2, "user2@example.com", "User 2"),
            MockInstance(3, "user3@example.com", "User 3"),
        ]

        # Mock queryset
        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = mock_instances
        self.viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "welcome",
            "object_ids": [1, 2, 3],
            "subject": "Bulk Welcome",
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = self.viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = response.data
        self.assertIn("job_id", result)
        self.assertEqual(result["total_recipients"], 3)

        # Verify job created
        job = EmailSendJob.objects.get(id=result["job_id"])
        self.assertEqual(job.template_slug, "welcome")
        self.assertEqual(job.subject, "Bulk Welcome")
        self.assertEqual(job.total, 3)

        # Verify recipients created
        recipients = job.recipients.all()
        self.assertEqual(recipients.count(), 3)
        emails = [r.email for r in recipients]
        self.assertIn("user1@example.com", emails)
        self.assertIn("user2@example.com", emails)
        self.assertIn("user3@example.com", emails)

        # Verify task enqueued
        mock_task.delay.assert_called_once_with(str(job.id))

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_bulk_send_with_filters(self, mock_task):
        """Test bulk send with filters parameter."""
        # Arrange
        mock_instances = [
            MockInstance(1, "user1@example.com", "User 1"),
            MockInstance(2, "user2@example.com", "User 2"),
        ]

        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = mock_instances
        self.viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "welcome",
            "filters": {"department": "Engineering"},
            "subject": "Welcome Engineers",
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = self.viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = response.data
        self.assertEqual(result["total_recipients"], 2)

        # Verify filters were passed to queryset
        mock_queryset.filter.assert_called_once_with(department="Engineering")

    def test_bulk_send_without_object_ids_or_filters(self):
        """TC10b: Bulk send without object_ids or filters returns 400."""
        # Arrange
        request_data = {
            "template_slug": "welcome",
            "subject": "Test",
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act & Assert - Should raise ValidationError during serializer validation
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            response = self.viewset.bulk_send_template_mail(request)

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_bulk_send_uses_default_subject(self, mock_task):
        """Test bulk send uses template default_subject when not provided."""
        # Arrange
        mock_instances = [MockInstance(1, "user1@example.com", "User 1")]

        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = mock_instances
        self.viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "welcome",
            "object_ids": [1],
            # No subject provided
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = self.viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job = EmailSendJob.objects.get(id=response.data["job_id"])
        # Should use default_subject from template
        from apps.mailtemplates.services import get_template_metadata

        template_meta = get_template_metadata("welcome")
        self.assertEqual(job.subject, template_meta["default_subject"])

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_bulk_send_with_client_request_id(self, mock_task):
        """Test bulk send stores client_request_id for idempotency."""
        # Arrange
        mock_instances = [MockInstance(1, "user1@example.com", "User 1")]

        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = mock_instances
        self.viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "welcome",
            "object_ids": [1],
            "client_request_id": "bulk-2025-11-06",
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = self.viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job = EmailSendJob.objects.get(id=response.data["job_id"])
        self.assertEqual(job.client_request_id, "bulk-2025-11-06")


class MultiRecipientPerInstanceTestCase(TestCase):
    """Test cases for get_recipients returning multiple recipients per instance."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
        )

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_bulk_send_with_multi_recipient_per_instance(self, mock_task):
        """Test bulk send where each instance has multiple recipients."""

        class MultiRecipientViewSet(EmailTemplateActionMixin):
            """ViewSet that returns multiple recipients per instance."""

            def get_queryset(self):
                return self._mock_queryset

            def get_recipients(self, request, instance):
                """Return multiple recipients for each instance."""
                # Simulating a schedule with multiple candidates
                return [
                    {
                        "email": f"candidate1_{instance.id}@example.com",
                        "data": {
                            "candidate_name": f"Candidate 1 for {instance.name}",
                            "position": "Software Engineer",
                            "interview_date": "2025-11-01",
                            "interview_time": "10:00 AM",
                        },
                        "callback_data": {"candidate_id": f"{instance.id}_1"},
                    },
                    {
                        "email": f"candidate2_{instance.id}@example.com",
                        "data": {
                            "candidate_name": f"Candidate 2 for {instance.name}",
                            "position": "Software Engineer",
                            "interview_date": "2025-11-01",
                            "interview_time": "02:00 PM",
                        },
                        "callback_data": {"candidate_id": f"{instance.id}_2"},
                    },
                ]

        # Arrange
        viewset = MultiRecipientViewSet()
        mock_instances = [
            MockInstance(1, "schedule1@example.com", "Schedule 1"),
            MockInstance(2, "schedule2@example.com", "Schedule 2"),
        ]

        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = mock_instances
        viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "interview_invite",
            "object_ids": [1, 2],
            "subject": "Interview Invitation",
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = response.data
        # 2 instances * 2 recipients each = 4 total recipients
        self.assertEqual(result["total_recipients"], 4)

        # Verify job and recipients
        job = EmailSendJob.objects.get(id=result["job_id"])
        self.assertEqual(job.total, 4)
        self.assertEqual(job.recipients.count(), 4)

        # Verify callback_data is stored for each recipient
        recipients = job.recipients.all()
        for recipient in recipients:
            self.assertIsNotNone(recipient.callback_data)
            self.assertIn("candidate_id", recipient.callback_data)


class BulkSendValidationTestCase(TestCase):
    """Test cases for bulk send validation."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.viewset = MockViewSet()

    def test_bulk_send_with_nonexistent_template(self):
        """Test bulk send with invalid template returns 404."""
        # Arrange
        mock_instances = [MockInstance(1, "user1@example.com", "User 1")]
        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = mock_instances
        self.viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "nonexistent",
            "object_ids": [1],
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = self.viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_bulk_send_with_empty_result_set(self):
        """Test bulk send with no matching objects returns 400."""
        # Arrange
        mock_queryset = MagicMock()
        mock_queryset.filter.return_value = []  # Empty queryset
        self.viewset._mock_queryset = mock_queryset

        request_data = {
            "template_slug": "welcome",
            "object_ids": [999],
        }
        factory_request = self.factory.post(
            "/api/test/bulk_send/", data=json.dumps(request_data), content_type="application/json"
        )
        request = wrap_request(factory_request, self.user)

        # Act
        response = self.viewset.bulk_send_template_mail(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No recipients found", str(response.data))
