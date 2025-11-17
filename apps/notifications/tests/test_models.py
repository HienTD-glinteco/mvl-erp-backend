import pytest
from django.contrib.contenttypes.models import ContentType

from apps.core.models import User
from apps.notifications.models import Notification


@pytest.mark.django_db
class TestNotificationModel:
    """Test cases for Notification model."""

    def test_create_notification(self):
        """Test creating a basic notification."""
        # Arrange
        # Changed to superuser to bypass RoleBasedPermission for API tests
        actor = User.objects.create_superuser(
            username="actor_user",
            email="actor@example.com",
            password="password123",
        )
        recipient = User.objects.create_superuser(
            username="recipient_user",
            email="recipient@example.com",
            password="password123",
        )

        # Act
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="commented on",
            message="This is a test notification",
        )

        # Assert
        assert notification.actor == actor
        assert notification.recipient == recipient
        assert notification.verb == "commented on"
        assert notification.message == "This is a test notification"
        assert notification.read is False
        assert str(notification) == f"{actor} commented on - {recipient}"

    def test_create_notification_with_target(self):
        """Test creating a notification with a target object."""
        # Arrange
        actor = User.objects.create_superuser(
            username="actor_user",
            email="actor@example.com",
            password="password123",
        )
        recipient = User.objects.create_superuser(
            username="recipient_user",
            email="recipient@example.com",
            password="password123",
        )
        target_user = User.objects.create_superuser(
            username="target_user",
            email="target@example.com",
            password="password123",
        )
        content_type = ContentType.objects.get_for_model(User)

        # Act
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="mentioned you in",
            target_content_type=content_type,
            target_object_id=str(target_user.id),
        )

        # Assert
        assert notification.target == target_user
        assert notification.target_content_type == content_type
        assert notification.target_object_id == str(target_user.id)

    def test_mark_as_read(self):
        """Test marking a notification as read."""
        # Arrange
        actor = User.objects.create_superuser(
            username="actor_user",
            email="actor@example.com",
            password="password123",
        )
        recipient = User.objects.create_superuser(
            username="recipient_user",
            email="recipient@example.com",
            password="password123",
        )
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="sent you a message",
        )
        assert notification.read is False

        # Act
        notification.mark_as_read()

        # Assert
        notification.refresh_from_db()
        assert notification.read is True

    def test_mark_as_unread(self):
        """Test marking a notification as unread."""
        # Arrange
        actor = User.objects.create_superuser(
            username="actor_user",
            email="actor@example.com",
            password="password123",
        )
        recipient = User.objects.create_superuser(
            username="recipient_user",
            email="recipient@example.com",
            password="password123",
        )
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="assigned you a task",
            read=True,
        )
        assert notification.read is True

        # Act
        notification.mark_as_unread()

        # Assert
        notification.refresh_from_db()
        assert notification.read is False

    def test_notification_ordering(self):
        """Test that notifications are ordered by creation time (newest first)."""
        # Arrange
        actor = User.objects.create_superuser(
            username="actor_user",
            email="actor@example.com",
            password="password123",
        )
        recipient = User.objects.create_superuser(
            username="recipient_user",
            email="recipient@example.com",
            password="password123",
        )

        # Act - Create multiple notifications
        notification1 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="first notification",
        )
        notification2 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="second notification",
        )
        notification3 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="third notification",
        )

        # Assert - Newest first
        notifications = Notification.objects.filter(recipient=recipient)
        assert list(notifications) == [notification3, notification2, notification1]
