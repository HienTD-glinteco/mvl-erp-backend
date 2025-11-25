"""Tests for Firebase Cloud Messaging service."""

from unittest.mock import Mock, patch

import pytest
from firebase_admin import messaging

from apps.core.models import User, UserDevice
from apps.notifications.fcm_service import FCMService, initialize_firebase
from apps.notifications.models import Notification


@pytest.mark.django_db
class TestFCMService:
    """Test cases for FCM service."""

    @pytest.fixture
    def actor(self):
        """Create an actor user."""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        return User.objects.create_superuser(
            username="actor",
            email="actor@example.com",
            password="password123",
            first_name="John",
            last_name="Doe",
        )

    @pytest.fixture
    def recipient(self):
        """Create a recipient user."""
        return User.objects.create_superuser(
            username="recipient",
            email="recipient@example.com",
            password="password123",
        )

    @pytest.fixture
    def recipient_with_device(self, recipient):
        """Create a recipient user with a device."""
        UserDevice.objects.create(
            user=recipient,
            device_id="test-device-123",
            fcm_token="test-fcm-token-xyz",
            platform="android",
            active=True,
        )
        return recipient

    @pytest.fixture
    def notification(self, actor, recipient_with_device):
        """Create a basic notification."""
        return Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="commented on your post",
            message="This is great!",
        )

    @patch("apps.notifications.fcm_service.settings")
    def test_send_notification_when_fcm_disabled(self, mock_settings, notification):
        """Test that send_notification returns False when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.messaging.send")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_notification_success(self, mock_settings, mock_init, mock_send, notification):
        """Test successful notification sending."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send.return_value = "message-id-123"

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is True
        mock_send.assert_called_once()

    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_notification_no_device(self, mock_settings, mock_init, actor, recipient):
        """Test send_notification when recipient has no device."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="mentioned you",
        )

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_notification_inactive_device(self, mock_settings, mock_init, actor, recipient_with_device):
        """Test send_notification when device is inactive."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        # Mark device as inactive
        device = recipient_with_device.device
        device.active = False
        device.save()

        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="mentioned you",
        )

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_notification_no_fcm_token(self, mock_settings, mock_init, actor, recipient):
        """Test send_notification when device has no FCM token."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        UserDevice.objects.create(
            user=recipient,
            device_id="test-device",
            fcm_token="",  # Empty FCM token
            platform="android",
            active=True,
        )

        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="mentioned you",
        )

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is False

    def test_build_payload_default(self, notification):
        """Test building notification payload with default values."""
        # Act
        payload = FCMService._build_payload(notification)

        # Assert
        assert "notification" in payload
        assert "data" in payload
        assert payload["notification"]["title"] == "John Doe"  # last_name first_name format
        assert payload["notification"]["body"] == "commented on your post This is great!"
        assert payload["data"]["notification_id"] == str(notification.id)
        assert payload["data"]["actor_id"] == str(notification.actor.id)
        assert payload["data"]["verb"] == "commented on your post"

    def test_build_payload_custom(self, notification):
        """Test building notification payload with custom values."""
        # Arrange
        custom_title = "Custom Title"
        custom_body = "Custom Body"
        custom_data = {"custom_key": "custom_value"}

        # Act
        payload = FCMService._build_payload(notification, title=custom_title, body=custom_body, data=custom_data)

        # Assert
        assert payload["notification"]["title"] == custom_title
        assert payload["notification"]["body"] == custom_body
        assert payload["data"] == custom_data

    def test_build_payload_with_target(self, actor, recipient_with_device):
        """Test building notification payload with a target object."""
        # Arrange
        target_user = User.objects.create_superuser(
            username="target",
            email="target@example.com",
            password="password123",
        )

        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="mentioned you in",
            target=target_user,
        )

        # Act
        payload = FCMService._build_payload(notification)

        # Assert
        assert "target_type" in payload["data"]
        assert "target_id" in payload["data"]
        assert payload["data"]["target_type"] == "user"
        assert payload["data"]["target_id"] == str(target_user.id)

    def test_build_payload_with_extra_data(self, actor, recipient_with_device):
        """Test building notification payload with extra data."""
        # Arrange
        extra_data = {"post_id": 123, "comment_url": "/posts/123#comment"}

        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="commented",
            extra_data=extra_data,
        )

        # Act
        payload = FCMService._build_payload(notification)

        # Assert
        assert "post_id" in payload["data"]
        assert "comment_url" in payload["data"]
        assert payload["data"]["post_id"] == 123
        assert payload["data"]["comment_url"] == "/posts/123#comment"

    @patch("apps.notifications.fcm_service.messaging.send")
    def test_send_fcm_message_success(self, mock_send):
        """Test successful FCM message sending."""
        # Arrange
        mock_send.return_value = "message-id-123"
        fcm_token = "test-token"
        payload = {
            "notification": {"title": "Test", "body": "Test body"},
            "data": {"key": "value"},
        }

        # Act
        result = FCMService._send_fcm_message(fcm_token, payload)

        # Assert
        assert result is True
        mock_send.assert_called_once()

    @patch("apps.notifications.fcm_service.messaging.send")
    def test_send_fcm_message_unregistered_error(self, mock_send):
        """Test FCM message sending with unregistered token."""
        # Arrange
        mock_send.side_effect = messaging.UnregisteredError("Token unregistered")
        fcm_token = "test-token"
        payload = {
            "notification": {"title": "Test", "body": "Test body"},
            "data": {},
        }

        # Act
        result = FCMService._send_fcm_message(fcm_token, payload)

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.messaging.send")
    def test_send_fcm_message_invalid_argument_error(self, mock_send):
        """Test FCM message sending with invalid argument."""
        # Arrange
        mock_send.side_effect = ValueError("Invalid argument")
        fcm_token = "test-token"
        payload = {
            "notification": {"title": "Test", "body": "Test body"},
            "data": {},
        }

        # Act
        result = FCMService._send_fcm_message(fcm_token, payload)

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.messaging.send")
    def test_send_fcm_message_generic_error(self, mock_send):
        """Test FCM message sending with generic error."""
        # Arrange
        mock_send.side_effect = Exception("Generic error")
        fcm_token = "test-token"
        payload = {
            "notification": {"title": "Test", "body": "Test body"},
            "data": {},
        }

        # Act
        result = FCMService._send_fcm_message(fcm_token, payload)

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.messaging.send")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_to_token_success(self, mock_settings, mock_init, mock_send):
        """Test sending notification directly to token."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send.return_value = "message-id-123"

        # Act
        result = FCMService.send_to_token(
            token="test-token",
            title="Test Title",
            body="Test Body",
            data={"key": "value"},
        )

        # Assert
        assert result is True
        mock_send.assert_called_once()

    @patch("apps.notifications.fcm_service.settings")
    def test_send_to_token_when_fcm_disabled(self, mock_settings):
        """Test send_to_token when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False

        # Act
        result = FCMService.send_to_token(
            token="test-token",
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.firebase_admin.initialize_app")
    @patch("apps.notifications.fcm_service.credentials.Certificate")
    @patch("apps.notifications.fcm_service.settings")
    def test_initialize_firebase_success(self, mock_settings, mock_cert, mock_init):
        """Test successful Firebase initialization."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_settings.FCM_CREDENTIALS = {"type": "service_account"}
        mock_cert.return_value = Mock()

        # Reset the global state
        import apps.notifications.fcm_service as fcm_module

        fcm_module._firebase_initialized = False

        # Act
        result = initialize_firebase()

        # Assert
        assert result is True
        mock_init.assert_called_once()

    @patch("apps.notifications.fcm_service.settings")
    def test_initialize_firebase_when_disabled(self, mock_settings):
        """Test Firebase initialization when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False

        # Reset the global state
        import apps.notifications.fcm_service as fcm_module

        fcm_module._firebase_initialized = False

        # Act
        result = initialize_firebase()

        # Assert
        assert result is False

    @patch("apps.notifications.fcm_service.settings")
    def test_initialize_firebase_no_credentials(self, mock_settings):
        """Test Firebase initialization when credentials are missing."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_settings.FCM_CREDENTIALS = None

        # Reset the global state
        import apps.notifications.fcm_service as fcm_module

        fcm_module._firebase_initialized = False

        # Act
        result = initialize_firebase()

        # Assert
        assert result is False
