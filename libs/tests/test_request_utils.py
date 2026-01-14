"""Test cases for request utility functions."""

from django.http import HttpRequest
from django.test import TestCase

from libs.request_utils import get_client_ip, get_user_agent


class GetClientIPTestCase(TestCase):
    """Test cases for the get_client_ip utility function."""

    def test_get_client_ip_from_remote_addr(self):
        """Test extracting IP address from REMOTE_ADDR."""
        # Arrange
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Act
        ip_address = get_client_ip(request)

        # Assert
        self.assertEqual(ip_address, "192.168.1.1")

    def test_get_client_ip_from_x_forwarded_for_single_ip(self):
        """Test extracting IP address from X-Forwarded-For with single IP."""
        # Arrange
        request = HttpRequest()
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.42"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Act
        ip_address = get_client_ip(request)

        # Assert - Should prefer X-Forwarded-For over REMOTE_ADDR
        self.assertEqual(ip_address, "203.0.113.42")

    def test_get_client_ip_from_x_forwarded_for_multiple_ips(self):
        """Test extracting IP address from X-Forwarded-For with multiple IPs."""
        # Arrange
        request = HttpRequest()
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.42, 198.51.100.1, 192.168.1.1"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Act
        ip_address = get_client_ip(request)

        # Assert - Should return the first IP from the chain
        self.assertEqual(ip_address, "203.0.113.42")

    def test_get_client_ip_with_spaces_in_header(self):
        """Test extracting IP address when X-Forwarded-For has extra spaces."""
        # Arrange
        request = HttpRequest()
        request.META["HTTP_X_FORWARDED_FOR"] = "  203.0.113.42  ,  198.51.100.1  "

        # Act
        ip_address = get_client_ip(request)

        # Assert - Should strip whitespace
        self.assertEqual(ip_address, "203.0.113.42")

    def test_get_client_ip_no_ip_available(self):
        """Test behavior when no IP information is available."""
        # Arrange
        request = HttpRequest()
        # Don't set any IP-related headers

        # Act
        ip_address = get_client_ip(request)

        # Assert - Should return None
        self.assertIsNone(ip_address)

    def test_get_client_ip_prefers_x_forwarded_for(self):
        """Test that X-Forwarded-For takes precedence over REMOTE_ADDR."""
        # Arrange
        request = HttpRequest()
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.42"
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        # Act
        ip_address = get_client_ip(request)

        # Assert
        self.assertEqual(ip_address, "203.0.113.42")
        self.assertNotEqual(ip_address, "10.0.0.1")


class GetUserAgentTestCase(TestCase):
    """Test cases for the get_user_agent utility function."""

    def test_get_user_agent_from_request(self):
        """Test extracting user agent from HTTP_USER_AGENT."""
        # Arrange
        request = HttpRequest()
        request.META["HTTP_USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

        # Act
        user_agent = get_user_agent(request)

        # Assert
        self.assertEqual(user_agent, "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

    def test_get_user_agent_empty_when_not_available(self):
        """Test that get_user_agent returns empty string when not available."""
        # Arrange
        request = HttpRequest()
        # Don't set HTTP_USER_AGENT

        # Act
        user_agent = get_user_agent(request)

        # Assert
        self.assertEqual(user_agent, "")
