"""Tests for notification tasks."""

from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.core.models import User, UserDevice
from apps.notifications.models import Notification
from apps.notifications.tasks import send_notification_email_task, send_push_notification_task


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
        from django.contrib.contenttypes.models import ContentType
        
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
            target=target_user,
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
            email="noemail@example.com",  # Email is required
            password="testpass123",
        )
        # Clear the email to test the handler
        recipient_no_email.email = ""
        recipient_no_email.save()
        
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


@pytest.mark.django_db
class TestPushNotificationTasks:
    """Test cases for FCM push notification tasks."""

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
        recipient = User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="testpass123",
        )
        # Create device for recipient
        UserDevice.objects.create(
            user=recipient,
            device_id="test-device-123",
            fcm_token="test-fcm-token",
            platform="android",
            active=True,
        )
        return recipient

    @pytest.fixture
    def notification(self, actor, recipient):
        """Create a basic notification."""
        return Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="commented on your post",
            message="This is great!",
        )

    @patch("apps.notifications.tasks.FCMService.send_notification")
    def test_send_push_notification_task_success(self, mock_send, notification):
        """Test successful push notification sending."""
        # Arrange
        mock_send.return_value = True

        # Act
        send_push_notification_task.apply(args=[notification.id]).get()

        # Assert
        mock_send.assert_called_once_with(notification)

    @patch("apps.notifications.tasks.FCMService.send_notification")
    def test_send_push_notification_task_failure(self, mock_send, notification):
        """Test push notification sending failure."""
        # Arrange
        mock_send.return_value = False

        # Act
        send_push_notification_task.apply(args=[notification.id]).get()

        # Assert
        mock_send.assert_called_once_with(notification)

    def test_send_push_notification_task_nonexistent_notification(self):
        """Test handling nonexistent notification."""
        # Act - should not raise an error
        send_push_notification_task.apply(args=[999999]).get()

        # Assert - no exception raised

    @patch("apps.notifications.tasks.FCMService.send_notification")
    def test_send_push_notification_task_retry_on_error(self, mock_send, notification):
        """Test that task retries on error."""
        # Arrange
        mock_send.side_effect = Exception("Network error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            send_push_notification_task.apply(args=[notification.id]).get()

        assert "Network error" in str(exc_info.value)
        # Task retries 3 times after initial attempt
        assert mock_send.call_count == 4
