from datetime import date, time

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
    ProposalVerifier,
)

pytestmark = pytest.mark.django_db


def has_error_for_field(error_response: dict, field_name: str) -> bool:
    """Check if the error response contains an error for a specific field.

    Supports both flat dict format and DRF standardized error format:
    - Flat: {"field_name": ["error message"]}
    - Standardized: {"errors": [{"attr": "field_name", ...}], "type": "validation_error"}
    """
    if "errors" in error_response and isinstance(error_response["errors"], list):
        return any(err.get("attr") == field_name for err in error_response["errors"])
    return field_name in error_response


@pytest.fixture
def test_employee(db):
    """Create a test employee for proposal tests."""
    from apps.core.models import AdministrativeUnit, Province

    province = Province.objects.create(name="Test Province", code="TP_EXPORT")
    admin_unit = AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit",
        code="TAU_EXPORT",
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
            timesheet_entry_complaint_complaint_reason="Test 1",
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
            timesheet_entry_complaint_complaint_reason="Test 1",
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
            assert result["colored_proposal_status"]["value"] == ProposalStatus.PENDING

    def test_list_all_proposals_filter_by_type(self, api_client, superuser, test_employee):
        """Test filtering all proposals by proposal type."""
        Proposal.objects.create(
            code="DX000007",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Test 1",
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
            timesheet_entry_complaint_complaint_reason="Test complaint",
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
            timesheet_entry_complaint_complaint_reason="Test complaint",
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
            timesheet_entry_complaint_complaint_reason="Test complaint",
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
            timesheet_entry_complaint_complaint_reason="Test complaint",
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
            timesheet_entry_complaint_complaint_reason="Test 1",
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

    def test_filter_by_created_by(self, api_client, superuser, test_employee):
        """Test filtering proposals by created_by employee ID."""
        from apps.core.models import AdministrativeUnit, Province

        # Create another employee
        province = Province.objects.create(name="Other Province", code="OP")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province,
            name="Other Admin Unit",
            code="OAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        branch = Branch.objects.create(
            name="Other Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(name="Other Block", branch=branch, block_type=Block.BlockType.BUSINESS)
        department = Department.objects.create(
            name="Other Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
        )
        position = Position.objects.create(name="Manager")

        other_employee = Employee.objects.create(
            code="MV_PROP_OTHER",
            fullname="Other Employee",
            username="user_prop_other",
            email="prop_other@example.com",
            attendance_code="99099",
            citizen_id="999000000099",
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        Proposal.objects.create(
            code="DX_CB001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By test employee",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_CB002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By other employee",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"created_by": test_employee.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["created_by"]["id"] == test_employee.id

    def test_filter_by_created_by_department(self, api_client, superuser, test_employee):
        """Test filtering proposals by creator's department ID."""
        from apps.core.models import AdministrativeUnit, Province

        # Create another employee in a different department
        province = Province.objects.create(name="Dept Province", code="DP")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province,
            name="Dept Admin Unit",
            code="DAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        branch = Branch.objects.create(
            name="Dept Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(name="Dept Block", branch=branch, block_type=Block.BlockType.BUSINESS)
        other_department = Department.objects.create(
            name="Other Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
        )
        position = Position.objects.create(name="Developer2")

        other_employee = Employee.objects.create(
            code="MV_PROP_DEPT",
            fullname="Dept Employee",
            username="user_prop_dept",
            email="prop_dept@example.com",
            attendance_code="99098",
            citizen_id="999000000098",
            branch=branch,
            block=block,
            department=other_department,
            position=position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        Proposal.objects.create(
            code="DX_DEPT001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By test employee dept",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_DEPT002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By other dept employee",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"created_by_department": test_employee.department.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1

    def test_filter_by_created_by_branch(self, api_client, superuser, test_employee):
        """Test filtering proposals by creator's branch ID."""
        from apps.core.models import AdministrativeUnit, Province

        # Create another employee in a different branch
        province = Province.objects.create(name="Branch Province", code="BP")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province,
            name="Branch Admin Unit",
            code="BAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        other_branch = Branch.objects.create(
            name="Other Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(name="Branch Block", branch=other_branch, block_type=Block.BlockType.BUSINESS)
        department = Department.objects.create(
            name="Branch Dept", branch=other_branch, block=block, function=Department.DepartmentFunction.BUSINESS
        )
        position = Position.objects.create(name="Developer3")

        other_employee = Employee.objects.create(
            code="MV_PROP_BRANCH",
            fullname="Branch Employee",
            username="user_prop_branch",
            email="prop_branch@example.com",
            attendance_code="99097",
            citizen_id="999000000097",
            branch=other_branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        Proposal.objects.create(
            code="DX_BRANCH001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By test employee branch",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_BRANCH002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By other branch employee",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"created_by_branch": test_employee.branch.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1

    def test_filter_by_created_by_block(self, api_client, superuser, test_employee):
        """Test filtering proposals by creator's block ID."""
        from apps.core.models import AdministrativeUnit, Province

        # Create another employee in a different block
        province = Province.objects.create(name="Block Province", code="BLP")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province,
            name="Block Admin Unit",
            code="BLAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        branch = Branch.objects.create(
            name="Block Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        other_block = Block.objects.create(name="Other Block", branch=branch, block_type=Block.BlockType.SUPPORT)
        department = Department.objects.create(
            name="Block Dept", branch=branch, block=other_block, function=Department.DepartmentFunction.BUSINESS
        )
        position = Position.objects.create(name="Developer4")

        other_employee = Employee.objects.create(
            code="MV_PROP_BLOCK",
            fullname="Block Employee",
            username="user_prop_block",
            email="prop_block@example.com",
            attendance_code="99096",
            citizen_id="999000000096",
            branch=branch,
            block=other_block,
            department=department,
            position=position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        Proposal.objects.create(
            code="DX_BLOCK001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By test employee block",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_BLOCK002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By other block employee",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"created_by_block": test_employee.block.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1

    def test_filter_by_created_by_position(self, api_client, superuser, test_employee):
        """Test filtering proposals by creator's position ID."""
        from apps.core.models import AdministrativeUnit, Province

        # Create another employee with a different position
        province = Province.objects.create(name="Position Province", code="PP")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province,
            name="Position Admin Unit",
            code="PAU",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        branch = Branch.objects.create(
            name="Position Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(name="Position Block", branch=branch, block_type=Block.BlockType.BUSINESS)
        department = Department.objects.create(
            name="Position Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
        )
        other_position = Position.objects.create(name="Other Position")

        other_employee = Employee.objects.create(
            code="MV_PROP_POS",
            fullname="Position Employee",
            username="user_prop_pos",
            email="prop_pos@example.com",
            attendance_code="99095",
            citizen_id="999000000095",
            branch=branch,
            block=block,
            department=department,
            position=other_position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        Proposal.objects.create(
            code="DX_POS001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By test employee position",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_POS002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="By other position employee",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"created_by_position": test_employee.position.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1

    def test_filter_by_approved_by(self, api_client, superuser, test_employee):
        """Test filtering proposals by approved_by employee ID."""
        # Create an approver employee
        approver = Employee.objects.create(
            code="MV_PROP_APPROVER",
            fullname="Approver Employee",
            username="user_prop_approver",
            email="prop_approver@example.com",
            attendance_code="99094",
            citizen_id="999000000094",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        Proposal.objects.create(
            code="DX_APPR001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Approved by approver",
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
            approved_by=approver,
        )
        Proposal.objects.create(
            code="DX_APPR002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="No approver",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-list")
        response = api_client.get(url, {"approved_by": approver.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["approved_by"]["id"] == approver.id


class TestTimesheetEntryComplaintProposalAPI:
    """Tests for Timesheet Entry Complaint Proposal API."""

    def test_list_timesheet_entry_complaint_proposals(self, api_client, superuser, test_employee):
        Proposal.objects.create(
            code="DX000001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Test 1",
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
            timesheet_entry_complaint_complaint_reason="Test 1",
            proposal_status=ProposalStatus.PENDING,
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Test 2",
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
        assert data["data"]["results"][0]["colored_proposal_status"]["value"] == ProposalStatus.PENDING

    def test_approve_complaint_success(self, api_client, superuser, test_employee):
        proposal = Proposal.objects.create(
            code="DX000005",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Wrong time",
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
        assert str(proposal.timesheet_entry_complaint_approved_check_in_time) == "08:00:00"
        assert str(proposal.timesheet_entry_complaint_approved_check_out_time) == "17:00:00"
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
            timesheet_entry_complaint_complaint_reason="Wrong time",
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
            timesheet_entry_complaint_complaint_reason="Wrong time",
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
            timesheet_entry_complaint_complaint_reason="Wrong time",
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
            timesheet_entry_complaint_complaint_reason="Wrong time",
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

    def test_create_paid_leave_proposal_success(self, api_client, superuser, test_employee):
        """Test creating a paid leave proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-paid-leave-list")
        data = {
            "paid_leave_start_date": "2025-02-01",
            "paid_leave_end_date": "2025-02-05",
            "paid_leave_shift": "full_day",
            "paid_leave_reason": "Family vacation",
            "note": "Annual leave",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.PAID_LEAVE
        assert response_data["data"]["paid_leave_start_date"] == "2025-02-01"
        assert response_data["data"]["paid_leave_end_date"] == "2025-02-05"
        assert response_data["data"]["paid_leave_shift"] == "full_day"
        assert response_data["data"]["paid_leave_reason"] == "Family vacation"

    def test_create_paid_leave_proposal_invalid_date_range(self, api_client, superuser, test_employee):
        """Test creating a paid leave proposal with end date before start date."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-paid-leave-list")
        data = {
            "paid_leave_start_date": "2025-02-05",
            "paid_leave_end_date": "2025-02-01",
            "paid_leave_shift": "full_day",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "paid_leave_end_date")

    def test_list_paid_leave_proposals(self, api_client, superuser, test_employee):
        Proposal.objects.create(
            code="DX000008",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX000009",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Test 2",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-paid-leave-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return paid leave proposals
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.PAID_LEAVE


class TestUnpaidLeaveProposalAPI:
    """Tests for Unpaid Leave Proposal API."""

    def test_create_unpaid_leave_proposal_success(self, api_client, superuser, test_employee):
        """Test creating an unpaid leave proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-unpaid-leave-list")
        data = {
            "unpaid_leave_start_date": "2025-02-01",
            "unpaid_leave_end_date": "2025-02-05",
            "unpaid_leave_shift": "full_day",
            "unpaid_leave_reason": "Personal matters",
            "note": "Unpaid leave request",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.UNPAID_LEAVE
        assert response_data["data"]["unpaid_leave_start_date"] == "2025-02-01"
        assert response_data["data"]["unpaid_leave_end_date"] == "2025-02-05"
        assert response_data["data"]["unpaid_leave_shift"] == "full_day"
        assert response_data["data"]["unpaid_leave_reason"] == "Personal matters"

    def test_create_unpaid_leave_proposal_invalid_date_range(self, api_client, superuser, test_employee):
        """Test creating an unpaid leave proposal with end date before start date."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-unpaid-leave-list")
        data = {
            "unpaid_leave_start_date": "2025-02-05",
            "unpaid_leave_end_date": "2025-02-01",
            "unpaid_leave_shift": "full_day",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "unpaid_leave_end_date")

    def test_list_unpaid_leave_proposals(self, api_client, superuser, test_employee):
        """Test listing unpaid leave proposals."""
        Proposal.objects.create(
            code="DX_UL_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            note="Test 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_PL_001",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-unpaid-leave-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["proposal_type"] == ProposalType.UNPAID_LEAVE


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
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
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
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
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
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
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
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
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
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
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


class TestLateExemptionProposalAPI:
    """Tests for Late Exemption Proposal API."""

    def test_create_late_exemption_proposal_success(self, api_client, superuser, test_employee):
        """Test creating a late exemption proposal with valid data."""
        # Associate the superuser with the test_employee
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-late-exemption-list")
        data = {
            "late_exemption_start_date": "2025-02-01",
            "late_exemption_end_date": "2025-02-28",
            "late_exemption_minutes": 30,
            "note": "Need extra time in the morning",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.LATE_EXEMPTION
        assert response_data["data"]["late_exemption_start_date"] == "2025-02-01"
        assert response_data["data"]["late_exemption_end_date"] == "2025-02-28"
        assert response_data["data"]["late_exemption_minutes"] == 30

    def test_create_late_exemption_proposal_missing_fields(self, api_client, superuser, test_employee):
        """Test creating a late exemption proposal with missing required fields."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-late-exemption-list")
        data = {"note": "Missing required fields"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "late_exemption_start_date")
        assert has_error_for_field(response_data["error"], "late_exemption_end_date")
        assert has_error_for_field(response_data["error"], "late_exemption_minutes")

    def test_create_late_exemption_proposal_invalid_date_range(self, api_client, superuser, test_employee):
        """Test creating a late exemption proposal with end date before start date."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-late-exemption-list")
        data = {
            "late_exemption_start_date": "2025-02-28",
            "late_exemption_end_date": "2025-02-01",
            "late_exemption_minutes": 30,
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "late_exemption_end_date")

    def test_list_late_exemption_proposals(self, api_client, superuser, test_employee):
        """Test listing late exemption proposals only shows late exemption type."""
        # Create a late exemption proposal
        Proposal.objects.create(
            code="DX_LE_001",
            proposal_type=ProposalType.LATE_EXEMPTION,
            late_exemption_start_date=date(2025, 2, 1),
            late_exemption_end_date=date(2025, 2, 28),
            late_exemption_minutes=30,
            created_by=test_employee,
        )
        # Create other proposal types
        Proposal.objects.create(
            code="DX_PL_001",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-late-exemption-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["count"] == 1
        assert response_data["data"]["results"][0]["proposal_type"] == ProposalType.LATE_EXEMPTION


class TestOvertimeWorkProposalAPI:
    """Tests for Overtime Work Proposal API."""

    def test_create_overtime_work_proposal_success(self, api_client, superuser, test_employee):
        """Test creating an overtime work proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-overtime-work-list")
        data = {
            "entries": [
                {
                    "date": "2025-01-15",
                    "start_time": "18:00:00",
                    "end_time": "21:00:00",
                    "description": "Project deadline",
                }
            ],
            "note": "Overtime for project deadline",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.OVERTIME_WORK
        assert len(response_data["data"]["overtime_entries"]) == 1
        assert response_data["data"]["overtime_entries"][0]["date"] == "2025-01-15"
        assert response_data["data"]["overtime_entries"][0]["start_time"] == "18:00:00"
        assert response_data["data"]["overtime_entries"][0]["end_time"] == "21:00:00"

    def test_create_overtime_work_proposal_missing_entries(self, api_client, superuser, test_employee):
        """Test creating an overtime work proposal with missing entries."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-overtime-work-list")
        data = {"note": "Missing entries"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "entries")

    def test_create_overtime_work_proposal_invalid_time_range(self, api_client, superuser, test_employee):
        """Test creating an overtime work proposal with end time before start time."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-overtime-work-list")
        data = {
            "entries": [
                {
                    "date": "2025-01-15",
                    "start_time": "21:00:00",
                    "end_time": "18:00:00",
                }
            ],
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False

    def test_list_overtime_work_proposals(self, api_client, superuser, test_employee):
        """Test listing overtime work proposals only shows overtime work type."""
        from apps.hrm.models import ProposalOvertimeEntry

        proposal = Proposal.objects.create(
            code="DX_OT_001",
            proposal_type=ProposalType.OVERTIME_WORK,
            created_by=test_employee,
        )
        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 1, 15),
            start_time=time(18, 0),
            end_time=time(21, 0),
        )
        Proposal.objects.create(
            code="DX_PL_002",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-overtime-work-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["count"] == 1
        assert response_data["data"]["results"][0]["proposal_type"] == ProposalType.OVERTIME_WORK
        assert len(response_data["data"]["results"][0]["overtime_entries"]) == 1


class TestPostMaternityBenefitsProposalAPI:
    """Tests for Post-Maternity Benefits Proposal API."""

    def test_create_post_maternity_benefits_proposal_success(self, api_client, superuser, test_employee):
        """Test creating a post-maternity benefits proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-post-maternity-benefits-list")
        data = {
            "post_maternity_benefits_start_date": "2025-02-01",
            "post_maternity_benefits_end_date": "2025-03-01",
            "note": "Post-maternity work schedule request",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.POST_MATERNITY_BENEFITS
        assert response_data["data"]["post_maternity_benefits_start_date"] == "2025-02-01"
        assert response_data["data"]["post_maternity_benefits_end_date"] == "2025-03-01"

    def test_create_post_maternity_benefits_proposal_missing_fields(self, api_client, superuser, test_employee):
        """Test creating a post-maternity benefits proposal with missing required fields."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-post-maternity-benefits-list")
        data = {"note": "Missing required fields"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "post_maternity_benefits_start_date")
        assert has_error_for_field(response_data["error"], "post_maternity_benefits_end_date")

    def test_list_post_maternity_benefits_proposals(self, api_client, superuser, test_employee):
        """Test listing post-maternity benefits proposals only shows the correct type."""
        Proposal.objects.create(
            code="DX_PM_001",
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            post_maternity_benefits_start_date=date(2025, 2, 1),
            post_maternity_benefits_end_date=date(2025, 3, 1),
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_PL_003",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-post-maternity-benefits-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["count"] == 1
        assert response_data["data"]["results"][0]["proposal_type"] == ProposalType.POST_MATERNITY_BENEFITS


class TestJobTransferProposalAPI:
    """Tests for Job Transfer Proposal API."""

    def test_create_job_transfer_proposal_success(self, api_client, superuser, test_employee):
        """Test creating a job transfer proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-job-transfer-list")
        data = {
            "job_transfer_new_department_id": test_employee.department.id,
            "job_transfer_new_position_id": test_employee.position.id,
            "job_transfer_effective_date": "2025-02-01",
            "job_transfer_reason": "Career development",
            "note": "Transfer request to Marketing department",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.JOB_TRANSFER
        assert response_data["data"]["job_transfer_effective_date"] == "2025-02-01"
        assert response_data["data"]["job_transfer_reason"] == "Career development"
        # Verify nested department/position objects in response
        assert response_data["data"]["job_transfer_new_department"]["id"] == test_employee.department.id
        assert response_data["data"]["job_transfer_new_position"]["id"] == test_employee.position.id

    def test_create_job_transfer_proposal_missing_required_fields(self, api_client, superuser, test_employee):
        """Test creating a job transfer proposal with missing required fields."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-job-transfer-list")
        data = {
            "job_transfer_reason": "Career development",
            "note": "Missing required fields",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "job_transfer_new_department_id")
        assert has_error_for_field(response_data["error"], "job_transfer_new_position_id")

    def test_list_job_transfer_proposals(self, api_client, superuser, test_employee):
        """Test listing job transfer proposals only shows the correct type."""
        Proposal.objects.create(
            code="DX_JT_001",
            proposal_type=ProposalType.JOB_TRANSFER,
            job_transfer_new_department=test_employee.department,
            job_transfer_new_position=test_employee.position,
            job_transfer_effective_date=date(2025, 2, 1),
            note="Transfer to IT",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_PL_005",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-job-transfer-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["count"] == 1
        result = response_data["data"]["results"][0]
        assert result["proposal_type"] == ProposalType.JOB_TRANSFER
        # Verify nested serializer format in response
        assert result["job_transfer_new_department"]["id"] == test_employee.department.id
        assert result["job_transfer_new_position"]["id"] == test_employee.position.id


class TestAssetAllocationProposalAPI:
    """Tests for Asset Allocation Proposal API."""

    def test_create_asset_allocation_proposal_success(self, api_client, superuser, test_employee):
        """Test creating an asset allocation proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-asset-allocation-list")
        data = {
            "proposal_assets": [
                {
                    "name": "Laptop Dell XPS 15",
                    "unit_type": "piece",
                    "quantity": 1,
                    "note": "For development work",
                },
                {
                    "name": "Monitor 27 inch",
                    "unit_type": "piece",
                    "quantity": 2,
                },
            ],
            "note": "Equipment for new employee",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.ASSET_ALLOCATION
        assert len(response_data["data"]["assets"]) == 2
        assert response_data["data"]["assets"][0]["name"] == "Laptop Dell XPS 15"
        assert response_data["data"]["assets"][1]["name"] == "Monitor 27 inch"

    def test_list_asset_allocation_proposals(self, api_client, superuser, test_employee):
        """Test listing asset allocation proposals only shows the correct type."""
        from apps.hrm.models import ProposalAsset

        proposal = Proposal.objects.create(
            code="DX_AA_001",
            proposal_type=ProposalType.ASSET_ALLOCATION,
            note="Equipment request",
            created_by=test_employee,
        )
        ProposalAsset.objects.create(
            proposal=proposal,
            name="Laptop",
            unit_type="piece",
            quantity=1,
        )
        Proposal.objects.create(
            code="DX_PL_006",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-asset-allocation-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["count"] == 1
        assert response_data["data"]["results"][0]["proposal_type"] == ProposalType.ASSET_ALLOCATION
        assert len(response_data["data"]["results"][0]["assets"]) == 1

    def test_retrieve_asset_allocation_proposal_includes_assets(self, api_client, superuser, test_employee):
        """Test retrieving an asset allocation proposal includes the assets."""
        from apps.hrm.models import ProposalAsset

        proposal = Proposal.objects.create(
            code="DX_AA_002",
            proposal_type=ProposalType.ASSET_ALLOCATION,
            note="Equipment request",
            created_by=test_employee,
        )
        ProposalAsset.objects.create(
            proposal=proposal,
            name="Laptop Dell XPS",
            unit_type="piece",
            quantity=1,
        )
        ProposalAsset.objects.create(
            proposal=proposal,
            name="Mouse",
            unit_type="piece",
            quantity=2,
        )

        url = reverse("hrm:proposal-asset-allocation-detail", args=[proposal.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert len(response_data["data"]["assets"]) == 2


class TestMaternityLeaveProposalAPI:
    """Tests for Maternity Leave Proposal API."""

    def test_create_maternity_leave_proposal_success(self, api_client, superuser, test_employee):
        """Test creating a maternity leave proposal with valid data."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-maternity-leave-list")
        data = {
            "maternity_leave_start_date": "2025-02-01",
            "maternity_leave_end_date": "2025-08-01",
            "maternity_leave_estimated_due_date": "2025-03-15",
            "note": "Maternity leave request",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["proposal_type"] == ProposalType.MATERNITY_LEAVE
        assert response_data["data"]["maternity_leave_start_date"] == "2025-02-01"
        assert response_data["data"]["maternity_leave_end_date"] == "2025-08-01"
        assert response_data["data"]["maternity_leave_estimated_due_date"] == "2025-03-15"

    def test_create_maternity_leave_proposal_invalid_date_range(self, api_client, superuser, test_employee):
        """Test creating a maternity leave proposal with end date before start date."""
        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-maternity-leave-list")
        data = {
            "maternity_leave_start_date": "2025-08-01",
            "maternity_leave_end_date": "2025-02-01",
            "note": "Invalid date range",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert has_error_for_field(response_data["error"], "maternity_leave_end_date")

    def test_create_maternity_leave_proposal_with_replacement_employee(self, api_client, superuser, test_employee):
        """Test creating a maternity leave proposal with a replacement employee."""
        superuser.employee = test_employee
        superuser.save()

        # Create a replacement employee
        replacement_employee = Employee.objects.create(
            code="MV_REPL_001",
            fullname="Replacement Employee",
            username="user_repl_001",
            email="repl001@example.com",
            attendance_code="99099",
            citizen_id="999000000099",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        url = reverse("hrm:proposal-maternity-leave-list")
        data = {
            "maternity_leave_start_date": "2025-02-01",
            "maternity_leave_end_date": "2025-08-01",
            "maternity_leave_replacement_employee_id": replacement_employee.id,
            "note": "Maternity leave with replacement",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["maternity_leave_replacement_employee"]["id"] == replacement_employee.id

    def test_list_maternity_leave_proposals(self, api_client, superuser, test_employee):
        """Test listing maternity leave proposals only shows the correct type."""
        Proposal.objects.create(
            code="DX_ML_001",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            maternity_leave_start_date=date(2025, 2, 1),
            maternity_leave_end_date=date(2025, 8, 1),
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_PL_007",
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-maternity-leave-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["count"] == 1
        assert response_data["data"]["results"][0]["proposal_type"] == ProposalType.MATERNITY_LEAVE


class TestProposalExportXLSX:
    """Tests for Proposal XLSX export functionality."""

    def test_export_serializer_fields(self):
        """Test that export serializer includes correct base fields."""
        from apps.hrm.api.serializers.proposal import ProposalExportXLSXSerializer

        serializer = ProposalExportXLSXSerializer()
        field_names = list(serializer.fields.keys())

        # Check base fields are present
        assert "id" in field_names
        assert "code" in field_names
        assert "proposal_date" in field_names
        assert "proposal_type" in field_names
        assert "proposal_status" in field_names
        assert "note" in field_names
        assert "created_by_code" in field_names
        assert "created_by_name" in field_names
        assert "approved_by_code" in field_names
        assert "approved_by_name" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names

    def test_late_exemption_export_serializer_fields(self):
        """Test that late exemption export serializer includes type-specific fields."""
        from apps.hrm.api.serializers.proposal import ProposalLateExemptionExportXLSXSerializer

        serializer = ProposalLateExemptionExportXLSXSerializer()
        field_names = list(serializer.fields.keys())

        # Check base fields are present
        assert "id" in field_names
        assert "code" in field_names

        # Check type-specific fields
        assert "late_exemption_start_date" in field_names
        assert "late_exemption_end_date" in field_names
        assert "late_exemption_minutes" in field_names

    def test_paid_leave_export_serializer_fields(self):
        """Test that paid leave export serializer includes type-specific fields."""
        from apps.hrm.api.serializers.proposal import ProposalPaidLeaveExportXLSXSerializer

        serializer = ProposalPaidLeaveExportXLSXSerializer()
        field_names = list(serializer.fields.keys())

        # Check base fields are present
        assert "id" in field_names
        assert "code" in field_names

        # Check type-specific fields
        assert "paid_leave_start_date" in field_names
        assert "paid_leave_end_date" in field_names
        assert "paid_leave_shift" in field_names
        assert "paid_leave_reason" in field_names

    def test_job_transfer_export_serializer_fields(self):
        """Test that job transfer export serializer includes type-specific fields."""
        from apps.hrm.api.serializers.proposal import ProposalJobTransferExportXLSXSerializer

        serializer = ProposalJobTransferExportXLSXSerializer()
        field_names = list(serializer.fields.keys())

        # Check base fields are present
        assert "id" in field_names
        assert "code" in field_names

        # Check type-specific fields
        assert "new_branch_name" in field_names
        assert "new_block_name" in field_names
        assert "new_department_name" in field_names
        assert "new_position_name" in field_names
        assert "job_transfer_effective_date" in field_names
        assert "job_transfer_reason" in field_names

    def test_maternity_leave_export_serializer_fields(self):
        """Test that maternity leave export serializer includes type-specific fields."""
        from apps.hrm.api.serializers.proposal import ProposalMaternityLeaveExportXLSXSerializer

        serializer = ProposalMaternityLeaveExportXLSXSerializer()
        field_names = list(serializer.fields.keys())

        # Check base fields are present
        assert "id" in field_names
        assert "code" in field_names

        # Check type-specific fields
        assert "maternity_leave_start_date" in field_names
        assert "maternity_leave_end_date" in field_names
        assert "maternity_leave_estimated_due_date" in field_names
        assert "replacement_employee_code" in field_names
        assert "replacement_employee_name" in field_names

    def test_viewset_uses_export_serializer_for_export_action(self):
        """Test that ViewSet uses correct export serializer for export action."""
        from apps.hrm.api.serializers.proposal import (
            ProposalLateExemptionExportXLSXSerializer,
            ProposalPaidLeaveExportXLSXSerializer,
        )
        from apps.hrm.api.views.proposal import (
            ProposalLateExemptionViewSet,
            ProposalPaidLeaveViewSet,
        )

        # Test late exemption viewset
        late_exemption_viewset = ProposalLateExemptionViewSet()
        late_exemption_viewset.action = "export"
        assert late_exemption_viewset.get_serializer_class() == ProposalLateExemptionExportXLSXSerializer

        # Test paid leave viewset
        paid_leave_viewset = ProposalPaidLeaveViewSet()
        paid_leave_viewset.action = "export"
        assert paid_leave_viewset.get_serializer_class() == ProposalPaidLeaveExportXLSXSerializer

        # Test that list action uses default serializer
        late_exemption_viewset.action = "list"
        assert late_exemption_viewset.get_serializer_class() != ProposalLateExemptionExportXLSXSerializer

    def test_export_endpoint_returns_xlsx(self, api_client, superuser, test_employee):
        """Test that export endpoint returns XLSX file."""
        # Create a proposal
        Proposal.objects.create(
            code="DX_EXPORT_001",
            proposal_type=ProposalType.PAID_LEAVE,
            paid_leave_start_date=date(2025, 2, 1),
            paid_leave_end_date=date(2025, 2, 5),
            paid_leave_reason="Vacation",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-paid-leave-export")
        response = api_client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]

    def test_export_filtered_proposals(self, api_client, superuser, test_employee):
        """Test exporting filtered proposals."""
        # Create proposals with different statuses
        Proposal.objects.create(
            code="DX_EXPORT_002",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            paid_leave_start_date=date(2025, 2, 1),
            paid_leave_end_date=date(2025, 2, 5),
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_EXPORT_003",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=date(2025, 3, 1),
            paid_leave_end_date=date(2025, 3, 5),
            created_by=test_employee,
        )

        # Export with filter
        url = reverse("hrm:proposal-paid-leave-export")
        response = api_client.get(url, {"delivery": "direct", "proposal_status": ProposalStatus.PENDING})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT


class TestMyProposalsAPI:
    """Tests for the my_proposals endpoint (me/proposals/)."""

    def test_my_proposals_returns_only_user_proposals(self, api_client, superuser, test_employee):
        """Test that my_proposals returns only proposals created by current user."""
        # Link the superuser to the test employee
        superuser.employee = test_employee
        superuser.save()

        # Create proposals by the test employee
        Proposal.objects.create(
            code="DX_MY001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="My proposal 1",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_MY002",
            proposal_type=ProposalType.OVERTIME_WORK,
            note="My proposal 2",
            created_by=test_employee,
        )

        # Create another employee and their proposals
        other_employee = Employee.objects.create(
            code="MV_OTHER001",
            fullname="Other Employee",
            username="other_user_001",
            email="other001@example.com",
            attendance_code="88001",
            citizen_id="888000000001",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )
        Proposal.objects.create(
            code="DX_OTHER001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Other proposal",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-my-proposals")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
        for result in data["data"]["results"]:
            assert result["created_by"]["id"] == test_employee.id

    def test_my_proposals_supports_filtering(self, api_client, superuser, test_employee):
        """Test that my_proposals supports existing filters."""
        superuser.employee = test_employee
        superuser.save()

        Proposal.objects.create(
            code="DX_MYFILTER001",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            note="Pending proposal",
            created_by=test_employee,
        )
        Proposal.objects.create(
            code="DX_MYFILTER002",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            note="Approved proposal",
            created_by=test_employee,
        )

        url = reverse("hrm:proposal-my-proposals")
        response = api_client.get(url, {"proposal_status": ProposalStatus.PENDING})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["colored_proposal_status"]["value"] == ProposalStatus.PENDING

    def test_my_proposals_user_without_employee_profile(self, api_client, superuser):
        """Test that my_proposals returns error for user without employee profile."""
        # Ensure superuser has no employee profile
        if hasattr(superuser, "employee"):
            superuser.employee = None
            superuser.save()

        url = reverse("hrm:proposal-my-proposals")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False

    def test_my_proposals_returns_empty_when_no_proposals(self, api_client, superuser, test_employee):
        """Test that my_proposals returns empty list when user has no proposals."""
        superuser.employee = test_employee
        superuser.save()

        # Create proposal by another employee
        other_employee = Employee.objects.create(
            code="MV_OTHER002",
            fullname="Other Employee 2",
            username="other_user_002",
            email="other002@example.com",
            attendance_code="88002",
            citizen_id="888000000002",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )
        Proposal.objects.create(
            code="DX_NOTMINE001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Not my proposal",
            created_by=other_employee,
        )

        url = reverse("hrm:proposal-my-proposals")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 0
        assert data["data"]["results"] == []


class TestProposalsNeedApprovalAPI:
    """Tests for the proposals_need_approval endpoint (me/proposals/need-approval/).

    This endpoint returns proposals where the current user is assigned as a ProposalVerifier.
    Only department leaders can access this endpoint.
    """

    def test_need_approval_returns_proposals_where_user_is_verifier(self, api_client, superuser, test_employee):
        """Test that need_approval returns proposals where user is assigned as verifier."""
        # Set up the test employee as department leader
        department = test_employee.department
        department.leader = test_employee
        department.save()

        superuser.employee = test_employee
        superuser.save()

        # Create another employee in the same department
        subordinate = Employee.objects.create(
            code="MV_SUB001",
            fullname="Subordinate Employee",
            username="subordinate_001",
            email="subordinate001@example.com",
            attendance_code="77001",
            citizen_id="777000000001",
            branch=test_employee.branch,
            block=test_employee.block,
            department=department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        # Create proposal by subordinate
        proposal1 = Proposal.objects.create(
            code="DX_APPROVAL001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Subordinate proposal",
            created_by=subordinate,
        )
        # Add test_employee as verifier
        ProposalVerifier.objects.create(proposal=proposal1, employee=test_employee)

        # Create another proposal without verifier assignment
        Proposal.objects.create(
            code="DX_APPROVAL002",
            proposal_type=ProposalType.OVERTIME_WORK,
            note="No verifier proposal",
            created_by=subordinate,
        )

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only return proposal where user is verifier
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["code"] == "DX_APPROVAL001"

    def test_need_approval_returns_error_for_non_leader(self, api_client, superuser, test_employee):
        """Test that need_approval returns 400 error for non-leader user."""
        # Ensure department has no leader
        department = test_employee.department
        department.leader = None
        department.save()

        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False

    def test_need_approval_returns_error_when_different_leader(self, api_client, superuser, test_employee):
        """Test that need_approval returns 400 when department has a different leader."""
        # Create another employee as department leader
        other_leader = Employee.objects.create(
            code="MV_LEADER001",
            fullname="Other Leader",
            username="other_leader_001",
            email="otherleader001@example.com",
            attendance_code="88001",
            citizen_id="888000000001",
            branch=test_employee.branch,
            block=test_employee.block,
            department=test_employee.department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        department = test_employee.department
        department.leader = other_leader
        department.save()

        superuser.employee = test_employee
        superuser.save()

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False

    def test_need_approval_user_without_employee_profile(self, api_client, superuser):
        """Test that need_approval returns error for user without employee profile."""
        # Ensure superuser has no employee profile
        if hasattr(superuser, "employee"):
            superuser.employee = None
            superuser.save()

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False

    def test_need_approval_supports_filtering(self, api_client, superuser, test_employee):
        """Test that need_approval supports existing filters."""
        # Set up the test employee as department leader
        department = test_employee.department
        department.leader = test_employee
        department.save()

        superuser.employee = test_employee
        superuser.save()

        # Create subordinate
        subordinate = Employee.objects.create(
            code="MV_SUB002",
            fullname="Subordinate Employee 2",
            username="subordinate_002",
            email="subordinate002@example.com",
            attendance_code="77002",
            citizen_id="777000000002",
            branch=test_employee.branch,
            block=test_employee.block,
            department=department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        # Create proposals with different statuses
        proposal1 = Proposal.objects.create(
            code="DX_FILTER_APPROVAL001",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            note="Pending proposal",
            created_by=subordinate,
        )
        ProposalVerifier.objects.create(proposal=proposal1, employee=test_employee)

        proposal2 = Proposal.objects.create(
            code="DX_FILTER_APPROVAL002",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            note="Approved proposal",
            created_by=subordinate,
        )
        ProposalVerifier.objects.create(proposal=proposal2, employee=test_employee)

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url, {"proposal_status": ProposalStatus.PENDING})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["colored_proposal_status"]["value"] == ProposalStatus.PENDING

    def test_need_approval_only_includes_proposals_where_user_is_verifier(self, api_client, superuser, test_employee):
        """Test that need_approval only includes proposals where user is assigned as verifier."""
        # Set up the test employee as department leader
        department = test_employee.department
        department.leader = test_employee
        department.save()

        superuser.employee = test_employee
        superuser.save()

        # Create subordinate in same department
        subordinate = Employee.objects.create(
            code="MV_SUB003",
            fullname="Subordinate Employee 3",
            username="subordinate_003",
            email="subordinate003@example.com",
            attendance_code="77003",
            citizen_id="777000000003",
            branch=test_employee.branch,
            block=test_employee.block,
            department=department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        # Create another leader
        other_leader = Employee.objects.create(
            code="MV_OTHER_LEADER",
            fullname="Other Leader",
            username="other_leader",
            email="otherleader@example.com",
            attendance_code="66001",
            citizen_id="666000000001",
            branch=test_employee.branch,
            block=test_employee.block,
            department=department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        # Create proposal where test_employee is verifier
        proposal1 = Proposal.objects.create(
            code="DX_VERIFIER001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Assigned to test_employee",
            created_by=subordinate,
        )
        ProposalVerifier.objects.create(proposal=proposal1, employee=test_employee)

        # Create proposal where other_leader is verifier (not test_employee)
        proposal2 = Proposal.objects.create(
            code="DX_VERIFIER002",
            proposal_type=ProposalType.PAID_LEAVE,
            note="Assigned to other leader",
            created_by=subordinate,
        )
        ProposalVerifier.objects.create(proposal=proposal2, employee=other_leader)

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should only include proposal where test_employee is verifier
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["code"] == "DX_VERIFIER001"

    def test_need_approval_returns_empty_when_no_verifier_assignments(self, api_client, superuser, test_employee):
        """Test that need_approval returns empty list when user has no verifier assignments."""
        # Set up the test employee as department leader
        department = test_employee.department
        department.leader = test_employee
        department.save()

        superuser.employee = test_employee
        superuser.save()

        # Create subordinate
        subordinate = Employee.objects.create(
            code="MV_SUB004",
            fullname="Subordinate Employee 4",
            username="subordinate_004",
            email="subordinate004@example.com",
            attendance_code="77004",
            citizen_id="777000000004",
            branch=test_employee.branch,
            block=test_employee.block,
            department=department,
            position=test_employee.position,
            start_date=date(2020, 1, 1),
            status=Employee.Status.ACTIVE,
        )

        # Create proposal without any verifier
        Proposal.objects.create(
            code="DX_NO_VERIFIER001",
            proposal_type=ProposalType.PAID_LEAVE,
            note="No verifier assigned",
            created_by=subordinate,
        )

        url = reverse("hrm:proposal-proposals-need-approval")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 0
        assert data["data"]["results"] == []
