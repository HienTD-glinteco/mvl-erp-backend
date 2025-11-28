from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    Position,
    Proposal,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_employee(db):
    """Create a test employee for proposal tests."""
    from apps.core.models import AdministrativeUnit, Province

    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit",
        code="TAU",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer")

    employee = Employee.objects.create(
        code="MV_PROP_001",
        fullname="Proposal Test Employee",
        username="user_prop_001",
        email="prop001@example.com",
        attendance_code="99001",
        citizen_id="999000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )
    return employee


class TestProposalAPI:
    """Tests for Proposal API that lists all proposals regardless of type."""

    def test_list_all_proposals(self, api_client, superuser, test_employee):
        """Test listing all proposals returns proposals of all types."""
        Proposal.objects.create(
            code="DX000001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000003",
            proposal_type=ProposalType.OVERTIME_WORK,
            note="Test 3",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should return all proposals regardless of type
        assert data["data"]["count"] == 3

    def test_list_all_proposals_filter_by_status(self, api_client, superuser, test_employee):
        """Test filtering all proposals by status."""
        Proposal.objects.create(
            code="DX000004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000005",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000006",
            proposal_type=ProposalType.OVERTIME_WORK,
            note="Test 3",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
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

    def test_list_all_proposals_filter_by_type(self, api_client, superuser, test_employee):
        """Test filtering all proposals by proposal type."""
        Proposal.objects.create(
            code="DX000007",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000008",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000009",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 3",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.PAID_LEAVE})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should return only paid leave proposals (2 items)
        assert data["data"]["count"] == 2
        for result in data["data"]["results"]:
            assert result["proposal_type"] == ProposalType.PAID_LEAVE

    def test_retrieve_proposal(self, api_client, superuser, test_employee):
        """Test retrieving a single proposal by ID."""
        proposal = Proposal.objects.create(
            code="DX000010",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test complaint",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == proposal.id
        assert data["data"]["proposal_type"] == ProposalType.TIMESHEET_ENTRY_COMPLAINT

    def test_retrieve_proposal_includes_created_by_employee_data(self, api_client, superuser, test_employee):
        """Test that retrieving a proposal includes created_by employee nested data."""
        proposal = Proposal.objects.create(
            code="DX000011",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test complaint",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Verify created_by contains employee nested data
        created_by = data["data"]["created_by"]
        assert created_by is not None
        assert created_by["id"] == test_employee.id
        assert created_by["fullname"] == test_employee.fullname
        assert created_by["email"] == test_employee.email

    def test_retrieve_proposal_approved_by_is_null_when_not_approved(self, api_client, superuser, test_employee):
        """Test that approved_by is null for pending proposals."""
        proposal = Proposal.objects.create(
            code="DX000012",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test complaint",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["approved_by"] is None

    def test_retrieve_proposal_approved_by_includes_employee_data(self, api_client, superuser, test_employee):
        """Test that approved_by includes employee nested data when proposal is approved."""
        # Create a second employee to act as approver
        from apps.hrm.models import Employee

        approver = Employee.objects.create(
            code="MV_PROP_002",
            fullname="Approver Employee",
            username="user_prop_002",
            email="prop002@example.com",
            attendance_code="99002",
            citizen_id="999000000002",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        proposal = Proposal.objects.create(
            code="DX000013",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test complaint",
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
            approved_by=approver,
        )

        url = reverse("hrm:proposal-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Verify approved_by contains employee nested data
        approved_by = data["data"]["approved_by"]
        assert approved_by is not None
        assert approved_by["id"] == approver.id
        assert approved_by["fullname"] == approver.fullname
        assert approved_by["email"] == approver.email

    def test_list_proposals_includes_created_by_and_approved_by(self, api_client, superuser, test_employee):
        """Test that list endpoint includes created_by and approved_by fields."""
        Proposal.objects.create(
            code="DX000014",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1

        result = data["data"]["results"][0]
        # Verify created_by is included with employee data
        assert result["created_by"] is not None
        assert result["created_by"]["id"] == test_employee.id
        # Verify approved_by is included (should be null for pending)
        assert "approved_by" in result
        assert result["approved_by"] is None


class TestTimesheetEntryComplaintProposalAPI:
    """Tests for Timesheet Entry Complaint Proposal API."""

    def test_list_timesheet_entry_complaint_proposals(self, api_client, superuser, test_employee):
        Proposal.objects.create(
            code="DX000001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return timesheet entry complaints, not paid leave
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.TIMESHEET_ENTRY_COMPLAINT

    def test_filter_by_status(self, api_client, superuser, test_employee):
        Proposal.objects.create(
            code="DX000003",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 2",
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
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

    def test_approve_complaint_success(self, api_client, superuser, test_employee):
        proposal = Proposal.objects.create(
            code="DX000005",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
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

    def test_approve_complaint_sets_approved_by_when_user_has_employee(self, api_client, test_employee):
        """Test that approved_by is set to the current user's employee when approving."""
        from rest_framework.test import APIClient

        # Create a user with an associated employee (the approver)
        approver_employee = Employee.objects.create(
            code="MV_APPROVER_001",
            fullname="Approver Employee",
            username="user_approver_001",
            email="approver001@example.com",
            attendance_code="99010",
            citizen_id="999000000010",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )
        approver_user = approver_employee.user
        # Grant superuser permission to bypass RoleBasedPermission checks
        approver_user.is_superuser = True
        approver_user.save()

        # Create a proposal
        proposal = Proposal.objects.create(
            code="DX000020",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        # Use a client authenticated as the approver_user (who has an employee)
        client = APIClient()
        client.force_authenticate(user=approver_user)

        url = reverse("hrm:proposal-timesheet-entry-complaint-approve", args=[proposal.id])
        data = {"approved_check_in_time": "08:00:00", "approved_check_out_time": "17:00:00", "note": "Approved"}

        response = client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True

        proposal.refresh_from_db()
        assert proposal.proposal_status == ProposalStatus.APPROVED
        # Verify approved_by is set to the approver's employee
        assert proposal.approved_by is not None
        assert proposal.approved_by.id == approver_employee.id

    def test_reject_complaint_success(self, api_client, superuser, test_employee):
        proposal = Proposal.objects.create(
            code="DX000006",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
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

    def test_reject_complaint_sets_approved_by_when_user_has_employee(self, api_client, test_employee):
        """Test that approved_by is set to the current user's employee when rejecting."""
        from rest_framework.test import APIClient

        # Create a user with an associated employee (the rejecter)
        rejecter_employee = Employee.objects.create(
            code="MV_REJECTER_001",
            fullname="Rejecter Employee",
            username="user_rejecter_001",
            email="rejecter001@example.com",
            attendance_code="99011",
            citizen_id="999000000011",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )
        rejecter_user = rejecter_employee.user
        # Grant superuser permission to bypass RoleBasedPermission checks
        rejecter_user.is_superuser = True
        rejecter_user.save()

        # Create a proposal
        proposal = Proposal.objects.create(
            code="DX000021",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        # Use a client authenticated as the rejecter_user (who has an employee)
        client = APIClient()
        client.force_authenticate(user=rejecter_user)

        url = reverse("hrm:proposal-timesheet-entry-complaint-reject", args=[proposal.id])
        data = {"note": "Rejected due to lack of evidence"}

        response = client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True

        proposal.refresh_from_db()
        assert proposal.proposal_status == ProposalStatus.REJECTED
        # Verify approved_by is set to the rejecter's employee
        assert proposal.approved_by is not None
        assert proposal.approved_by.id == rejecter_employee.id

    def test_reject_complaint_missing_note(self, api_client, superuser, test_employee):
        proposal = Proposal.objects.create(
            code="DX000007",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Wrong time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
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

    def test_list_paid_leave_proposals(self, api_client, superuser, test_employee):
        Proposal.objects.create(
            code="DX000008",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000009",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            created_by=test_employee,
        )

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

    def test_list_overtime_work_proposals(self, api_client, superuser, test_employee):
        Proposal.objects.create(
            code="DX000010",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000011",
            proposal_type=ProposalType.OVERTIME_WORK,
            note="Test 2",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"proposal_type": ProposalType.OVERTIME_WORK})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return overtime work proposals
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.OVERTIME_WORK


class TestTimesheetEntryComplaintWithTimesheetEntry:
    """Tests for Timesheet Entry Complaint proposals with linked timesheet entries."""

    @pytest.fixture
    def timesheet_entry(self, db, test_employee):
        """Create a test timesheet entry for the test employee."""
        from datetime import datetime
        from decimal import Decimal

        from apps.hrm.constants import TimesheetStatus
        from apps.hrm.models import TimeSheetEntry

        entry = TimeSheetEntry(
            employee=test_employee,
            date=date.today(),
            start_time=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0),
            end_time=datetime.now().replace(hour=17, minute=0, second=0, microsecond=0),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            status=TimesheetStatus.ON_TIME,
        )
        entry.save()
        return entry

    def test_list_complaint_proposals_includes_timesheet_entry_id(
        self, api_client, superuser, test_employee, timesheet_entry
    ):
        """Test that listing complaint proposals includes the linked timesheet entry ID."""
        from apps.hrm.models import ProposalTimeSheetEntry

        # Create complaint proposal
        proposal = Proposal.objects.create(
            code="DX_TS_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
            created_by=test_employee,
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(
            proposal=proposal,
            timesheet_entry=timesheet_entry,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1

        result = data["data"]["results"][0]
        assert "timesheet_entry_id" in result
        assert result["timesheet_entry_id"] == timesheet_entry.id

    def test_retrieve_complaint_proposal_includes_timesheet_entry_id(
        self, api_client, superuser, test_employee, timesheet_entry
    ):
        """Test that retrieving a complaint proposal includes the linked timesheet entry ID."""
        from apps.hrm.models import ProposalTimeSheetEntry

        # Create complaint proposal
        proposal = Proposal.objects.create(
            code="DX_TS_002",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
            created_by=test_employee,
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(
            proposal=proposal,
            timesheet_entry=timesheet_entry,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "timesheet_entry_id" in data["data"]
        assert data["data"]["timesheet_entry_id"] == timesheet_entry.id

    def test_complaint_proposal_without_linked_entry_returns_null(self, api_client, superuser, test_employee):
        """Test that a complaint proposal without a linked entry returns null for timesheet_entry_id."""
        proposal = Proposal.objects.create(
            code="DX_TS_003",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "timesheet_entry_id" in data["data"]
        assert data["data"]["timesheet_entry_id"] is None

    def test_approve_complaint_returns_timesheet_entry_id(self, api_client, superuser, test_employee, timesheet_entry):
        """Test that approving a complaint proposal returns the linked timesheet entry ID in response."""
        from apps.hrm.models import ProposalTimeSheetEntry

        # Create complaint proposal
        proposal = Proposal.objects.create(
            code="DX_TS_004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(
            proposal=proposal,
            timesheet_entry=timesheet_entry,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-approve", args=[proposal.id])
        response = api_client.post(
            url,
            {"approved_check_in_time": "08:00:00", "approved_check_out_time": "17:00:00"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "timesheet_entry_id" in data["data"]
        assert data["data"]["timesheet_entry_id"] == timesheet_entry.id

    def test_reject_complaint_returns_timesheet_entry_id(self, api_client, superuser, test_employee, timesheet_entry):
        """Test that rejecting a complaint proposal returns the linked timesheet entry ID in response."""
        from apps.hrm.models import ProposalTimeSheetEntry

        # Create complaint proposal
        proposal = Proposal.objects.create(
            code="DX_TS_005",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(
            proposal=proposal,
            timesheet_entry=timesheet_entry,
        )

        url = reverse("hrm:proposal-timesheet-entry-complaint-reject", args=[proposal.id])
        response = api_client.post(url, {"note": "Not enough evidence"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "timesheet_entry_id" in data["data"]
        assert data["data"]["timesheet_entry_id"] == timesheet_entry.id
