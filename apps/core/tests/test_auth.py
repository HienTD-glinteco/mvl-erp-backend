from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.constants import APP_TESTER_OTP_CODE, APP_TESTER_USERNAME
from apps.core.models import PasswordResetOTP, User, UserDevice


class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser001",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )
        self.login_url = reverse("core:login")
        self.otp_url = reverse("core:verify_otp")
        self.forgot_password_url = reverse("core:forgot_password")

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.core.tasks.send_otp_email_task.delay")
    def test_successful_login(self, mock_email_task):
        """Test successful login with correct credentials"""
        mock_email_task.return_value = MagicMock()

        data = {"username": "testuser001", "password": "testpass123"}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("message", response_data["data"])
        self.assertIn("OTP code has been sent", response_data["data"]["message"])
        self.assertEqual(response_data["data"]["username"], "testuser001")
        self.assertIn("email_hint", response_data["data"])
        # Verify OTP email task was called
        mock_email_task.assert_called_once()

    def test_login_with_wrong_credentials(self):
        """Test login with wrong credentials"""
        data = {"username": "testuser001", "password": "wrongpassword"}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("non_field_errors", response_data["error"])
        self.assertIn("Incorrect password", str(response_data["error"]["non_field_errors"][0]))

    def test_login_with_nonexistent_user(self):
        """Test login with non-existent username"""
        data = {"username": "NONEXISTENT", "password": "testpass123"}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("non_field_errors", response_data["error"])
        self.assertIn(
            "Username does not exist",
            str(response_data["error"]["non_field_errors"][0]),
        )

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_account_lockout_after_failed_attempts(self):
        """Test account lockout after 5 failed login attempts"""
        data = {"username": "testuser001", "password": "wrongpassword"}

        # Make 5 failed attempts
        for i in range(5):
            response = self.client.post(self.login_url, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 6th attempt should show account locked message
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("locked", str(response_data["error"]["non_field_errors"][0]))

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_otp_verification_success(self, mock_trigger_send_notification):
        """Test successful OTP verification"""
        # First generate OTP for the user
        otp_code = self.user.generate_otp()

        data = {"username": "testuser001", "otp_code": otp_code}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("message", response_data["data"])
        self.assertIn("tokens", response_data["data"])
        self.assertIn("user", response_data["data"])
        self.assertIn("access", response_data["data"]["tokens"])
        self.assertIn("refresh", response_data["data"]["tokens"])

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    def test_otp_verification_wrong_code(self):
        """Test OTP verification with wrong code"""
        # First generate OTP for the user
        self.user.generate_otp()

        data = {
            "username": "testuser001",
            "otp_code": "000000",  # Wrong OTP
        }
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        # Check for the actual error structure - it could be either format
        error_data = response_data["error"]
        self.assertTrue(
            "non_field_errors" in error_data
            or ("errors" in error_data and any(err.get("attr") == "non_field_errors" for err in error_data["errors"]))
        )

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    @patch("apps.core.tasks.send_password_reset_email_task.delay")
    def test_password_reset_request_email(self, mock_email_task):
        """Test password reset request with email"""
        mock_email_task.return_value = MagicMock()

        data = {"identifier": "test@example.com"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("message", response_data["data"])
        self.assertIn("Password reset", response_data["data"]["message"])

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    @patch("apps.core.tasks.sms.send_otp_sms_task.delay")
    def test_password_reset_request_phone(self, mock_sms_task):
        """Test password reset request with phone number uses SMS"""
        mock_sms_task.return_value = MagicMock()

        # Add phone number to user
        self.user.phone_number = "0123456789"
        self.user.save()

        data = {"identifier": "0123456789"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("message", response_data["data"])
        # Message should indicate SMS was used
        self.assertIn("via SMS", response_data["data"]["message"])  # contains SMS
        # Should include phone hint, not email hint
        self.assertIn("phone_hint", response_data["data"])  # masked phone
        self.assertNotIn("email_hint", response_data["data"])  # no email hint in SMS path
        # Verify SMS task was called
        mock_sms_task.assert_called_once()

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    def test_password_reset_wrong_identifier(self):
        """Test password reset with wrong identifier"""
        data = {"identifier": "wrong@example.com"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("non_field_errors", response_data["error"])

    def test_user_model_methods(self):
        """Test User model methods"""
        # Test account locking
        self.assertFalse(self.user.is_locked)
        self.user.lock_account()
        self.assertTrue(self.user.is_locked)

        # Test account unlocking
        self.user.unlock_account()
        self.assertFalse(self.user.is_locked)
        self.assertEqual(self.user.failed_login_attempts, 0)

        # Test OTP generation
        otp = self.user.generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())
        self.assertIsNotNone(self.user.otp_expires_at)

        # Test OTP verification
        self.assertTrue(self.user.verify_otp(otp))
        self.assertFalse(self.user.verify_otp("000000"))

        # Test full name
        self.assertEqual(self.user.get_full_name(), "John Doe")
        self.assertEqual(self.user.get_short_name(), "John")

    def test_mobile_app_tester_login_otp_is_constant(self):
        tester = User.objects.create_superuser(
            username=APP_TESTER_USERNAME,
            email="mobile.tester@example.com",
            password="testpass123",
            first_name="Mobile",
            last_name="Tester",
        )

        otp = tester.generate_otp()

        self.assertEqual(otp, APP_TESTER_OTP_CODE)
        self.assertEqual(tester.otp_code, APP_TESTER_OTP_CODE)

    def test_mobile_app_tester_password_reset_otp_is_constant(self):
        tester = User.objects.create_superuser(
            username=APP_TESTER_USERNAME,
            email="mobile.tester.reset@example.com",
            password="testpass123",
            first_name="Mobile",
            last_name="Tester",
        )

        reset_request, otp = PasswordResetOTP.objects.create_request(tester, channel="email")

        self.assertEqual(otp, APP_TESTER_OTP_CODE)
        self.assertEqual(len(otp), 6)
        self.assertTrue(reset_request.otp_hash)

    def test_inactive_user_login(self):
        """Test login attempt with inactive user"""
        self.user.is_active = False
        self.user.save()

        data = {"username": "testuser001", "password": "testpass123"}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("non_field_errors", response_data["error"])
        self.assertIn("deactivated", str(response_data["error"]["non_field_errors"][0]))

    def test_empty_credentials(self):
        """Test login with empty credentials"""
        data = {"username": "", "password": ""}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        # Should have validation errors for both fields
        self.assertTrue("username" in response_data["error"] or "non_field_errors" in response_data["error"])

    def test_otp_expiration(self):
        """Test OTP verification with expired code"""
        # Generate OTP and manually expire it
        otp_code = self.user.generate_otp()
        self.user.otp_expires_at = timezone.now() - timezone.timedelta(minutes=10)
        self.user.save()

        data = {"username": "testuser001", "otp_code": otp_code}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        # Check for the actual error structure - it could be either format
        error_data = response_data["error"]
        self.assertTrue(
            "non_field_errors" in error_data
            or ("errors" in error_data and any(err.get("attr") == "non_field_errors" for err in error_data["errors"]))
        )

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    @patch("apps.core.tasks.send_password_reset_email_task.delay")
    def test_password_reset_step1_returns_reset_token(self, mock_email_task):
        mock_email_task.return_value = MagicMock()

        data = {"identifier": self.user.email}
        url = reverse("core:forgot_password")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        envelope = response.json()
        self.assertTrue(envelope["success"])  # wrapped by middleware
        data = envelope["data"]
        self.assertIn("message", data)
        self.assertIn("reset_token", data)
        self.assertIn("expires_at", data)
        self.assertIn("email_hint", data)
        # reset_token should correspond to a DB record
        reset_request = PasswordResetOTP.objects.get_by_token(data["reset_token"])
        self.assertIsNotNone(reset_request)

    @patch(
        "apps.core.api.views.auth.password_reset_otp_verification.PasswordResetOTPVerificationView.throttle_classes",
        new=[],
    )
    def test_password_reset_step2_verify_otp_returns_jwt(self):
        # Create a fresh reset request to get the plain OTP code
        reset_request, otp_code = PasswordResetOTP.objects.create_request(self.user, channel="email")
        url = reverse("core:forgot_password_verify_otp")
        payload = {"reset_token": reset_request.reset_token, "otp_code": otp_code}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        envelope = response.json()
        self.assertTrue(envelope["success"])  # wrapped by middleware
        data = envelope["data"]
        self.assertIn("message", data)
        self.assertIn("tokens", data)
        self.assertIn("access", data["tokens"])  # access token provided
        self.assertIn("refresh", data["tokens"])  # refresh token provided

    @patch(
        "apps.core.api.views.auth.password_reset_otp_verification.PasswordResetOTPVerificationView.throttle_classes",
        new=[],
    )
    def test_password_reset_step3_change_password_authenticated(self):
        # Step 2: verify OTP to get JWT first
        reset_request, otp_code = PasswordResetOTP.objects.create_request(self.user, channel="email")

        url_verify = reverse("core:forgot_password_verify_otp")
        resp2 = self.client.post(
            url_verify,
            {"reset_token": reset_request.reset_token, "otp_code": otp_code},
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        tokens = resp2.json()["data"]["tokens"]
        access = tokens["access"]

        # Step 3: change password using authenticated request
        new_password = "NewSecure123!"
        url_change = reverse("core:forgot_password_change_password")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp3 = client.post(
            url_change,
            {"new_password": new_password, "confirm_password": new_password},
            format="json",
        )

        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        # Ensure reset request is cleaned up
        self.assertFalse(PasswordResetOTP.objects.filter(user=self.user, is_verified=True, is_used=False).exists())

    @patch(
        "apps.core.api.views.auth.password_reset_change_password.PasswordResetChangePasswordView.throttle_classes",
        new=[],
    )
    def test_password_reset_step3_requires_authentication(self):
        new_password = "NewSecure123!"
        url_change = reverse("core:forgot_password_change_password")
        resp = self.client.post(
            url_change,
            {"new_password": new_password, "confirm_password": new_password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch(
        "apps.core.api.views.auth.password_reset_change_password.PasswordResetChangePasswordView.throttle_classes",
        new=[],
    )
    def test_password_reset_step3_without_verified_request(self):
        # Authenticate with a token that didn't come from step 2
        access = str(RefreshToken.for_user(self.user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        url_change = reverse("core:forgot_password_change_password")
        resp = client.post(
            url_change,
            {"new_password": "NewSecure123!", "confirm_password": "NewSecure123!"},
            format="json",
        )
        # Should fail because no verified reset request exists
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        envelope = resp.json()
        self.assertFalse(envelope["success"])  # error envelope

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_otp_verification_with_device_id_success(self, mock_trigger_send_notification):
        """Test OTP verification with device_id creates UserDevice"""
        otp_code = self.user.generate_otp()
        device_id = "test-device-123"

        data = {"username": "testuser001", "otp_code": otp_code, "device_id": device_id}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])

        # Verify device was created
        self.user.refresh_from_db()
        self.assertTrue(hasattr(self.user, "device"))
        self.assertEqual(self.user.device.device_id, device_id)

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    def test_otp_verification_device_id_already_registered_to_another_user(self):
        """Test OTP verification fails when device_id is registered to another user"""
        # Create another user with a device
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )
        device_id = "shared-device-123"
        UserDevice.objects.create(user=other_user, device_id=device_id)

        # Try to verify OTP for first user with same device_id
        otp_code = self.user.generate_otp()
        data = {"username": "testuser001", "otp_code": otp_code, "device_id": device_id}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])

        # Check error message
        error_data = response_data["error"]
        self.assertTrue(
            "non_field_errors" in error_data
            or ("errors" in error_data and any(err.get("attr") == "non_field_errors" for err in error_data["errors"]))
        )

        # Verify the error message mentions the device is already registered
        error_message = str(error_data)
        self.assertIn("already registered", error_message)

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_otp_verification_device_id_same_user_no_error(self, mock_trigger_send_notification):
        """Test OTP verification succeeds when device_id is already registered to same user"""
        device_id = "my-device-456"
        UserDevice.objects.create(user=self.user, device_id=device_id)

        otp_code = self.user.generate_otp()
        data = {"username": "testuser001", "otp_code": otp_code, "device_id": device_id}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("tokens", response_data["data"])

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_otp_verification_without_device_id(self, mock_trigger_send_notification):
        """Test OTP verification without device_id still works"""
        otp_code = self.user.generate_otp()

        data = {"username": "testuser001", "otp_code": otp_code}
        response = self.client.post(self.otp_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])

        # Verify no device was created
        self.user.refresh_from_db()
        self.assertFalse(hasattr(self.user, "device") and self.user.device is not None)

    @patch("apps.core.api.views.auth.otp_verification.OTPVerificationView.throttle_classes", new=[])
    def test_otp_verification_user_with_device_trying_different_unassigned_device(self):
        """Test OTP verification fails when user with registered device tries to login with different unassigned device.

        This is a critical security check to prevent users from bypassing the device change request process.
        """
        # Create user with a registered device
        existing_device_id = "user-existing-device-789"
        UserDevice.objects.create(user=self.user, device_id=existing_device_id, platform="android")

        # User tries to login with a different device that is not assigned to anyone
        new_device_id = "different-unassigned-device-999"
        otp_code = self.user.generate_otp()
        data = {"username": "testuser001", "otp_code": otp_code, "device_id": new_device_id}
        response = self.client.post(self.otp_url, data, format="json")

        # Should reject the login
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])

        # Check error message mentions device change process
        error_data = response_data["error"]
        error_message = str(error_data)
        self.assertIn("different device", error_message.lower())
        self.assertIn("device change request", error_message.lower())

        # Verify the new device was NOT created
        self.assertFalse(UserDevice.objects.filter(device_id=new_device_id).exists())

        # Verify user still has only their original device
        self.user.refresh_from_db()
        self.assertEqual(self.user.device.device_id, existing_device_id)
