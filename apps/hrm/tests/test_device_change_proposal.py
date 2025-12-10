from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import User, UserDevice
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Block, Branch, Department, Employee, Position, Proposal


class DeviceChangeProposalApprovalTestCase(TestCase):
    """Test cases for device change proposal approval/rejection."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create province and administrative unit first
        from apps.core.models import AdministrativeUnit, Province

        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province,
            name="Test Admin Unit",
            code="TAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Create organizational structure
        self.branch = Branch.objects.create(
            name="Main Branch", code="MB001", province=province, administrative_unit=admin_unit
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
        self.admin_position = Position.objects.create(name="Admin", code="ADM")

        # Create requester user with employee
        self.requester_user = User.objects.create_user(
            username="requester",
            email="requester@example.com",
            password="testpass123",
        )
        self.requester_employee = Employee.objects.create(
            user=self.requester_user,
            fullname="Requester User",
            username="requester",
            email="requester@example.com",
            phone="0901111111",
            citizen_id="1234567890",
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
        )

        # Create admin user with employee
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.admin_employee = Employee.objects.create(
            user=self.admin_user,
            fullname="Admin User",
            username="admin",
            email="admin@example.com",
            phone="0902222222",
            citizen_id="0987654321",
            department=self.department,
            position=self.admin_position,
            start_date="2024-01-01",
        )

        # Create existing device for requester
        self.old_device_id = "old_device_token_123"
        self.requester_device = UserDevice.objects.create(
            user=self.requester_user, device_id=self.old_device_id, platform="android"
        )

        # Create another user with a device (for reassignment test)
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )
        self.other_employee = Employee.objects.create(
            user=self.other_user,
            fullname="Other User",
            username="otheruser",
            email="other@example.com",
            phone="0903333333",
            citizen_id="1122334455",
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
        )
        self.conflicting_device_id = "device_to_reassign"
        self.other_device = UserDevice.objects.create(
            user=self.other_user, device_id=self.conflicting_device_id, platform="ios"
        )

    def _create_device_change_proposal(self, new_device_id, old_device_id=None):
        """Helper to create a device change proposal."""
        return Proposal.objects.create(
            proposal_type=ProposalType.DEVICE_CHANGE,
            proposal_status=ProposalStatus.PENDING,
            created_by=self.requester_employee,
            device_change_new_device_id=new_device_id,
            device_change_new_platform="ios",
            device_change_old_device_id=old_device_id or self.old_device_id,
            note="Requesting new device",
        )

    @patch("apps.notifications.utils.trigger_send_notification")
    @patch("apps.core.utils.jwt.OutstandingToken")
    @patch("apps.core.utils.jwt.BlacklistedToken")
    def test_approve_device_change_simple(self, mock_blacklisted, mock_outstanding, mock_notify):
        """Test approving device change proposal with new device."""
        # Mock JWT token blacklisting
        mock_outstanding.objects.filter.return_value = []
        mock_blacklisted.objects.get_or_create = MagicMock()

        # Create proposal
        new_device_id = "brand_new_device_789"
        proposal = self._create_device_change_proposal(new_device_id)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Approve proposal
        url = f"/api/hrm/proposals/{proposal.id}/approve/"
        response = self.client.post(url, {"approval_note": "Approved"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify proposal status
        proposal.refresh_from_db()
        self.assertEqual(proposal.proposal_status, ProposalStatus.APPROVED)
        self.assertEqual(proposal.approved_by, self.admin_employee)

        # Verify device was assigned to requester
        requester_device = UserDevice.objects.get(user=self.requester_user)
        self.assertEqual(requester_device.device_id, new_device_id)
        self.assertEqual(requester_device.platform, "ios")

        # Verify old device was removed
        self.assertFalse(UserDevice.objects.filter(device_id=self.old_device_id).exists())

    @patch("apps.notifications.utils.trigger_send_notification")
    @patch("apps.core.utils.jwt.OutstandingToken")
    @patch("apps.core.utils.jwt.BlacklistedToken")
    def test_approve_device_change_with_reassignment(self, mock_blacklisted, mock_outstanding, mock_notify):
        """Test approving device change when new device belongs to another user."""
        # Mock JWT token blacklisting
        mock_outstanding.objects.filter.return_value = []
        mock_blacklisted.objects.get_or_create = MagicMock()

        # Create proposal requesting device that belongs to other_user
        proposal = self._create_device_change_proposal(self.conflicting_device_id)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Approve proposal
        url = f"/api/hrm/proposals/{proposal.id}/approve/"
        response = self.client.post(url, {"approval_note": "Approved for reassignment"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify proposal status
        proposal.refresh_from_db()
        self.assertEqual(proposal.proposal_status, ProposalStatus.APPROVED)

        # Verify device was reassigned to requester
        requester_device = UserDevice.objects.get(user=self.requester_user)
        self.assertEqual(requester_device.device_id, self.conflicting_device_id)

        # Verify other_user no longer has the device
        self.assertFalse(
            UserDevice.objects.filter(user=self.other_user, device_id=self.conflicting_device_id).exists()
        )

        # Verify old device was removed from requester
        self.assertFalse(UserDevice.objects.filter(device_id=self.old_device_id).exists())

    @patch("apps.notifications.utils.trigger_send_notification")
    def test_reject_device_change(self, mock_notify):
        """Test rejecting device change proposal."""
        # Create proposal
        new_device_id = "rejected_device_555"
        proposal = self._create_device_change_proposal(new_device_id)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Reject proposal
        url = f"/api/hrm/proposals/{proposal.id}/reject/"
        response = self.client.post(url, {"approval_note": "Device not authorized"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify proposal status
        proposal.refresh_from_db()
        self.assertEqual(proposal.proposal_status, ProposalStatus.REJECTED)
        self.assertEqual(proposal.approved_by, self.admin_employee)
        self.assertEqual(proposal.approval_note, "Device not authorized")

        # Verify device was NOT assigned to requester
        requester_device = UserDevice.objects.get(user=self.requester_user)
        self.assertEqual(requester_device.device_id, self.old_device_id)  # Still has old device

        # Verify new device was not created
        self.assertFalse(UserDevice.objects.filter(device_id=new_device_id).exists())

    def test_non_admin_cannot_approve(self):
        """Test that non-admin users cannot approve proposals."""
        # Create proposal
        proposal = self._create_device_change_proposal("unauthorized_device")

        # Authenticate as regular user (requester)
        self.client.force_authenticate(user=self.requester_user)

        # Try to approve
        url = f"/api/hrm/proposals/{proposal.id}/approve/"
        response = self.client.post(url, {"approval_note": "Trying to approve"}, format="json")

        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify proposal status unchanged
        proposal.refresh_from_db()
        self.assertEqual(proposal.proposal_status, ProposalStatus.PENDING)
