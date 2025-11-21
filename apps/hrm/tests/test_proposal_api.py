import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal

pytestmark = pytest.mark.django_db


class TestProposalAPI:
    def test_list_proposals(self, api_client, superuser):
        Proposal.objects.create(
            code="DX000001", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000002", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2

    def test_filter_proposals_by_type(self, api_client, superuser):
        Proposal.objects.create(
            code="DX000003", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000004", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.TIMESHEET_ENTRY_COMPLAINT

    def test_filter_proposals_by_type_in(self, api_client, superuser):
        Proposal.objects.create(
            code="DX000005", proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT, complaint_reason="Test 1"
        )
        Proposal.objects.create(code="DX000006", proposal_type=ProposalType.PAID_LEAVE, note="Test 2")
        Proposal.objects.create(code="DX000007", proposal_type=ProposalType.OVERTIME_WORK, note="Test 3")

        url = reverse("hrm:proposal-list")
        response = api_client.get(
            url, {"proposal_type__in": f"{ProposalType.TIMESHEET_ENTRY_COMPLAINT},{ProposalType.PAID_LEAVE}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["count"] == 2

    def test_approve_complaint_success(self, api_client, superuser):
        proposal = Proposal.objects.create(
            code="DX000008",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-approve-complaint", args=[proposal.id])
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

    def test_approve_complaint_wrong_type(self, api_client, superuser):
        proposal = Proposal.objects.create(
            code="DX000009",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Leave request",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-approve-complaint", args=[proposal.id])
        data = {"approved_check_in_time": "08:00:00", "approved_check_out_time": "17:00:00"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "only applicable for complaint proposals" in data["error"]["detail"]

    def test_reject_complaint_success(self, api_client, superuser):
        proposal = Proposal.objects.create(
            code="DX000010",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-reject-complaint", args=[proposal.id])
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
            code="DX000011",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
        )

        url = reverse("hrm:proposal-reject-complaint", args=[proposal.id])
        data = {"note": ""}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        # Check if any error attribute is 'note'
        errors = data.get("error", {}).get("errors", [])
        assert any(error.get("attr") == "note" for error in errors)
