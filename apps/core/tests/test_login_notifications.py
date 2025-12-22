"""Test cases for login notification feature."""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import User
from apps.notifications.models import Notification
from libs.request_utils import UNKNOWN_IP


class LoginNotificationTestCase(TestCase):
    """Test cases for notifications created during login."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )
        self.login_url = reverse("core:login")

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_login_creates_notification(self, mock_trigger_send_notification):
        """Test that successful login creates a notification for the user."""
        # Arrange - Generate OTP for the user

        # Act - Complete login with OTP verification
        data = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        # Assert - Check response and notification
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.first()
        self.assertEqual(notification.actor, self.user)
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.verb, "logged in")
        self.assertIn("IP address", notification.message)
        self.assertFalse(notification.read)

    @patch("apps.notifications.utils.trigger_send_notification")
    def test_login_notification_includes_ip_address(self, mock_trigger_send_notification):
        """Test that login notification includes the IP address in extra_data."""
        # Arrange - Generate OTP and set up request with IP

        # Act - Complete login with a specific IP address
        data = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(
            self.login_url,
            data,
            format="json",
            REMOTE_ADDR="192.168.1.100",
        )

        # Assert - Check notification has IP address
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.first()
        self.assertIn("ip_address", notification.extra_data)
        self.assertEqual(notification.extra_data["ip_address"], "192.168.1.100")
        # Check that message includes IP address
        self.assertIn("192.168.1.100", notification.message)

    @patch("apps.notifications.utils.trigger_send_notification")
    def test_login_notification_with_x_forwarded_for_header(self, mock_trigger_send_notification):
        """Test that login notification uses X-Forwarded-For header when present."""
        # Arrange - Generate OTP

        # Act - Complete login with X-Forwarded-For header
        data = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(
            self.login_url,
            data,
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.42, 198.51.100.1",
        )

        # Assert - Check notification uses the first IP from X-Forwarded-For
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.first()
        self.assertEqual(notification.extra_data["ip_address"], "203.0.113.42")

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_login_notification_delivery_method(self, mock_trigger_send_notification):
        """Test that login notification uses firebase delivery method."""
        # Arrange

        # Act
        data = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.first()
        self.assertEqual(notification.delivery_method, Notification.DeliveryMethod.FIREBASE)

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_login_notification_includes_user_agent(self, mock_trigger_send_notification):
        """Test that login notification includes user agent in extra_data."""
        # Arrange
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

        # Act
        data = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(
            self.login_url,
            data,
            format="json",
            HTTP_USER_AGENT=user_agent,
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.first()
        self.assertIn("user_agent", notification.extra_data)
        self.assertEqual(notification.extra_data["user_agent"], user_agent)

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_multiple_logins_create_multiple_notifications(self, mock_trigger_send_notification):
        """Test that multiple logins create separate notifications."""
        # Arrange & Act - First login
        data_1 = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response_1 = self.client.post(self.login_url, data_1, format="json")

        # Arrange & Act - Second login
        data_2 = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
        response_2 = self.client.post(
            self.login_url,
            data_2,
            format="json",
            REMOTE_ADDR="10.0.0.5",
        )

        # Assert - Check both logins succeeded and created notifications
        self.assertEqual(response_1.status_code, status.HTTP_200_OK)
        self.assertEqual(response_2.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.count(), 2)

        # Verify each notification has correct data
        notifications = Notification.objects.order_by("created_at")
        self.assertEqual(notifications[0].recipient, self.user)
        self.assertEqual(notifications[1].recipient, self.user)
        self.assertEqual(notifications[1].extra_data["ip_address"], "10.0.0.5")

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_login_notification_without_ip_address(self, mock_trigger_send_notification):
        """Test that notification is created even when IP address is not available."""
        # Arrange

        # Act - Mock get_client_ip to return None at the view level
        with patch("apps.core.api.views.auth.login.get_client_ip") as mock_get_ip:
            mock_get_ip.return_value = None
            data = {"username": "testuser", "password": "testpass123", "device_id": "web-device-1"}
            response = self.client.post(self.login_url, data, format="json")

        # Assert - Notification is still created with "Unknown" IP
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.extra_data["ip_address"], UNKNOWN_IP)

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_failed_login_does_not_create_notification(self):
        """Test that failed login attempts do not create notifications."""
        # Act - Try to login with invalid password
        data = {"username": "testuser", "password": "wrongpassword", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        # Assert - Login failed and no notification was created
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Notification.objects.count(), 0)
