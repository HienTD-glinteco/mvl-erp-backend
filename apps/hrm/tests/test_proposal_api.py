import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal

pytestmark = pytest.mark.django_db


class TestProposalAPI:
    """Tests for Proposal API that lists all proposals regardless of type."""

    def test_list_all_proposals(self, api_client, superuser):
        """Test listing all proposals returns proposals of all types."""
        Proposal.objects.create(
            code="DX000001", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000002", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")
        Proposal.objects.create(code="DX000003", proposal_type=ProposalType.OVERTIME_WORK, note="Test 3")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should return all proposals regardless of type
        assert data["data"]["count"] == 3

    def test_list_all_proposals_filter_by_status(self, api_client, superuser):
        """Test filtering all proposals by status."""
        Proposal.objects.create(
            code="DX000004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            proposal_status=ProposalStatus.PENDING,
        )
        Proposal.objects.create(
            code="DX000005",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            proposal_status=ProposalStatus.APPROVED,
        )
        Proposal.objects.create(
            code="DX000006",
            proposal_type=ProposalType.OVERTIME_WORK,
            note="Test 3",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_status": ProposalStatus.PENDING})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should return only pending proposals (2 items)
        assert data["data"]["count"] == 2
        for result in data["data"]["results"]:
            assert result["proposal_status"] == ProposalStatus.PENDING

    def test_list_all_proposals_filter_by_type(self, api_client, superuser):
        """Test filtering all proposals by proposal type."""
        Proposal.objects.create(
            code="DX000007", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000008", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")
        Proposal.objects.create(code="DX000009", proposal_type=ProposalType.PAID_LEAVE, note="Test 3")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.PAID_LEAVE})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should return only paid leave proposals (2 items)
        assert data["data"]["count"] == 2
        for result in data["data"]["results"]:
            assert result["proposal_type"] == ProposalType.PAID_LEAVE

    def test_retrieve_proposal(self, api_client, superuser):
        """Test retrieving a single proposal by ID."""
        proposal = Proposal.objects.create(
            code="DX000010", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test complaint"
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == proposal.id
        assert data["data"]["proposal_type"] == ProposalType.TIMESHEET_ENTRY_COMPLAINT


class TestTimesheetEntryComplaintProposalAPI:
    """Tests for Timesheet Entry Complaint Proposal API."""

    def test_list_timesheet_entry_complaint_proposals(self, api_client, superuser):
        Proposal.objects.create(
            code="DX000001", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000002", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return timesheet entry complaints, not paid leave
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.TIMESHEET_ENTRY_COMPLAINT

    def test_filter_by_status(self, api_client, superuser):
        Proposal.objects.create(
            code="DX000003",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            proposal_status=ProposalStatus.PENDING,
        )
        Proposal.objects.create(
            code="DX000004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 2",
            proposal_status=ProposalStatus.APPROVED,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(
            url, {"proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT, "proposal_status": ProposalStatus.PENDING}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_status"] == ProposalStatus.PENDING

    def test_approve_complaint_success(self, api_client, superuser):
        proposal = Proposal.objects.create(
            code="DX000005",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-approve", args=[proposal.id])
        data = {"approved_check_in_time": "08:00:00", "approved_check_out_time": "17:00:00", "note": "Approved"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        proposal.refresh_from_db()
        assert proposal.proposal_status == ProposalStatus.APPROVED
        assert str(proposal.approved_check_in_time) == "08:00:00"
        assert str(proposal.approved_check_out_time) == "17:00:00"
        assert proposal.note == "Approved"

    def test_reject_complaint_success(self, api_client, superuser):
        proposal = Proposal.objects.create(
            code="DX000006",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-reject", args=[proposal.id])
        data = {"note": "Rejected due to lack of evidence"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        proposal.refresh_from_db()
        assert proposal.proposal_status == ProposalStatus.REJECTED
        assert proposal.note == "Rejected due to lack of evidence"

    def test_reject_complaint_missing_note(self, api_client, superuser):
        proposal = Proposal.objects.create(
            code="DX000007",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-reject", args=[proposal.id])
        data = {"note": ""}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        # Check if any error attribute is 'note'
        errors = data.get("error", {}).get("errors", [])
        assert any(error.get("attr") == "note" for error in errors)


class TestPaidLeaveProposalAPI:
    """Tests for Paid Leave Proposal API."""

    def test_list_paid_leave_proposals(self, api_client, superuser):
        Proposal.objects.create(
            code="DX000008", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000009", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.PAID_LEAVE})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return paid leave proposals
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.PAID_LEAVE


class TestOvertimeWorkProposalAPI:
    """Tests for Overtime Work Proposal API."""

    def test_list_overtime_work_proposals(self, api_client, superuser):
        Proposal.objects.create(code="DX000010", proposal_type=ProposalType.PAID_LEAVE, note="Test 1")
        Proposal.objects.create(code="DX000011", proposal_type=ProposalType.OVERTIME_WORK, note="Test 2")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.OVERTIME_WORK})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return overtime work proposals
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.OVERTIME_WORK
