"""Tests for notification email tasks."""

from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.core.models import User
from apps.notifications.models import Notification
from apps.notifications.tasks import send_notification_email_task


@pytest.mark.django_db
class TestNotificationEmailTasks:
    """Test cases for notification email tasks."""

    @pytest.fixture
    def actor(self):
        """Create an actor user."""
        return User.objects.create_user(
            username="actor",
            email="actor@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def recipient(self):
        """Create a recipient user."""
        return User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="testpass123",
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    @patch("apps.notifications.tasks.send_mail")
    def test_send_notification_email_task_success(self, mock_send_mail, actor, recipient):
        """Test sending notification email successfully."""
        # Arrange
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="commented on your post",
            message="Great work!",
        )
        mock_send_mail.return_value = 1

        # Act
        result = send_notification_email_task.apply(args=[notification.id]).get()

        # Assert
        assert result is True
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args[1]
        assert call_kwargs["recipient_list"] == ["recipient@example.com"]
        assert "New Notification" in call_kwargs["subject"]
        assert "recipient" in call_kwargs["message"]
        assert "actor" in call_kwargs["message"]

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    @patch("apps.notifications.tasks.send_mail")
    def test_send_notification_email_task_without_message(self, mock_send_mail, actor, recipient):
        """Test sending notification email without custom message."""
        # Arrange
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="liked your comment",
        )
        mock_send_mail.return_value = 1

        # Act
        result = send_notification_email_task.apply(args=[notification.id]).get()

        # Assert
        assert result is True
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args[1]
        assert call_kwargs["recipient_list"] == ["recipient@example.com"]

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    @patch("apps.notifications.tasks.send_mail")
    def test_send_notification_email_task_with_target_info(self, mock_send_mail, actor, recipient):
        """Test sending notification email with target information."""
        # Arrange
        # Use another user as target for testing
        target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="testpass123",
        )
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="assigned you to",
            message="Please review this task",
            target_content_type=User.objects.get(username="target").__class__.__name__,
            target_object_id=str(target_user.id),
        )
        mock_send_mail.return_value = 1

        # Act
        result = send_notification_email_task.apply(args=[notification.id]).get()

        # Assert
        assert result is True
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args[1]
        assert "target" in call_kwargs["message"]

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    @patch("apps.notifications.tasks.send_mail")
    def test_send_notification_email_task_failure_retries(self, mock_send_mail, actor, recipient):
        """Test that the task retries on failure."""
        # Arrange
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="mentioned you",
        )
        mock_send_mail.side_effect = Exception("SMTP connection failed")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            send_notification_email_task.apply(args=[notification.id]).get()

        assert "SMTP connection failed" in str(exc_info.value)
        # Task retries 3 times after initial attempt
        assert mock_send_mail.call_count == 4

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    @patch("apps.notifications.tasks.render_to_string")
    @patch("apps.notifications.tasks.send_mail")
    def test_send_notification_email_task_template_error(self, mock_send_mail, mock_render, actor, recipient):
        """Test handling template rendering errors."""
        # Arrange
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="shared a document with you",
        )
        mock_render.side_effect = Exception("Template not found")
        mock_send_mail.return_value = 1

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            send_notification_email_task.apply(args=[notification.id]).get()

        assert "Template not found" in str(exc_info.value)
        # Task retries 3 times after initial attempt
        assert mock_render.call_count == 4

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    def test_send_notification_email_task_nonexistent_notification(self):
        """Test handling nonexistent notification."""
        # Act
        result = send_notification_email_task.apply(args=[999999]).get()

        # Assert
        assert result is False

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@maivietland.com",
    )
    @patch("apps.notifications.tasks.send_mail")
    def test_send_notification_email_task_recipient_no_email(self, mock_send_mail, actor):
        """Test handling recipient without email address."""
        # Arrange
        recipient_no_email = User.objects.create_user(
            username="no_email",
            email="",  # No email
            password="testpass123",
        )
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_no_email,
            verb="mentioned you",
        )

        # Act
        result = send_notification_email_task.apply(args=[notification.id]).get()

        # Assert
        assert result is False
        mock_send_mail.assert_not_called()
