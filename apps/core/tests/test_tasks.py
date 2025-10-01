from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.tasks.sms import send_otp_sms_task


class SMSTaskTestCase(TestCase):
    """Test cases for SMS tasks."""

    @override_settings(SMS_API_URL="http://sms-api.test/send", SMS_SENDER_ID="TestSender")
    @patch("apps.core.tasks.sms.urlrequest.urlopen")
    def test_send_otp_sms_with_valid_http_url(self, mock_urlopen):
        """Test sending OTP SMS with valid HTTP URL scheme."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "success"}'
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        # Call the task directly (not through Celery)
        result = send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        # Assertions
        self.assertTrue(result)
        mock_urlopen.assert_called_once()

    @override_settings(SMS_API_URL="https://sms-api.test/send", SMS_SENDER_ID="TestSender")
    @patch("apps.core.tasks.sms.urlrequest.urlopen")
    def test_send_otp_sms_with_valid_https_url(self, mock_urlopen):
        """Test sending OTP SMS with valid HTTPS URL scheme."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "success"}'
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        # Call the task directly (not through Celery)
        result = send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        # Assertions
        self.assertTrue(result)
        mock_urlopen.assert_called_once()

    @override_settings(SMS_API_URL="file:///etc/passwd", SMS_SENDER_ID="TestSender")
    def test_send_otp_sms_with_invalid_file_url(self):
        """Test sending OTP SMS with invalid file:// URL scheme."""
        # Should raise ValueError for invalid URL scheme
        with self.assertRaises(ValueError) as context:
            send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        self.assertIn("Invalid URL scheme", str(context.exception))
        self.assertIn("file", str(context.exception))

    @override_settings(SMS_API_URL="ftp://sms-api.test/send", SMS_SENDER_ID="TestSender")
    def test_send_otp_sms_with_invalid_ftp_url(self):
        """Test sending OTP SMS with invalid ftp:// URL scheme."""
        # Should raise ValueError for invalid URL scheme
        with self.assertRaises(ValueError) as context:
            send_otp_sms_task.apply(args=["+1234567890", "123456"]).get()

        self.assertIn("Invalid URL scheme", str(context.exception))
        self.assertIn("ftp", str(context.exception))
