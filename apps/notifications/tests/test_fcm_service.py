"""Tests for Firebase Cloud Messaging service."""

from unittest.mock import Mock, patch

import pytest
from firebase_admin import messaging

import apps.notifications.fcm_service as fcm_module
from apps.core.models import User, UserDevice
from apps.notifications.fcm_service import FCMResult, FCMService, initialize_firebase
from apps.notifications.models import Notification


@pytest.mark.django_db(transaction=True)
class TestFCMService:
    """Test cases for FCM service."""

    @pytest.fixture
    def actor(self, transactional_db):
        """Create an actor user."""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        return User.objects.create_superuser(
            username="actor_fcm",  # Unique username to avoid conflicts
            email="actor_fcm@example.com",
            password="password123",
            first_name="John",
            last_name="Doe",
        )

    @pytest.fixture
    def recipient(self, transactional_db):
        """Create a recipient user."""
        return User.objects.create_superuser(
            username="recipient_fcm",  # Unique username
            email="recipient_fcm@example.com",
            password="password123",
        )

    @pytest.fixture
    def recipient_with_device(self, recipient, transactional_db):
        """Create a recipient user with a device."""
        UserDevice.objects.create(
            user=recipient,
            device_id="test-fcm-token-xyz",
            push_token="test-fcm-token-xyz",
            platform=UserDevice.Platform.ANDROID,
            client=UserDevice.Client.MOBILE,
        )
        return recipient

    @pytest.fixture
    def notification(self, actor, recipient_with_device, transactional_db):
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

    @patch("apps.notifications.fcm_service.messaging.send_each_for_multicast")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_notification_success(self, mock_settings, mock_init, mock_send_each_for_multicast, notification):
        """Test successful notification sending."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send_each_for_multicast.return_value = Mock(
            success_count=1,
            failure_count=0,
            responses=[Mock(success=True)],
        )

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is True
        mock_send_each_for_multicast.assert_called_once()

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
        device.state = UserDevice.State.REVOKED
        device.save(update_fields=["state"])

        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="mentioned you",
        )

        # Act
        result = FCMService.send_notification(notification)

        # Assert
        assert result is False

    def test_build_payload_default(self, actor, recipient_with_device):
        """Test building notification payload with default values."""
        # Create notification with specific values for this test
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="commented on your post",
            message="This is great!",
        )

        # Act
        payload = FCMService._build_payload(notification)

        # Assert
        assert "notification" in payload
        assert "data" in payload
        assert payload["notification"]["title"] == "John Doe"  # last_name first_name format
        assert payload["notification"]["body"] == "This is great!"
        assert payload["data"]["notification_id"] == str(notification.id)
        assert payload["data"]["actor_id"] == str(notification.actor.id)
        assert payload["data"]["verb"] == "commented on your post"

    def test_build_payload_custom(self, actor, recipient_with_device):
        """Test building notification payload with custom values."""
        # Create notification for this test
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient_with_device,
            verb="liked your post",
            message="Great content!",
        )

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
            username=f"target_fcm_{actor.id}",  # Unique username
            email=f"target_fcm_{actor.id}@example.com",
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

        fcm_module._firebase_initialized = False

        # Act
        result = initialize_firebase()

        # Assert
        assert result is False


@pytest.mark.django_db(transaction=True)
class TestFCMServiceTopicMessaging:
    """Test cases for FCM topic-based messaging."""

    # =========================================================================
    # send_to_topic tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.send")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_to_topic_success(self, mock_settings, mock_init, mock_send):
        """Test successful topic notification sending."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send.return_value = "message-id-123"

        # Act
        result = FCMService.send_to_topic(
            topic="announcements",
            title="Test Title",
            body="Test Body",
            data={"key": "value"},
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.message_id == "message-id-123"
        assert result.successful_tokens == ["announcements"]
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0][0]
        assert call_args.topic == "announcements"

    @patch("apps.notifications.fcm_service.settings")
    def test_send_to_topic_when_fcm_disabled(self, mock_settings):
        """Test send_to_topic when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False

        # Act
        result = FCMService.send_to_topic(
            topic="announcements",
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.error == "FCM is disabled"

    @patch("apps.notifications.fcm_service.messaging.send")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_to_topic_with_exception(self, mock_settings, mock_init, mock_send):
        """Test send_to_topic handling exceptions."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send.side_effect = Exception("Network error")

        # Act
        result = FCMService.send_to_topic(
            topic="announcements",
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.error == "Network error"
        assert result.failed_tokens == {"announcements": "Network error"}

    # =========================================================================
    # send_to_topics tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.send")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_to_topics_success(self, mock_settings, mock_init, mock_send):
        """Test sending to multiple topics."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send.return_value = "message-id-123"

        # Act
        result = FCMService.send_to_topics(
            topics=["news", "announcements", "alerts"],
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.successful_tokens == ["news", "announcements", "alerts"]
        assert mock_send.call_count == 3

    # =========================================================================
    # subscribe_to_topic tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.subscribe_to_topic")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_subscribe_to_topic_success(self, mock_settings, mock_init, mock_subscribe):
        """Test successful topic subscription."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_response = Mock()
        mock_response.success_count = 3
        mock_response.failure_count = 0
        mock_response.errors = []
        mock_subscribe.return_value = mock_response

        tokens = ["token1", "token2", "token3"]

        # Act
        result = FCMService.subscribe_to_topic(tokens, "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.successful_tokens == tokens
        assert result.failed_tokens == {}
        mock_subscribe.assert_called_once_with(tokens, "news")

    @patch("apps.notifications.fcm_service.messaging.subscribe_to_topic")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_subscribe_to_topic_partial_failure(self, mock_settings, mock_init, mock_subscribe):
        """Test topic subscription with partial failures."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_error = Mock()
        mock_error.index = 2
        mock_error.reason = "INVALID_ARGUMENT"
        mock_response = Mock()
        mock_response.success_count = 2
        mock_response.failure_count = 1
        mock_response.errors = [mock_error]
        mock_subscribe.return_value = mock_response

        tokens = ["token1", "token2", "invalid_token"]

        # Act
        result = FCMService.subscribe_to_topic(tokens, "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.successful_tokens == ["token1", "token2"]
        assert result.failed_tokens == {"invalid_token": "INVALID_ARGUMENT"}

    @patch("apps.notifications.fcm_service.settings")
    def test_subscribe_to_topic_when_fcm_disabled(self, mock_settings):
        """Test subscribe_to_topic when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False
        tokens = ["token1", "token2"]

        # Act
        result = FCMService.subscribe_to_topic(tokens, "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.success_count == 0
        assert result.failure_count == 2
        assert result.failed_tokens == {"token1": "FCM is disabled", "token2": "FCM is disabled"}
        assert result.error == "FCM is disabled"

    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_subscribe_to_topic_empty_tokens(self, mock_settings, mock_init):
        """Test subscribe_to_topic with empty token list."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        # Act
        result = FCMService.subscribe_to_topic([], "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 0
        assert result.failure_count == 0

    # =========================================================================
    # subscribe_to_topics tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.subscribe_to_topic")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_subscribe_to_topics_success(self, mock_settings, mock_init, mock_subscribe):
        """Test subscribing a single token to multiple topics."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_response = Mock()
        mock_response.success_count = 1
        mock_response.failure_count = 0
        mock_response.errors = []
        mock_subscribe.return_value = mock_response

        # Act
        result = FCMService.subscribe_to_topics("token1", ["news", "alerts", "updates"])

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.successful_tokens == ["news", "alerts", "updates"]
        assert mock_subscribe.call_count == 3

    # =========================================================================
    # unsubscribe_from_topic tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.unsubscribe_from_topic")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_unsubscribe_from_topic_success(self, mock_settings, mock_init, mock_unsubscribe):
        """Test successful topic unsubscription."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_response = Mock()
        mock_response.success_count = 2
        mock_response.failure_count = 0
        mock_response.errors = []
        mock_unsubscribe.return_value = mock_response

        tokens = ["token1", "token2"]

        # Act
        result = FCMService.unsubscribe_from_topic(tokens, "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.successful_tokens == tokens
        assert result.failed_tokens == {}
        mock_unsubscribe.assert_called_once_with(tokens, "news")

    @patch("apps.notifications.fcm_service.settings")
    def test_unsubscribe_from_topic_when_fcm_disabled(self, mock_settings):
        """Test unsubscribe_from_topic when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False
        tokens = ["token1", "token2"]

        # Act
        result = FCMService.unsubscribe_from_topic(tokens, "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.success_count == 0
        assert result.failure_count == 2
        assert result.failed_tokens == {"token1": "FCM is disabled", "token2": "FCM is disabled"}
        assert result.error == "FCM is disabled"

    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_unsubscribe_from_topic_empty_tokens(self, mock_settings, mock_init):
        """Test unsubscribe_from_topic with empty token list."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        # Act
        result = FCMService.unsubscribe_from_topic([], "news")

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 0
        assert result.failure_count == 0

    # =========================================================================
    # unsubscribe_from_topics tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.unsubscribe_from_topic")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_unsubscribe_from_topics_success(self, mock_settings, mock_init, mock_unsubscribe):
        """Test unsubscribing a single token from multiple topics."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_response = Mock()
        mock_response.success_count = 1
        mock_response.failure_count = 0
        mock_response.errors = []
        mock_unsubscribe.return_value = mock_response

        # Act
        result = FCMService.unsubscribe_from_topics("token1", ["news", "alerts"])

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.successful_tokens == ["news", "alerts"]
        assert mock_unsubscribe.call_count == 2

    # =========================================================================
    # send_multicast tests
    # =========================================================================

    @patch("apps.notifications.fcm_service.messaging.send_each_for_multicast")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_multicast_success(self, mock_settings, mock_init, mock_send):
        """Test successful multicast sending."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        # Create mock responses for each token
        mock_response1 = Mock()
        mock_response1.success = True
        mock_response2 = Mock()
        mock_response2.success = True
        mock_response3 = Mock()
        mock_response3.success = True

        mock_response = Mock()
        mock_response.success_count = 3
        mock_response.failure_count = 0
        mock_response.responses = [mock_response1, mock_response2, mock_response3]
        mock_send.return_value = mock_response

        tokens = ["token1", "token2", "token3"]

        # Act
        result = FCMService.send_multicast(
            tokens=tokens,
            title="Test Title",
            body="Test Body",
            data={"key": "value"},
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.successful_tokens == tokens
        assert result.failed_tokens == {}
        mock_send.assert_called_once()

    @patch("apps.notifications.fcm_service.messaging.send_each_for_multicast")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_multicast_partial_failure(self, mock_settings, mock_init, mock_send):
        """Test multicast with partial failures."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        success_response = Mock()
        success_response.success = True
        failure_response = Mock()
        failure_response.success = False
        failure_response.exception = "Invalid token"

        mock_response = Mock()
        mock_response.success_count = 2
        mock_response.failure_count = 1
        mock_response.responses = [success_response, success_response, failure_response]
        mock_send.return_value = mock_response

        tokens = ["token1", "token2", "invalid_token"]

        # Act
        result = FCMService.send_multicast(
            tokens=tokens,
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.successful_tokens == ["token1", "token2"]
        assert result.failed_tokens == {"invalid_token": "Invalid token"}

    @patch("apps.notifications.fcm_service.settings")
    def test_send_multicast_when_fcm_disabled(self, mock_settings):
        """Test send_multicast when FCM is disabled."""
        # Arrange
        mock_settings.FCM_ENABLED = False
        tokens = ["token1", "token2"]

        # Act
        result = FCMService.send_multicast(
            tokens=tokens,
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.success_count == 0
        assert result.failure_count == 2
        assert result.failed_tokens == {"token1": "FCM is disabled", "token2": "FCM is disabled"}
        assert result.error == "FCM is disabled"

    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_multicast_empty_tokens(self, mock_settings, mock_init):
        """Test send_multicast with empty token list."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True

        # Act
        result = FCMService.send_multicast(
            tokens=[],
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is True
        assert result.success_count == 0
        assert result.failure_count == 0

    @patch("apps.notifications.fcm_service.messaging.send_each_for_multicast")
    @patch("apps.notifications.fcm_service.initialize_firebase")
    @patch("apps.notifications.fcm_service.settings")
    def test_send_multicast_with_exception(self, mock_settings, mock_init, mock_send):
        """Test send_multicast handling exceptions."""
        # Arrange
        mock_settings.FCM_ENABLED = True
        mock_init.return_value = True
        mock_send.side_effect = Exception("Network error")

        tokens = ["token1", "token2"]

        # Act
        result = FCMService.send_multicast(
            tokens=tokens,
            title="Test Title",
            body="Test Body",
        )

        # Assert
        assert isinstance(result, FCMResult)
        assert result.success is False
        assert result.success_count == 0
        assert result.failure_count == 2
        assert result.failed_tokens == {"token1": "Network error", "token2": "Network error"}
        assert result.error == "Network error"
