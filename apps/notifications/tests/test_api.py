import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import User
from apps.notifications.models import Notification


@pytest.mark.django_db
class TestNotificationAPI:
    """Test cases for Notification API endpoints."""

    @pytest.fixture
    def api_client(self):
        """Create an API client."""
        return APIClient()

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123",
        )

    @pytest.fixture
    def other_user(self):
        """Create another test user."""
        return User.objects.create_user(
            username="otheruser",
            email="otheruser@example.com",
            password="password123",
        )

    @pytest.fixture
    def authenticated_client(self, api_client, user):
        """Create an authenticated API client."""
        api_client.force_authenticate(user=user)
        return api_client

    def test_list_notifications(self, authenticated_client, user, other_user):
        """Test listing notifications for authenticated user."""
        # Arrange - Create notifications
        notification1 = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="commented on your post",
        )
        notification2 = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="liked your post",
        )
        # Create a notification for another user (should not appear)
        Notification.objects.create(
            actor=user,
            recipient=other_user,
            verb="replied to your comment",
        )

        # Act
        url = reverse("notifications:notification-list")
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2

        # Should be ordered newest first
        notifications = data["data"]["results"]
        assert notifications[0]["id"] == notification2.id
        assert notifications[1]["id"] == notification1.id

    def test_list_notifications_requires_authentication(self, api_client):
        """Test that listing notifications requires authentication."""
        # Act
        url = reverse("notifications:notification-list")
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_notification(self, authenticated_client, user, other_user):
        """Test retrieving a specific notification."""
        # Arrange
        notification = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="mentioned you",
            message="Check out this great post!",
        )

        # Act
        url = reverse("notifications:notification-detail", kwargs={"pk": notification.id})
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == notification.id
        assert data["data"]["verb"] == "mentioned you"
        assert data["data"]["message"] == "Check out this great post!"
        assert data["data"]["actor"]["username"] == other_user.username

    def test_retrieve_notification_not_found(self, authenticated_client):
        """Test retrieving a non-existent notification returns 404."""
        # Act
        url = reverse("notifications:notification-detail", kwargs={"pk": "00000000-0000-0000-0000-000000000000"})
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_mark_notification_as_read(self, authenticated_client, user, other_user):
        """Test marking a single notification as read."""
        # Arrange
        notification = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="assigned you a task",
            read=False,
        )

        # Act
        url = reverse("notifications:notification-mark-as-read", kwargs={"pk": notification.id})
        response = authenticated_client.patch(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.read is True

    def test_mark_notification_as_unread(self, authenticated_client, user, other_user):
        """Test marking a single notification as unread."""
        # Arrange
        notification = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="completed your task",
            read=True,
        )

        # Act
        url = reverse("notifications:notification-mark-as-unread", kwargs={"pk": notification.id})
        response = authenticated_client.patch(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.read is False

    def test_bulk_mark_as_read(self, authenticated_client, user, other_user):
        """Test bulk marking multiple notifications as read."""
        # Arrange
        notification1 = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="liked your post",
            read=False,
        )
        notification2 = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="shared your post",
            read=False,
        )
        notification3 = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="followed you",
            read=False,
        )

        # Act
        url = reverse("notifications:notification-bulk-mark-as-read")
        payload = {"notification_ids": [notification1.id, notification2.id]}
        response = authenticated_client.post(url, payload, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        notification1.refresh_from_db()
        notification2.refresh_from_db()
        notification3.refresh_from_db()
        assert notification1.read is True
        assert notification2.read is True
        assert notification3.read is False  # Not included in the list

    def test_bulk_mark_as_read_empty_list(self, authenticated_client):
        """Test bulk marking with empty list returns validation error."""
        # Act
        url = reverse("notifications:notification-bulk-mark-as-read")
        data = {"notification_ids": []}
        response = authenticated_client.post(url, data, format="json")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_mark_as_read_only_own_notifications(self, authenticated_client, user, other_user):
        """Test that bulk marking only affects user's own notifications."""
        # Arrange
        user_notification = Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="mentioned you",
            read=False,
        )
        other_notification = Notification.objects.create(
            actor=user,
            recipient=other_user,
            verb="replied to you",
            read=False,
        )

        # Act - Try to mark both notifications
        url = reverse("notifications:notification-bulk-mark-as-read")
        payload = {"notification_ids": [user_notification.id, other_notification.id]}
        response = authenticated_client.post(url, payload, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1  # Only 1 notification marked
        user_notification.refresh_from_db()
        other_notification.refresh_from_db()
        assert user_notification.read is True
        assert other_notification.read is False  # Not the user's notification

    def test_mark_all_as_read(self, authenticated_client, user, other_user):
        """Test marking all notifications as read."""
        # Arrange - Create multiple unread notifications
        Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="liked your post",
            read=False,
        )
        Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="commented on your post",
            read=False,
        )
        Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="shared your post",
            read=True,  # Already read
        )
        # Create a notification for another user
        Notification.objects.create(
            actor=user,
            recipient=other_user,
            verb="followed you",
            read=False,
        )

        # Act
        url = reverse("notifications:notification-mark-all-as-read")
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2  # Only 2 unread notifications were marked
        unread_count = Notification.objects.filter(recipient=user, read=False).count()
        assert unread_count == 0

    def test_unread_count(self, authenticated_client, user, other_user):
        """Test getting unread notification count."""
        # Arrange
        Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="liked your post",
            read=False,
        )
        Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="commented on your post",
            read=False,
        )
        Notification.objects.create(
            actor=other_user,
            recipient=user,
            verb="shared your post",
            read=True,
        )

        # Act
        url = reverse("notifications:notification-unread-count")
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
