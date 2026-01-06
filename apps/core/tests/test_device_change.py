from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import DeviceChangeRequest, User, UserDevice
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Block, Branch, Department, Employee, Position, Proposal


class DeviceChangeRequestTestCase(TestCase):
    """Test cases for device change request flow."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Disable throttling for tests
        from apps.core.api.views.auth.device_change import DeviceChangeRequestView, DeviceChangeVerifyOTPView

        DeviceChangeRequestView.throttle_classes = []
        DeviceChangeVerifyOTPView.throttle_classes = []

        # Create province and administrative unit first
        from apps.core.models import AdministrativeUnit, Province

        self.province = Province.objects.create(name="Test Province", code="TP")
        self.admin_unit = AdministrativeUnit.objects.create(
            parent_province=self.province,
            name="Test Admin Unit",
            code="TAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Create organizational structure
        self.branch = Branch.objects.create(
            name="Main Branch", code="MB001", province=self.province, administrative_unit=self.admin_unit
        )
        self.block = Block.objects.create(
            name="Block A", code="BLA", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            name="IT Department",
            code="IT",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )
        self.position = Position.objects.create(name="Developer", code="DEV")

        # Create user with employee
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        self.employee = Employee.objects.create(
            user=self.user,
            fullname="Test User",
            username="testuser",
            email="test@example.com",
            phone="0901234567",
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            personal_email="test@example.com",
        )

        # Create existing device for user
        self.old_device_id = "old_device_token_123"
        UserDevice.objects.create(user=self.user, device_id=self.old_device_id, platform="android")

        # URLs
        self.request_url = reverse("mobile-core:device_change_request")
        self.verify_otp_url = reverse("mobile-core:device_change_verify_otp")

    @patch("apps.core.api.views.auth.device_change.send_otp_device_change_task.delay")
    def test_device_change_request_success(self, mock_email_task):
        """Test successful device change request creates DeviceChangeRequest and sends OTP."""
        mock_email_task.return_value = MagicMock()

        data = {
            "username": "testuser",
            "password": "testpass123",
            "device_id": "new_device_token_456",
            "platform": "ios",
            "notes": "Switching to new iPhone",
        }

        response = self.client.post(self.request_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("request_id", response_data["data"])
        self.assertIn("expires_in_seconds", response_data["data"])

        # Verify DeviceChangeRequest was created
        request_id = response_data["data"]["request_id"]
        device_request = DeviceChangeRequest.objects.get(id=request_id)
        self.assertEqual(device_request.user, self.user)
        self.assertEqual(device_request.new_device_id, "new_device_token_456")
        self.assertEqual(device_request.new_platform, "ios")
        self.assertEqual(device_request.status, DeviceChangeRequest.Status.OTP_SENT)

        # Verify OTP email task was called
        mock_email_task.assert_called_once()

    def test_device_change_request_same_device_rejected(self):
        """Test that requesting same device_id as current device is rejected."""
        data = {
            "username": "testuser",
            "password": "testpass123",
            "device_id": self.old_device_id,  # Same as current device
            "platform": "android",
        }

        response = self.client.post(self.request_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("non_field_errors", response_data["error"])

    def test_device_change_request_invalid_credentials(self):
        """Test that invalid credentials are rejected."""
        data = {
            "username": "testuser",
            "password": "wrongpassword",
            "device_id": "new_device_token_789",
        }

        response = self.client.post(self.request_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])

    @patch("apps.core.models.User.generate_otp")
    @patch("apps.core.api.views.auth.device_change.send_otp_device_change_task.delay")
    def test_verify_otp_creates_proposal(self, mock_email_task, mock_generate_otp):
        """Test that verifying OTP creates a device change proposal."""
        mock_email_task.return_value = MagicMock()
        mock_generate_otp.return_value = "123456"

        # Create a new user for this test to avoid rate limiting
        user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )
        employee2 = Employee.objects.create(
            user=user2,
            fullname="Test User 2",
            username="testuser2",
            email="test2@example.com",
            phone="0901234568",
            citizen_id="1234567892",
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            personal_email="test2@example.com",
        )
        UserDevice.objects.create(user=user2, device_id="old_device_2", platform="android")

        # First create a device change request
        data = {
            "username": "testuser2",
            "password": "testpass123",
            "device_id": "new_device_token_999",
            "platform": "web",
            "notes": "Using web browser",
        }

        response = self.client.post(self.request_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        request_id = response.json()["data"]["request_id"]

        # Get the device request
        device_request = DeviceChangeRequest.objects.get(id=request_id)
        # Use the mocked OTP
        otp_code = "123456"

        # Verify OTP
        verify_data = {"request_id": request_id, "otp": otp_code}
        response = self.client.post(self.verify_otp_url, verify_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("proposal_id", response_data["data"])

        # Verify Proposal was created
        proposal_id = response_data["data"]["proposal_id"]
        proposal = Proposal.objects.get(id=proposal_id)
        self.assertEqual(proposal.proposal_type, ProposalType.DEVICE_CHANGE)
        self.assertEqual(proposal.proposal_status, ProposalStatus.PENDING)
        self.assertEqual(proposal.created_by, employee2)
        self.assertEqual(proposal.device_change_new_device_id, "new_device_token_999")
        self.assertEqual(proposal.device_change_new_platform, "web")
        self.assertEqual(proposal.device_change_old_device_id, "old_device_2")

        # Verify DeviceChangeRequest marked as verified
        device_request.refresh_from_db()
        self.assertEqual(device_request.status, DeviceChangeRequest.Status.VERIFIED)

    @patch("apps.core.models.User.generate_otp")
    @patch("apps.core.api.views.auth.device_change.send_otp_device_change_task.delay")
    def test_verify_otp_wrong_otp(self, mock_email_task, mock_generate_otp):
        """Test that wrong OTP is rejected and attempts are tracked."""
        mock_email_task.return_value = MagicMock()
        mock_generate_otp.return_value = "123456"

        # Create a new user for this test
        user3 = User.objects.create_user(
            username="testuser3",
            email="test3@example.com",
            password="testpass123",
        )
        UserDevice.objects.create(user=user3, device_id="old_device_3", platform="android")

        # Create device change request
        data = {
            "username": "testuser3",
            "password": "testpass123",
            "device_id": "new_device_token_111",
        }
        response = self.client.post(self.request_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        request_id = response.json()["data"]["request_id"]

        # Try with wrong OTP
        verify_data = {"request_id": request_id, "otp": "000000"}
        response = self.client.post(self.verify_otp_url, verify_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])

        # Check attempts were incremented
        device_request = DeviceChangeRequest.objects.get(id=request_id)
        self.assertEqual(device_request.otp_attempts, 1)

    @patch("apps.core.models.User.generate_otp")
    @patch("apps.core.api.views.auth.device_change.send_otp_device_change_task.delay")
    def test_verify_otp_expired(self, mock_email_task, mock_generate_otp):
        """Test that expired OTP is rejected."""
        mock_email_task.return_value = MagicMock()
        mock_generate_otp.return_value = "123456"

        # Create a new user for this test
        user4 = User.objects.create_user(
            username="testuser4",
            email="test4@example.com",
            password="testpass123",
        )
        UserDevice.objects.create(user=user4, device_id="old_device_4", platform="android")

        # Create device change request
        data = {
            "username": "testuser4",
            "password": "testpass123",
            "device_id": "new_device_token_222",
        }
        response = self.client.post(self.request_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        request_id = response.json()["data"]["request_id"]

        # Manually expire the OTP
        device_request = DeviceChangeRequest.objects.get(id=request_id)
        device_request.otp_expires_at = timezone.now() - timedelta(seconds=1)
        device_request.save()

        # Generate valid OTP
        otp_code = self.user.generate_otp()

        # Try to verify with expired request
        verify_data = {"request_id": request_id, "otp": otp_code}
        response = self.client.post(self.verify_otp_url, verify_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("expired", str(response_data["error"]).lower())
