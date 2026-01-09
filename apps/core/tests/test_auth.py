from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.constants import APP_TESTER_OTP_CODE, APP_TESTER_USERNAME
from apps.core.models import PasswordResetOTP, User, UserDevice


@pytest.mark.django_db
class TestAuthentication:
    @pytest.fixture(autouse=True)
    def setup_auth(self):
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
        self.mobile_login_url = reverse("mobile-core:login")
        self.me_url = reverse("core:me")
        self.mobile_me_url = reverse("mobile-core:me")
        self.forgot_password_url = reverse("core:forgot_password")

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_successful_login(self, mock_trigger_send_notification):
        """Test successful login with correct credentials (no OTP step)."""
        data = {"username": "testuser001", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()["data"]
        assert "tokens" in response_data
        assert "access" in response_data["tokens"]
        assert "refresh" in response_data["tokens"]

        token = AccessToken(response_data["tokens"]["access"])
        assert token["client"] == "web"
        assert token["device_id"] == "web-device-1"
        assert "tv" not in token

    def test_login_with_wrong_credentials(self):
        data = {"username": "testuser001", "password": "wrongpassword", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        assert not envelope["success"]
        errors = envelope["error"].get("errors", [])
        assert any("Incorrect password" in str(err.get("detail")) for err in errors)
        assert any(err.get("attr") == "password" for err in errors)

    def test_login_with_nonexistent_user(self):
        data = {"username": "NONEXISTENT", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        assert not envelope["success"]
        errors = envelope["error"].get("errors", [])
        assert any("Username does not exist" in str(err.get("detail")) for err in errors)
        assert any(err.get("attr") == "username" for err in errors)

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_account_lockout_after_failed_attempts(self):
        data = {"username": "testuser001", "password": "wrongpassword", "device_id": "web-device-1"}

        for _ in range(5):
            response = self.client.post(self.login_url, data, format="json")
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = self.client.post(self.login_url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        assert not envelope["success"]
        errors = envelope["error"].get("errors", [])
        # verify lockout error
        assert any("locked" in str(err.get("detail")).lower() for err in errors)
        assert any(err.get("attr") == "username" for err in errors)

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    @patch("apps.core.tasks.send_password_reset_email_task.delay")
    def test_password_reset_request_email(self, mock_email_task):
        """Test password reset request with email"""
        mock_email_task.return_value = MagicMock()

        data = {"identifier": "test@example.com"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"]
        assert "message" in response_data["data"]
        assert "Password reset" in response_data["data"]["message"]

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

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"]
        assert "message" in response_data["data"]
        # Message should indicate SMS was used
        assert "via SMS" in response_data["data"]["message"]  # contains SMS
        # Should include phone hint, not email hint
        assert "phone_hint" in response_data["data"]  # masked phone
        assert "email_hint" not in response_data["data"]  # no email hint in SMS path
        # Verify SMS task was called
        mock_sms_task.assert_called_once()

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    def test_password_reset_wrong_identifier(self):
        """Test password reset with wrong identifier"""
        data = {"identifier": "wrong@example.com"}
        response = self.client.post(self.forgot_password_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert not response_data["success"]
        assert "non_field_errors" in response_data["error"]

    def test_user_model_methods(self):
        """Test User model methods"""
        # Test account locking
        assert not self.user.is_locked
        self.user.lock_account()
        assert self.user.is_locked

        # Test account unlocking
        self.user.unlock_account()
        assert not self.user.is_locked
        assert self.user.failed_login_attempts == 0

        # Test OTP generation
        otp = self.user.generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()
        assert self.user.otp_expires_at is not None

        # Test OTP verification
        assert self.user.verify_otp(otp)
        assert not self.user.verify_otp("000000")

        # Test full name
        assert self.user.get_full_name() == "John Doe"
        assert self.user.get_short_name() == "John"

    def test_mobile_app_tester_login_otp_is_constant(self):
        tester = User.objects.create_superuser(
            username=APP_TESTER_USERNAME,
            email="mobile.tester@example.com",
            password="testpass123",
            first_name="Mobile",
            last_name="Tester",
        )

        otp = tester.generate_otp()

        assert otp == APP_TESTER_OTP_CODE
        assert tester.otp_code == APP_TESTER_OTP_CODE

    def test_mobile_app_tester_password_reset_otp_is_constant(self):
        tester = User.objects.create_superuser(
            username=APP_TESTER_USERNAME,
            email="mobile.tester.reset@example.com",
            password="testpass123",
            first_name="Mobile",
            last_name="Tester",
        )

        reset_request, otp = PasswordResetOTP.objects.create_request(tester, channel="email")

        assert otp == APP_TESTER_OTP_CODE
        assert len(otp) == 6
        assert reset_request.otp_hash

    def test_inactive_user_login(self):
        """Test login attempt with inactive user"""
        self.user.is_active = False
        self.user.save()

        data = {"username": "testuser001", "password": "testpass123", "device_id": "web-device-1"}
        response = self.client.post(self.login_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        assert not envelope["success"]
        errors = envelope["error"].get("errors", [])
        assert any("deactivated" in str(err.get("detail")).lower() for err in errors)
        assert any(err.get("attr") == "username" for err in errors)

    def test_empty_credentials(self):
        """Test login with empty credentials"""
        data = {"username": "", "password": "", "device_id": ""}
        response = self.client.post(self.login_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        assert not envelope["success"]
        errors = envelope["error"].get("errors", [])
        attrs = {err.get("attr") for err in errors}
        assert "username" in attrs
        assert "password" in attrs
        # device_id may be validated after other required fields depending on serializer validation flow

    @patch("apps.core.api.views.auth.password_reset.PasswordResetView.throttle_classes", new=[])
    @patch("apps.core.tasks.send_password_reset_email_task.delay")
    def test_password_reset_step1_returns_reset_token(self, mock_email_task):
        mock_email_task.return_value = MagicMock()

        data = {"identifier": self.user.email}
        url = reverse("core:forgot_password")
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        envelope = response.json()
        assert envelope["success"]  # wrapped by middleware
        data = envelope["data"]
        assert "message" in data
        assert "reset_token" in data
        assert "expires_at" in data
        assert "email_hint" in data
        # reset_token should correspond to a DB record
        reset_request = PasswordResetOTP.objects.get_by_token(data["reset_token"])
        assert reset_request is not None

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
        assert response.status_code == status.HTTP_200_OK
        envelope = response.json()
        assert envelope["success"]  # wrapped by middleware
        data = envelope["data"]
        assert "message" in data
        assert "tokens" in data
        assert "access" in data["tokens"]  # access token provided
        assert "refresh" in data["tokens"]  # refresh token provided

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
        assert resp2.status_code == status.HTTP_200_OK
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

        assert resp3.status_code == status.HTTP_200_OK
        self.user.refresh_from_db()
        assert self.user.check_password(new_password)
        # Ensure reset request is cleaned up
        assert not PasswordResetOTP.objects.filter(user=self.user, is_verified=True, is_used=False).exists()

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
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @patch(
        "apps.core.api.views.auth.password_reset_change_password.PasswordResetChangePasswordView.throttle_classes",
        new=[],
    )
    def test_password_reset_step3_without_verified_request(self):
        # Authenticate with a token that didn't come from step 2
        refresh = RefreshToken.for_user(self.user)
        refresh["client"] = "web"
        refresh["device_id"] = "web-test"
        access = str(refresh.access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        url_change = reverse("core:forgot_password_change_password")
        resp = client.post(
            url_change,
            {"new_password": "NewSecure123!", "confirm_password": "NewSecure123!"},
            format="json",
        )
        # Should fail because no verified reset request exists
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        envelope = resp.json()
        assert not envelope["success"]  # error envelope

    def test_routing_web_and_mobile_login_endpoints_exist(self):
        """Web endpoints remain unchanged; mobile endpoints exist with /mobile/ prefix."""
        assert self.login_url == "/api/auth/login/"
        assert self.mobile_login_url == "/api/mobile/auth/login/"

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_web_login_sets_claims_and_updates_last_web_device(self, mock_trigger_send_notification):
        device_id = "web-device-123"

        resp = self.client.post(
            self.login_url,
            {"username": self.user.username, "password": "testpass123", "device_id": device_id},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        access = resp.json()["data"]["tokens"]["access"]

        token = AccessToken(access)
        assert token["client"] == "web"
        assert token["device_id"] == device_id
        assert "tv" not in token

        assert UserDevice.objects.filter(
            user=self.user,
            client=UserDevice.Client.WEB,
            device_id=device_id,
            platform=UserDevice.Platform.WEB,
        ).exists()

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_employee_cannot_login_web(self):
        from apps.core.models import Role

        employee_role = Role.objects.create(code="employee", name="Employee")
        employee = User.objects.create_user(username="emp", email="emp@example.com", password="testpass123")
        employee.role = employee_role
        employee.save(update_fields=["role"])

        resp = self.client.post(
            self.login_url,
            {"username": employee.username, "password": "testpass123", "device_id": "web-emp"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert not resp.json()["success"]

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_web_login_not_blocked_by_mobile_binding(self, mock_trigger_send_notification):
        UserDevice.objects.create(
            user=self.user,
            client=UserDevice.Client.MOBILE,
            state=UserDevice.State.ACTIVE,
            device_id="mobile-bound-1",
            platform="android",
        )

        resp = self.client.post(
            self.login_url,
            {"username": self.user.username, "password": "testpass123", "device_id": "web-2"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    @patch("apps.notifications.utils.trigger_send_notification")
    def test_mobile_login_first_time_creates_active_device_and_sets_claims(self, mock_trigger_send_notification):
        device_id = "mobile-device-1"

        resp = self.client.post(
            self.mobile_login_url,
            {
                "username": self.user.username,
                "password": "testpass123",
                "device_id": device_id,
                "platform": "android",
                "push_token": "push-1",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

        access = resp.json()["data"]["tokens"]["access"]
        token = AccessToken(access)
        assert token["client"] == "mobile"
        assert token["device_id"] == device_id
        assert token["tv"] == self.user.mobile_token_version

        assert UserDevice.objects.filter(
            user=self.user,
            client=UserDevice.Client.MOBILE,
            state=UserDevice.State.ACTIVE,
            device_id=device_id,
        ).exists()

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_mobile_login_same_device_ok(self):
        UserDevice.objects.create(
            user=self.user,
            client=UserDevice.Client.MOBILE,
            state=UserDevice.State.ACTIVE,
            device_id="mobile-device-1",
            platform="android",
        )

        resp = self.client.post(
            self.mobile_login_url,
            {"username": self.user.username, "password": "testpass123", "device_id": "mobile-device-1"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert UserDevice.objects.filter(user=self.user, client="mobile", state="active").count() == 1

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_mobile_login_different_device_conflict(self):
        UserDevice.objects.create(
            user=self.user,
            client=UserDevice.Client.MOBILE,
            state=UserDevice.State.ACTIVE,
            device_id="mobile-device-1",
            platform="android",
        )

        resp = self.client.post(
            self.mobile_login_url,
            {"username": self.user.username, "password": "testpass123", "device_id": "mobile-device-2"},
            format="json",
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_employee_web_token_forbidden_on_web_protected_endpoint(self):
        from apps.core.models import Role

        employee_role = Role.objects.create(code="employee", name="Employee")
        employee = User.objects.create_user(username="emp2", email="emp2@example.com", password="testpass123")
        employee.role = employee_role
        employee.save(update_fields=["role"])

        refresh = RefreshToken.for_user(employee)
        refresh["client"] = "web"
        refresh["device_id"] = "web-emp"
        access = refresh.access_token
        access["client"] = "web"
        access["device_id"] = "web-emp"

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = client.get(self.me_url, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.core.api.views.auth.login.LoginView.throttle_classes", new=[])
    def test_mobile_token_version_mismatch_rejected(self):
        resp = self.client.post(
            self.mobile_login_url,
            {"username": self.user.username, "password": "testpass123", "device_id": "mobile-device-1"},
            format="json",
        )
        access = resp.json()["data"]["tokens"]["access"]

        self.user.mobile_token_version += 1
        self.user.save(update_fields=["mobile_token_version"])

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp2 = client.get(self.mobile_me_url, format="json")
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPasswordChangeValidation:
    """Test validation errors for password change endpoint"""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser_pwd_val",
            email="test_pwd_val@example.com",
            password="OldPassword123!",
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("core:change_password")

    def test_change_password_mismatch_confirm(self):
        """Test that password mismatch error is associated with confirm_password"""
        data = {
            "old_password": "OldPassword123!",
            "new_password": "NewPassword123!",
            "confirm_password": "DifferentPassword123!",
        }
        response = self.client.post(self.url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        assert not envelope["success"]

        # View returns serializer.errors directly, wrapped by middleware in 'error'
        # Since PasswordChangeView returns Response(serializer.errors), the structure
        # is likely {"success": False, "error": {"confirm_password": [...]}}
        errors = envelope["error"]

        # Verify field attribution
        assert "confirm_password" in errors
        # Verify message content roughly
        assert "match" in str(errors["confirm_password"])

    def test_change_password_same_as_old(self):
        """Test that new password same as old error is associated with new_password"""
        data = {
            "old_password": "OldPassword123!",
            "new_password": "OldPassword123!",
            "confirm_password": "OldPassword123!",
        }
        response = self.client.post(self.url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        errors = envelope["error"]

        # Verify field attribution
        assert "new_password" in errors
        assert "different" in str(errors["new_password"])

    def test_change_password_incorrect_old(self):
        """Test that incorrect old password error is associated with old_password"""
        data = {
            "old_password": "WrongPassword123!",
            "new_password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
        }
        response = self.client.post(self.url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        envelope = response.json()
        errors = envelope["error"]

        # Verify field attribution
        assert "old_password" in errors
        assert "incorrect" in str(errors["old_password"]).lower()
