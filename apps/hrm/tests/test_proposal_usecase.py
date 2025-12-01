"""Tests for Proposal Management Use Case (UC 10.2).

This test file covers the following scenarios:
1. CRUD Operations (TC01-TC06)
2. Validation Logic (TC07-TC09)
3. Workflow & Permissions (TC10-TC13)
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import ProposalSession, ProposalStatus, ProposalType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    Position,
    Proposal,
    ProposalAsset,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_employee(db):
    """Create a test employee for proposal tests."""
    from apps.core.models import AdministrativeUnit, Province

    province = Province.objects.create(name="Test Province UC10", code="TPUC10")
    admin_unit = AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit UC10",
        code="TAUUC10",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch UC10",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block UC10", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept UC10", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer UC10")

    employee = Employee.objects.create(
        code="MV_UC10_001",
        fullname="UC10 Test Employee",
        username="user_uc10_001",
        email="uc10_001@example.com",
        attendance_code="UC10001",
        citizen_id="UC1000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )
    return employee


@pytest.fixture
def test_employee_with_user(test_employee):
    """Create a test employee that also has a user account for authentication."""
    user = test_employee.user
    user.is_superuser = True
    user.save()
    return test_employee


@pytest.fixture
def another_department(test_employee):
    """Create another department for transfer proposals."""
    return Department.objects.create(
        name="Another Dept UC10",
        branch=test_employee.branch,
        block=test_employee.block,
        function=Department.DepartmentFunction.BUSINESS,
    )


@pytest.fixture
def another_position(db):
    """Create another position for transfer proposals."""
    return Position.objects.create(name="Senior Developer UC10")


class TestCRUDOperations:
    """Test CRUD operations for Proposal Management (TC01-TC06)."""

    def test_tc01_create_paid_leave_proposal(self, api_client, test_employee_with_user):
        """TC01 - Verify creation of paid leave proposal with start_date, end_date, and session."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.PAID_LEAVE,
            "start_date": str(date.today() + timedelta(days=7)),
            "end_date": str(date.today() + timedelta(days=9)),
            "session": ProposalSession.FULL_DAY,
            "note": "Family vacation",
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal_type"] == ProposalType.PAID_LEAVE
        assert result["data"]["proposal_status"] == ProposalStatus.PENDING
        assert result["data"]["start_date"] == data["start_date"]
        assert result["data"]["end_date"] == data["end_date"]
        assert result["data"]["session"] == ProposalSession.FULL_DAY

    def test_tc02_create_overtime_proposal(self, api_client, test_employee_with_user):
        """TC02 - Verify creation of overtime proposal with date, total_hours."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.OVERTIME_WORK,
            "start_date": str(date.today() + timedelta(days=1)),
            "total_hours": "4.0",
            "note": "Project deadline",
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal_type"] == ProposalType.OVERTIME_WORK
        assert result["data"]["proposal_status"] == ProposalStatus.PENDING
        assert float(result["data"]["total_hours"]) == 4.0

    def test_tc03_create_asset_allocation_proposal(self, api_client, test_employee_with_user):
        """TC03 - Verify creation of asset allocation proposal with nested list of assets."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.ASSET_ALLOCATION,
            "assets": [
                {"name": "Laptop", "unit": "piece", "quantity": 1},
                {"name": "Monitor", "unit": "piece", "quantity": 2},
            ],
            "note": "New equipment request",
        }

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal_type"] == ProposalType.ASSET_ALLOCATION
        assert result["data"]["proposal_status"] == ProposalStatus.PENDING

        # Verify assets were created
        proposal_id = result["data"]["id"]
        proposal = Proposal.objects.get(id=proposal_id)
        assert proposal.assets.count() == 2
        assert proposal.assets.filter(name="Laptop").exists()
        assert proposal.assets.filter(name="Monitor", quantity=2).exists()

    def test_tc04_create_transfer_proposal(
        self, api_client, test_employee_with_user, another_department, another_position
    ):
        """TC04 - Verify creation of transfer proposal with effective_date, new_department, new_job_title."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.TRANSFER,
            "effective_date": str(date.today() + timedelta(days=30)),
            "new_department": another_department.id,
            "new_job_title": another_position.id,
            "note": "Department transfer request",
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal_type"] == ProposalType.TRANSFER
        assert result["data"]["proposal_status"] == ProposalStatus.PENDING
        assert result["data"]["effective_date"] == data["effective_date"]

    def test_tc05_update_pending_proposal(self, api_client, test_employee):
        """TC05 - Verify user can update a proposal while it is PENDING."""
        proposal = Proposal.objects.create(
            code="DX_UC10_005",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=15),  # Increased to allow for update
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        data = {
            "note": "Updated note",
            "start_date": str(date.today() + timedelta(days=10)),
        }

        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["note"] == "Updated note"

        proposal.refresh_from_db()
        assert proposal.start_date == date.today() + timedelta(days=10)

    def test_tc06_delete_pending_proposal(self, api_client, test_employee):
        """TC06 - Verify user can delete a proposal while it is PENDING."""
        proposal = Proposal.objects.create(
            code="DX_UC10_006",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )
        proposal_id = proposal.id

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Proposal.objects.filter(id=proposal_id).exists()


class TestValidationLogic:
    """Test validation logic for Proposal Management (TC07-TC09)."""

    def test_tc07_date_validation_start_after_end(self, api_client, test_employee_with_user):
        """TC07 - Ensure start_date cannot be after end_date."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.PAID_LEAVE,
            "start_date": str(date.today() + timedelta(days=10)),
            "end_date": str(date.today() + timedelta(days=5)),
            "session": ProposalSession.FULL_DAY,
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert result["success"] is False
        assert "start_date" in str(result["error"]).lower()

    def test_tc08_required_fields_complaint_reason(self, api_client, test_employee_with_user):
        """TC08 - Verify complaint_reason is required for complaint proposals."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            # Missing complaint_reason
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert result["success"] is False
        assert "complaint_reason" in str(result["error"]).lower()

    def test_tc08_required_fields_assets_for_asset_allocation(self, api_client, test_employee_with_user):
        """TC08 - Verify assets list is required for asset allocation proposals."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.ASSET_ALLOCATION,
            # Missing assets
        }

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert result["success"] is False
        assert "assets" in str(result["error"]).lower()

    def test_tc08_required_fields_leave_proposal(self, api_client, test_employee_with_user):
        """TC08 - Verify start_date and end_date are required for leave proposals."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.PAID_LEAVE,
            # Missing start_date and end_date
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert result["success"] is False

    def test_tc09_cannot_update_approved_proposal(self, api_client, test_employee):
        """TC09 - Verify user cannot update a proposal once it is APPROVED."""
        proposal = Proposal.objects.create(
            code="DX_UC10_009A",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        data = {"note": "Trying to update approved proposal"}

        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert result["success"] is False
        assert "pending" in str(result["error"]).lower()

    def test_tc09_cannot_update_rejected_proposal(self, api_client, test_employee):
        """TC09 - Verify user cannot update a proposal once it is REJECTED."""
        proposal = Proposal.objects.create(
            code="DX_UC10_009B",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.REJECTED,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            note="Rejected due to insufficient leave balance",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        data = {"note": "Trying to update rejected proposal"}

        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_tc09_cannot_delete_approved_proposal(self, api_client, test_employee):
        """TC09 - Verify user cannot delete a proposal once it is APPROVED."""
        proposal = Proposal.objects.create(
            code="DX_UC10_009C",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Proposal should still exist
        assert Proposal.objects.filter(id=proposal.id).exists()


class TestWorkflowAndPermissions:
    """Test workflow and permissions for Proposal Management (TC10-TC13)."""

    def test_tc10_approve_proposal(self, api_client, test_employee):
        """TC10 - Verify manager can approve a proposal (PENDING -> APPROVED)."""
        proposal = Proposal.objects.create(
            code="DX_UC10_010",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-approve", args=[proposal.id])
        data = {"note": "Approved as requested"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal_status"] == ProposalStatus.APPROVED

        proposal.refresh_from_db()
        assert proposal.proposal_status == ProposalStatus.APPROVED
        assert proposal.note == "Approved as requested"

    def test_tc11_reject_proposal(self, api_client, test_employee):
        """TC11 - Verify manager can reject a proposal (PENDING -> REJECTED) with required note."""
        proposal = Proposal.objects.create(
            code="DX_UC10_011",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-reject", args=[proposal.id])
        data = {"note": "Insufficient leave balance"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal_status"] == ProposalStatus.REJECTED

        proposal.refresh_from_db()
        assert proposal.proposal_status == ProposalStatus.REJECTED
        assert proposal.note == "Insufficient leave balance"

    def test_tc11_reject_without_note_fails(self, api_client, test_employee):
        """TC11 - Verify rejection fails without note."""
        proposal = Proposal.objects.create(
            code="DX_UC10_011B",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-reject", args=[proposal.id])
        data = {}  # Missing note

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_tc12_verify_proposal(self, api_client, superuser, test_employee):
        """TC12 - Verify assigned verifier can mark proposal as VERIFIED."""
        from apps.hrm.models import ProposalVerifier

        proposal = Proposal.objects.create(
            code="DX_UC10_012",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        # Assign verifier
        verifier = ProposalVerifier.objects.create(
            proposal=proposal,
            employee=test_employee,
        )

        url = reverse("hrm:proposal-verifier-verify", args=[verifier.id])
        data = {"note": "Verified and confirmed"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["status"] == "verified"
        assert result["data"]["verified_time"] is not None

    def test_tc13_cannot_approve_already_processed_proposal(self, api_client, test_employee):
        """TC13 - Verify cannot approve an already approved proposal."""
        proposal = Proposal.objects.create(
            code="DX_UC10_013A",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-approve", args=[proposal.id])
        data = {"note": "Trying to approve again"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert "processed" in str(result["error"]).lower()

    def test_tc13_cannot_reject_already_processed_proposal(self, api_client, test_employee):
        """TC13 - Verify cannot reject an already rejected proposal."""
        proposal = Proposal.objects.create(
            code="DX_UC10_013B",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.REJECTED,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=9),
            note="Already rejected",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-reject", args=[proposal.id])
        data = {"note": "Trying to reject again"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAdditionalFeatures:
    """Additional tests for edge cases and new proposal types."""

    def test_create_transfer_proposal_without_effective_date_fails(self, api_client, test_employee_with_user):
        """Verify transfer proposal requires effective_date."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.TRANSFER,
            # Missing effective_date
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert "effective_date" in str(result["error"]).lower()

    def test_create_overtime_proposal_without_total_hours_fails(self, api_client, test_employee_with_user):
        """Verify overtime proposal requires total_hours."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=test_employee_with_user.user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.OVERTIME_WORK,
            "start_date": str(date.today() + timedelta(days=1)),
            # Missing total_hours
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert "total_hours" in str(result["error"]).lower()

    def test_update_asset_allocation_replaces_assets(self, api_client, test_employee):
        """Verify updating assets on asset allocation proposal replaces existing assets."""
        proposal = Proposal.objects.create(
            code="DX_UC10_ASSET_UPDATE",
            proposal_type=ProposalType.ASSET_ALLOCATION,
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )
        ProposalAsset.objects.create(proposal=proposal, name="Old Laptop", unit="piece", quantity=1)

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        data = {
            "assets": [
                {"name": "New Desktop", "unit": "piece", "quantity": 1},
            ],
        }

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Old asset should be removed, new asset should exist
        proposal.refresh_from_db()
        assert proposal.assets.count() == 1
        assert proposal.assets.first().name == "New Desktop"

    def test_list_proposal_includes_assets(self, api_client, test_employee):
        """Verify list endpoint includes assets for asset allocation proposals."""
        proposal = Proposal.objects.create(
            code="DX_UC10_LIST_ASSETS",
            proposal_type=ProposalType.ASSET_ALLOCATION,
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )
        ProposalAsset.objects.create(proposal=proposal, name="Monitor", unit="piece", quantity=2)

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert "assets" in result["data"]
        assert len(result["data"]["assets"]) == 1
        assert result["data"]["assets"][0]["name"] == "Monitor"

    def test_create_proposal_without_user_employee_fails(self, api_client):
        """Verify that creating a proposal fails when user has no associated employee."""
        # Using superuser which doesn't have an associated employee by default
        from apps.core.models import User

        user = User.objects.create_user(username="noemployee", email="noemployee@test.com", password="test123")
        user.is_superuser = True
        user.save()

        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("hrm:proposal-list")
        data = {
            "proposal_type": ProposalType.PAID_LEAVE,
            "start_date": str(date.today() + timedelta(days=7)),
            "end_date": str(date.today() + timedelta(days=9)),
        }

        response = client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert "employee" in str(result["error"]).lower()

    def test_model_date_validation(self, test_employee):
        """Verify model-level validation for start_date > end_date via clean()."""
        from django.core.exceptions import ValidationError

        proposal = Proposal(
            proposal_type=ProposalType.PAID_LEAVE,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=5),
            created_by=test_employee,
        )

        with pytest.raises(ValidationError) as exc_info:
            proposal.clean()

        assert "start_date" in str(exc_info.value)
