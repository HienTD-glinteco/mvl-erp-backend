from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.tasks.sms import send_otp_sms_task


class SMSTaskTestCase(TestCase):
    """Test cases for SMS tasks."""

    @override_settings(SMS_API_URL="http://sms-api.test/send", SMS_SENDER_ID="TestSender")
    @patch("apps.core.tasks.sms.requests.post")
    def test_send_otp_sms_with_valid_http_url(self, mock_post):
        """Test sending OTP SMS with valid HTTP URL scheme."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response

        # Call the task directly (not through Celery)
        result = send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        # Assertions
        self.assertTrue(result)
        mock_post.assert_called_once()

    @override_settings(SMS_API_URL="https://sms-api.test/send", SMS_SENDER_ID="TestSender")
    @patch("apps.core.tasks.sms.requests.post")
    def test_send_otp_sms_with_valid_https_url(self, mock_post):
        """Test sending OTP SMS with valid HTTPS URL scheme."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response

        # Call the task directly (not through Celery)
        result = send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        # Assertions
        self.assertTrue(result)
        mock_post.assert_called_once()

    @override_settings(SMS_API_URL="http://sms-api.test/send", SMS_SENDER_ID="TestSender")
    @patch("apps.core.tasks.sms.requests.post")
    def test_send_otp_sms_with_error_status(self, mock_post):
        """Test sending OTP SMS with error status code."""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"error": "Internal server error"}'
        mock_post.return_value = mock_response

        # Should raise an exception for non-2xx status
        # Note: Celery will retry the task (max_retries=3), so we expect 4 calls
        with self.assertRaises(Exception) as context:
            send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        self.assertIn("SMS provider error", str(context.exception))
        # Task retries 3 times after initial attempt
        self.assertEqual(mock_post.call_count, 4)

    @override_settings(SMS_API_URL="http://sms-api.test/send", SMS_SENDER_ID="TestSender")
    @patch("apps.core.tasks.sms.requests.post")
    def test_send_otp_sms_with_network_error(self, mock_post):
        """Test sending OTP SMS with network error."""
        # Mock network error
        import requests

        mock_post.side_effect = requests.ConnectionError("Connection refused")

        # Should raise an exception for network error
        # Note: Celery will retry the task (max_retries=3), so we expect 4 calls
        with self.assertRaises(Exception):
            send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        # Task retries 3 times after initial attempt
        self.assertEqual(mock_post.call_count, 4)
