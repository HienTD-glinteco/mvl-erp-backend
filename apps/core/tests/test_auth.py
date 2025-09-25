from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.core.models import User


class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            employee_code="EMP001",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )
        self.login_url = reverse("core:login")
        self.otp_url = reverse("core:verify_otp")
        self.forgot_password_url = reverse("core:forgot_password")

    def test_successful_login(self):
        """Test successful login with correct credentials"""
        data = {
            "employee_code": "EMP001",
            "password": "testpass123"
        }
        response = self.client.post(self.login_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("OTP đã được gửi", response.data["message"])
        self.assertEqual(response.data["employee_code"], "EMP001")
        self.assertIn("email_hint", response.data)

    def test_login_with_wrong_credentials(self):
        """Test login with wrong credentials"""
        data = {
            "employee_code": "EMP001",
            "password": "wrongpassword"
        }
        response = self.client.post(self.login_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_login_with_nonexistent_user(self):
        """Test login with non-existent employee code"""
        data = {
            "employee_code": "NONEXISTENT",
            "password": "testpass123"
        }
        response = self.client.post(self.login_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_account_lockout_after_failed_attempts(self):
        """Test account lockout after 5 failed login attempts"""
        data = {
            "employee_code": "EMP001",
            "password": "wrongpassword"
        }
        
        # Make 5 failed attempts
        for i in range(5):
            response = self.client.post(self.login_url, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 6th attempt should show account locked message
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("khóa", response.data["non_field_errors"][0])

    def test_otp_verification_success(self):
        """Test successful OTP verification"""
        # First login to generate OTP
        self.user.generate_otp()
        otp_code = self.user.otp_code
        
        data = {
            "employee_code": "EMP001",
            "otp_code": otp_code
        }
        response = self.client.post(self.otp_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("tokens", response.data)
        self.assertIn("user", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_otp_verification_wrong_code(self):
        """Test OTP verification with wrong code"""
        # First login to generate OTP
        self.user.generate_otp()
        
        data = {
            "employee_code": "EMP001",
            "otp_code": "000000"  # Wrong OTP
        }
        response = self.client.post(self.otp_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_password_reset_request_email(self):
        """Test password reset request with email"""
        data = {
            "identifier": "test@example.com"
        }
        response = self.client.post(self.forgot_password_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("đặt lại mật khẩu", response.data["message"])

    def test_password_reset_request_phone(self):
        """Test password reset request with phone number"""
        # Add phone number to user
        self.user.phone_number = "0123456789"
        self.user.save()
        
        data = {
            "identifier": "0123456789"
        }
        response = self.client.post(self.forgot_password_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("đặt lại mật khẩu", response.data["message"])

    def test_password_reset_wrong_identifier(self):
        """Test password reset with wrong identifier"""
        data = {
            "identifier": "wrong@example.com"
        }
        response = self.client.post(self.forgot_password_url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

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
        self.assertEqual(self.user.get_full_name(), "Doe John")
        self.assertEqual(self.user.get_short_name(), "John")