from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit_logging import LogAction
from apps.core.models import User


class AuthAuditLoggingTestCase(TestCase):
    """Test cases for audit logging in authentication flows"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser001",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )
        self.otp_url = reverse("core:verify_otp")
        self.password_change_url = reverse("core:change_password")
        self.forgot_password_url = reverse("core:forgot_password")

    @patch("apps.notifications.utils.trigger_send_notification")
    @patch("apps.core.api.views.auth.otp_verification.log_audit_event")
    def test_login_audit_log(self, mock_log_audit_event, mock_trigger_send_notification):
        """Test that successful login creates an audit log"""
        # Generate OTP for the user
        otp_code = self.user.generate_otp()

        data = {"username": "testuser001", "otp_code": otp_code}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created
        mock_log_audit_event.assert_called_once()
        call_kwargs = mock_log_audit_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.LOGIN)
        self.assertEqual(call_kwargs["user"], self.user)
        self.assertIn("logged in successfully", call_kwargs["change_message"])

    @patch("apps.core.api.views.auth.password_change.log_audit_event")
    def test_password_change_audit_log(self, mock_log_audit_event):
        """Test that password change creates an audit log"""
        # Authenticate the user
        self.client.force_authenticate(user=self.user)

        data = {
            "old_password": "testpass123",
            "new_password": "Newpass456!",
            "confirm_password": "Newpass456!",
        }
        response = self.client.post(self.password_change_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created
        mock_log_audit_event.assert_called_once()
        call_kwargs = mock_log_audit_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.PASSWORD_CHANGE)
        self.assertEqual(call_kwargs["user"], self.user)
        self.assertIn("changed their password", call_kwargs["change_message"])

    @patch("apps.core.api.views.auth.password_reset.log_audit_event")
    @patch("apps.core.tasks.send_password_reset_email_task.delay")
    def test_password_reset_request_audit_log(self, mock_email_task, mock_log_audit_event):
        """Test that password reset request creates an audit log"""
        mock_email_task.return_value = MagicMock()

        data = {"identifier": "test@example.com"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created
        mock_log_audit_event.assert_called_once()
        call_kwargs = mock_log_audit_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.PASSWORD_RESET)
        self.assertEqual(call_kwargs["user"], self.user)
        self.assertIn("requested password reset", call_kwargs["change_message"])
        self.assertEqual(call_kwargs["reset_channel"], "email")

    @patch("apps.core.api.views.auth.password_reset.log_audit_event")
    @patch("apps.core.tasks.sms.send_otp_sms_task.delay")
    def test_password_reset_request_sms_audit_log(self, mock_sms_task, mock_log_audit_event):
        """Test that password reset request via SMS creates an audit log"""
        mock_sms_task.return_value = MagicMock()

        # Add phone number to user
        self.user.phone_number = "0123456789"
        self.user.save()

        data = {"identifier": "0123456789"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created
        mock_log_audit_event.assert_called_once()
        call_kwargs = mock_log_audit_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.PASSWORD_RESET)
        self.assertEqual(call_kwargs["user"], self.user)
        self.assertIn("requested password reset", call_kwargs["change_message"])
        self.assertEqual(call_kwargs["reset_channel"], "sms")
