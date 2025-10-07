import pytest

from apps.core.models import User
from apps.notifications.models import Notification
from apps.notifications.utils import create_bulk_notifications, create_notification, notify_user


@pytest.mark.django_db
class TestNotificationUtils:
    """Test cases for notification utility functions."""

    @pytest.fixture
    def actor(self):
        """Create an actor user."""
        return User.objects.create_user(
            username="actor",
            email="actor@example.com",
            password="password123",
        )

    @pytest.fixture
    def recipient(self):
        """Create a recipient user."""
        return User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="password123",
        )

    def test_create_notification(self, actor, recipient):
        """Test creating a basic notification using utility function."""
        # Act
        notification = create_notification(
            actor=actor,
            recipient=recipient,
            verb="liked your post",
            message="This is great!",
        )

        # Assert
        assert notification.actor == actor
        assert notification.recipient == recipient
        assert notification.verb == "liked your post"
        assert notification.message == "This is great!"
        assert notification.read is False
        assert Notification.objects.count() == 1

    def test_create_notification_with_target(self, actor, recipient):
        """Test creating a notification with a target object."""
        # Arrange - Use User as target for testing
        target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="password123",
        )

        # Act
        notification = create_notification(
            actor=actor,
            recipient=recipient,
            verb="mentioned you in",
            target=target_user,
        )

        # Assert
        assert notification.target == target_user
        assert notification.target_content_type.model == "user"

    def test_create_bulk_notifications(self, actor):
        """Test creating multiple notifications at once."""
        # Arrange - Create multiple recipients
        recipient1 = User.objects.create_user(
            username="recipient1",
            email="recipient1@example.com",
            password="password123",
        )
        recipient2 = User.objects.create_user(
            username="recipient2",
            email="recipient2@example.com",
            password="password123",
        )
        recipient3 = User.objects.create_user(
            username="recipient3",
            email="recipient3@example.com",
            password="password123",
        )
        recipients = [recipient1, recipient2, recipient3]

        # Act
        notifications = create_bulk_notifications(
            actor=actor,
            recipients=recipients,
            verb="sent you a message",
            message="Hello everyone!",
        )

        # Assert
        assert len(notifications) == 3
        assert Notification.objects.count() == 3
        for notification in notifications:
            assert notification.actor == actor
            assert notification.verb == "sent you a message"
            assert notification.message == "Hello everyone!"
            assert notification.read is False

    def test_create_bulk_notifications_with_target(self, actor):
        """Test creating bulk notifications with a target object."""
        # Arrange
        recipient1 = User.objects.create_user(
            username="recipient1",
            email="recipient1@example.com",
            password="password123",
        )
        recipient2 = User.objects.create_user(
            username="recipient2",
            email="recipient2@example.com",
            password="password123",
        )
        target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="password123",
        )
        recipients = [recipient1, recipient2]

        # Act
        notifications = create_bulk_notifications(
            actor=actor,
            recipients=recipients,
            verb="mentioned you in",
            target=target_user,
        )

        # Assert
        assert len(notifications) == 2
        for notification in notifications:
            assert notification.target == target_user

    def test_notify_user_creates_notification(self, actor, recipient):
        """Test notify_user creates a notification when actor != recipient."""
        # Act
        notification = notify_user(
            actor=actor,
            recipient=recipient,
            verb="followed you",
        )

        # Assert
        assert notification is not None
        assert notification.actor == actor
        assert notification.recipient == recipient
        assert Notification.objects.count() == 1

    def test_notify_user_returns_none_for_self_notification(self, actor):
        """Test notify_user returns None when actor == recipient (self-notification)."""
        # Act
        notification = notify_user(
            actor=actor,
            recipient=actor,  # Same as actor
            verb="commented on your own post",
        )

        # Assert
        assert notification is None
        assert Notification.objects.count() == 0

    def test_notify_user_with_target(self, actor, recipient):
        """Test notify_user with a target object."""
        # Arrange
        target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="password123",
        )

        # Act
        notification = notify_user(
            actor=actor,
            recipient=recipient,
            verb="replied to",
            target=target_user,
            message="Your comment",
        )

        # Assert
        assert notification is not None
        assert notification.target == target_user
        assert notification.message == "Your comment"
