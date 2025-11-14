"""Tests for notification signals."""

from unittest.mock import patch

import pytest

from apps.core.models import User
from apps.notifications.models import Notification
from apps.notifications.signals import handle_send_notification, trigger_send_notification, trigger_send_notifications


@pytest.mark.django_db
class TestNotificationSignals:
    """Test cases for notification signal handlers."""

    @pytest.fixture
    def actor(self):
        """Create an actor user."""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        return User.objects.create_superuser(
            username="actor",
            email="actor@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def recipient(self):
        """Create a recipient user."""
        return User.objects.create_superuser(
            username="recipient",
            email="recipient@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def notification_firebase(self, actor, recipient):
        """Create a notification with firebase delivery method."""
        return Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="liked your post",
            delivery_method=Notification.DeliveryMethod.FIREBASE,
        )

    @pytest.fixture
    def notification_email(self, actor, recipient):
        """Create a notification with email delivery method."""
        return Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="mentioned you",
            delivery_method=Notification.DeliveryMethod.EMAIL,
        )

    @pytest.fixture
    def notification_both(self, actor, recipient):
        """Create a notification with both delivery methods."""
        return Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="commented on your post",
            delivery_method=Notification.DeliveryMethod.BOTH,
        )

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_trigger_send_notification_firebase_only(self, mock_email_task, mock_push_task, notification_firebase):
        """Test that only push notification is sent for firebase delivery method."""
        # Act
        trigger_send_notification(notification_firebase)

        # Assert
        mock_push_task.delay.assert_called_once_with(notification_firebase.id)
        mock_email_task.delay.assert_not_called()

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_trigger_send_notification_email_only(self, mock_email_task, mock_push_task, notification_email):
        """Test that only email is sent for email delivery method."""
        # Act
        trigger_send_notification(notification_email)

        # Assert
        mock_email_task.delay.assert_called_once_with(notification_email.id)
        mock_push_task.delay.assert_not_called()

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_trigger_send_notification_both(self, mock_email_task, mock_push_task, notification_both):
        """Test that both email and push are sent for both delivery method."""
        # Act
        trigger_send_notification(notification_both)

        # Assert
        mock_email_task.delay.assert_called_once_with(notification_both.id)
        mock_push_task.delay.assert_called_once_with(notification_both.id)

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_trigger_send_notifications_bulk_firebase(self, mock_email_task, mock_push_task, actor, recipient):
        """Test bulk notification sending with firebase delivery method."""
        # Arrange
        notifications = [
            Notification.objects.create(
                actor=actor,
                recipient=recipient,
                verb=f"notification {i}",
                delivery_method=Notification.DeliveryMethod.FIREBASE,
            )
            for i in range(3)
        ]

        # Act
        trigger_send_notifications(notifications, "firebase")

        # Assert
        assert mock_push_task.delay.call_count == 3
        mock_email_task.delay.assert_not_called()

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_trigger_send_notifications_bulk_email(self, mock_email_task, mock_push_task, actor, recipient):
        """Test bulk notification sending with email delivery method."""
        # Arrange
        notifications = [
            Notification.objects.create(
                actor=actor,
                recipient=recipient,
                verb=f"notification {i}",
                delivery_method=Notification.DeliveryMethod.EMAIL,
            )
            for i in range(2)
        ]

        # Act
        trigger_send_notifications(notifications, "email")

        # Assert
        assert mock_email_task.delay.call_count == 2
        mock_push_task.delay.assert_not_called()

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_trigger_send_notifications_bulk_both(self, mock_email_task, mock_push_task, actor, recipient):
        """Test bulk notification sending with both delivery methods."""
        # Arrange
        notifications = [
            Notification.objects.create(
                actor=actor,
                recipient=recipient,
                verb=f"notification {i}",
                delivery_method=Notification.DeliveryMethod.BOTH,
            )
            for i in range(2)
        ]

        # Act
        trigger_send_notifications(notifications, "both")

        # Assert
        assert mock_email_task.delay.call_count == 2
        assert mock_push_task.delay.call_count == 2

    def test_handle_send_notification_raises_error_without_notification(self):
        """Test that handler raises error when neither notification nor notifications is provided."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            handle_send_notification(sender=Notification)

        assert "Either 'notification' or 'notifications' must be provided" in str(exc_info.value)

    def test_handle_send_notification_raises_error_without_delivery_method_for_bulk(self, actor, recipient):
        """Test that handler raises error when notifications is provided without delivery_method."""
        # Arrange
        notifications = [
            Notification.objects.create(
                actor=actor,
                recipient=recipient,
                verb="test",
                delivery_method=Notification.DeliveryMethod.FIREBASE,
            )
        ]

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            handle_send_notification(sender=Notification, notifications=notifications)

        assert "'delivery_method' must be provided when sending multiple notifications" in str(exc_info.value)

    @patch("apps.notifications.signals.send_push_notification_task")
    @patch("apps.notifications.signals.send_notification_email_task")
    def test_handle_send_notification_with_empty_notification_list(self, mock_email_task, mock_push_task):
        """Test that handler handles empty notification list gracefully."""
        # Act
        handle_send_notification(sender=Notification, notifications=[], delivery_method="firebase")

        # Assert
        mock_email_task.delay.assert_not_called()
        mock_push_task.delay.assert_not_called()
