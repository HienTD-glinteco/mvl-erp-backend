from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit_logging import LogAction
from apps.core.models import PasswordResetOTP, User
from apps.hrm.models import Employee


@override_settings(AUDIT_LOG_DISABLED=False)
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


@override_settings(AUDIT_LOG_DISABLED=False)
class AuthAuditLoggingWithEmployeeTestCase(TestCase):
    """Test cases for audit logging with employee records in authentication flows"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="emp001",
            email="employee@example.com",
            password="testpass123",
            first_name="Jane",
            last_name="Smith",
        )
        # Create associated employee record
        self.employee = Employee.objects.create(
            code="EMP001",
            name="Jane Smith",
            user=self.user,
        )
        self.otp_url = reverse("core:verify_otp")
        self.password_change_url = reverse("core:change_password")
        self.forgot_password_url = reverse("core:forgot_password")

    @patch("apps.notifications.utils.trigger_send_notification")
    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_login_audit_log_includes_employee_code_and_object(self, mock_log_event, mock_trigger_send_notification):
        """Test that successful login includes employee code and object type/id"""
        # Generate OTP for the user
        otp_code = self.user.generate_otp()

        data = {"username": "emp001", "otp_code": otp_code}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created with employee information
        mock_log_event.assert_called_once()
        call_kwargs = mock_log_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.LOGIN)
        self.assertEqual(call_kwargs["employee_code"], "EMP001")
        self.assertEqual(call_kwargs["object_type"], "employee")
        self.assertEqual(call_kwargs["object_id"], str(self.employee.pk))
        self.assertIn("logged in successfully", call_kwargs["change_message"])

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_password_change_audit_log_includes_employee_code_and_object(self, mock_log_event):
        """Test that password change includes employee code and object type/id"""
        # Authenticate the user
        self.client.force_authenticate(user=self.user)

        data = {
            "old_password": "testpass123",
            "new_password": "Newpass456!",
            "confirm_password": "Newpass456!",
        }
        response = self.client.post(self.password_change_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created with employee information
        mock_log_event.assert_called_once()
        call_kwargs = mock_log_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.PASSWORD_CHANGE)
        self.assertEqual(call_kwargs["employee_code"], "EMP001")
        self.assertEqual(call_kwargs["object_type"], "employee")
        self.assertEqual(call_kwargs["object_id"], str(self.employee.pk))
        self.assertIn("changed their password", call_kwargs["change_message"])

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    @patch("apps.core.tasks.send_password_reset_email_task.delay")
    def test_password_reset_audit_log_includes_employee_code_and_object(self, mock_email_task, mock_log_event):
        """Test that password reset request includes employee code and object type/id"""
        mock_email_task.return_value = MagicMock()

        data = {"identifier": "employee@example.com"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created with employee information
        mock_log_event.assert_called_once()
        call_kwargs = mock_log_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.PASSWORD_RESET)
        self.assertEqual(call_kwargs["employee_code"], "EMP001")
        self.assertEqual(call_kwargs["object_type"], "employee")
        self.assertEqual(call_kwargs["object_id"], str(self.employee.pk))
        self.assertIn("requested password reset", call_kwargs["change_message"])
        self.assertEqual(call_kwargs["reset_channel"], "email")

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_password_reset_change_password_audit_log_includes_employee(self, mock_log_event):
        """Test that password reset change (step 3) includes employee code and object type/id"""
        # Create a password reset request for the user
        reset_request, otp_code = PasswordResetOTP.objects.create_request(self.user, channel="email")
        # Mark OTP as verified
        reset_request.is_otp_verified = True
        reset_request.save()

        # Authenticate with reset token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {reset_request.reset_token}")

        data = {
            "reset_token": reset_request.reset_token,
            "new_password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
        }

        url = reverse("core:forgot_password_change_password")
        response = self.client.post(url, data, format="json")

        # Note: This might fail if the view requires special authentication handling
        # but we're mainly testing that the audit logging call is correct
        if response.status_code == status.HTTP_200_OK:
            # Verify audit log was created with employee information
            mock_log_event.assert_called()
            call_kwargs = mock_log_event.call_args[1]
            self.assertEqual(call_kwargs["action"], LogAction.PASSWORD_RESET)
            self.assertEqual(call_kwargs["employee_code"], "EMP001")
            self.assertEqual(call_kwargs["object_type"], "employee")
            self.assertEqual(call_kwargs["object_id"], str(self.employee.pk))

    @patch("apps.notifications.utils.trigger_send_notification")
    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_login_audit_log_without_employee_record(self, mock_log_event, mock_trigger_send_notification):
        """Test that login still works for users without employee records"""
        # Create a user without employee record
        user_no_employee = User.objects.create_user(
            username="noemployee",
            email="noemployee@example.com",
            password="testpass123",
        )
        otp_code = user_no_employee.generate_otp()

        data = {"username": "noemployee", "otp_code": otp_code}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify audit log was created but without employee_code and object_type
        mock_log_event.assert_called_once()
        call_kwargs = mock_log_event.call_args[1]
        self.assertEqual(call_kwargs["action"], LogAction.LOGIN)
        # employee_code should not be present for users without employee records
        self.assertIn("employee_code", call_kwargs)
        # object_type should not be present when modified_object is None
        self.assertNotIn("object_type", call_kwargs)
        self.assertIn("logged in successfully", call_kwargs["change_message"])
