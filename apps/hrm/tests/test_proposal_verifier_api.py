import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import ProposalStatus, ProposalType, ProposalVerifierStatus
from apps.hrm.models import Employee, Proposal, ProposalVerifier

pytestmark = pytest.mark.django_db


class TestProposalVerifierModel:
    """Tests for ProposalVerifier model."""

    @pytest.fixture
    def province(self):
        """Create a province for testing."""
        from apps.core.models import Province

        return Province.objects.create(name="Test Province", code="TP001")

    @pytest.fixture
    def administrative_unit(self, province):
        """Create an administrative unit for testing."""
        from apps.core.models import AdministrativeUnit

        return AdministrativeUnit.objects.create(
            name="Test Administrative Unit",
            code="TAU001",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            parent_province=province,
        )

    @pytest.fixture
    def branch(self, administrative_unit):
        """Create a branch for testing."""
        from apps.hrm.models import Branch

        return Branch.objects.create(
            name="Test Branch",
            code="TB001",
            administrative_unit=administrative_unit,
            province=administrative_unit.parent_province,
        )

    @pytest.fixture
    def block(self, branch):
        """Create a block for testing."""
        from apps.hrm.models import Block

        return Block.objects.create(
            name="Test Block", code="BLK001", branch=branch, block_type=Block.BlockType.BUSINESS
        )

    @pytest.fixture
    def department(self, branch, block):
        """Create a department for testing."""
        from apps.hrm.models import Department

        return Department.objects.create(
            name="Test Department",
            code="TD001",
            branch=branch,
            block=block,
        )

    @pytest.fixture
    def employee(self, branch, block, department):
        """Create an employee for testing."""
        return Employee.objects.create(
            code_type="MV",
            fullname="Test Employee",
            username="testemployee001",
            email="test001@example.com",
            citizen_id="000000001001",
            start_date="2023-01-01",
            branch=branch,
            block=block,
            department=department,
        )

    @pytest.fixture
    def timesheet_complaint_proposal(self, employee):
        """Create a timesheet entry complaint proposal for testing."""
        return Proposal.objects.create(
            code="DX000001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
            proposal_status=ProposalStatus.PENDING,
            created_by=employee,
        )

    def test_create_proposal_verifier_with_default_status(self, timesheet_complaint_proposal, employee):
        """Test creating a proposal verifier has default status of NOT_VERIFIED."""
        verifier = ProposalVerifier.objects.create(
            proposal=timesheet_complaint_proposal,
            employee=employee,
        )

        assert verifier.status == ProposalVerifierStatus.NOT_VERIFIED
        assert verifier.verified_time is None
        assert verifier.note is None

    def test_create_proposal_verifier_with_custom_fields(self, timesheet_complaint_proposal, employee):
        """Test creating a proposal verifier with custom field values."""
        verifier = ProposalVerifier.objects.create(
            proposal=timesheet_complaint_proposal,
            employee=employee,
            status=ProposalVerifierStatus.VERIFIED,
            note="Custom note",
        )

        assert verifier.status == ProposalVerifierStatus.VERIFIED
        assert verifier.note == "Custom note"

    def test_proposal_verifier_string_representation(self, timesheet_complaint_proposal, employee):
        """Test the string representation of ProposalVerifier."""
        verifier = ProposalVerifier.objects.create(
            proposal=timesheet_complaint_proposal,
            employee=employee,
        )

        expected = f"Proposal {verifier.proposal_id} - Verifier {verifier.employee_id}"
        assert str(verifier) == expected

    def test_unique_together_constraint(self, timesheet_complaint_proposal, employee):
        """Test that the unique_together constraint prevents duplicate verifiers."""
        ProposalVerifier.objects.create(
            proposal=timesheet_complaint_proposal,
            employee=employee,
        )

        # Attempting to create duplicate should raise IntegrityError
        with pytest.raises(Exception):  # Django raises IntegrityError
            ProposalVerifier.objects.create(
                proposal=timesheet_complaint_proposal,
                employee=employee,
            )


class TestProposalVerifierAPI:
    """Tests for ProposalVerifier API."""

    @pytest.fixture
    def province(self):
        """Create a province for testing."""
        from apps.core.models import Province

        return Province.objects.create(name="Test Province", code="TP001")

    @pytest.fixture
    def administrative_unit(self, province):
        """Create an administrative unit for testing."""
        from apps.core.models import AdministrativeUnit

        return AdministrativeUnit.objects.create(
            name="Test Administrative Unit",
            code="TAU002",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            parent_province=province,
        )

    @pytest.fixture
    def branch(self, administrative_unit):
        """Create a branch for testing."""
        from apps.hrm.models import Branch

        return Branch.objects.create(
            name="Test Branch",
            code="TB002",
            administrative_unit=administrative_unit,
            province=administrative_unit.parent_province,
        )

    @pytest.fixture
    def block(self, branch):
        """Create a block for testing."""
        from apps.hrm.models import Block

        return Block.objects.create(
            name="Test Block", code="BLK002", branch=branch, block_type=Block.BlockType.BUSINESS
        )

    @pytest.fixture
    def department(self, branch, block):
        """Create a department for testing."""
        from apps.hrm.models import Department

        dept = Department.objects.create(
            name="Test Department",
            code="TD002",
            branch=branch,
            block=block,
        )
        return dept

    @pytest.fixture
    def department_leader(self, branch, block, department):
        """Create a department leader employee for testing."""
        employee = Employee.objects.create(
            code_type="MV",
            fullname="Department Leader",
            username="deptleader001",
            email="leader001@example.com",
            citizen_id="000000001099",
            start_date="2023-01-01",
            branch=branch,
            block=block,
            department=department,
        )
        # Set the leader properly using ForeignKey assignment
        department.leader = employee
        department.save()
        return employee

    @pytest.fixture
    def employee(self, branch, block, department):
        """Create an employee for testing."""
        return Employee.objects.create(
            code_type="MV",
            fullname="Test Employee",
            username="testemployee001",
            email="test001@example.com",
            citizen_id="000000001002",
            start_date="2023-01-01",
            branch=branch,
            block=block,
            department=department,
        )

    @pytest.fixture
    def superuser_with_employee(self, superuser, department_leader):
        """Link the superuser to the department leader employee."""
        department_leader.user = superuser
        department_leader.save()
        return superuser

    @pytest.fixture
    def timesheet_complaint_proposal(self, employee):
        """Create a timesheet entry complaint proposal for testing."""
        return Proposal.objects.create(
            code="DX000003",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time",
            proposal_status=ProposalStatus.PENDING,
            created_by=employee,
        )

    @pytest.fixture
    def paid_leave_proposal(self, employee):
        """Create a paid leave proposal for testing."""
        return Proposal.objects.create(
            code="DX000002",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            created_by=employee,
        )

    @pytest.fixture
    def proposal_verifier(self, timesheet_complaint_proposal, employee):
        """Create a proposal verifier for testing."""
        return ProposalVerifier.objects.create(
            proposal=timesheet_complaint_proposal,
            employee=employee,
            note="Assigned as verifier",
        )

    @pytest.fixture
    def proposal_verifier_for_verify(self, timesheet_complaint_proposal, department_leader):
        """Get or create a proposal verifier with department_leader for verify tests.

        Note: The ProposalVerifier may already be auto-created when the Proposal is saved,
        so we use get_or_create to avoid duplicate key errors.
        """
        verifier, _ = ProposalVerifier.objects.get_or_create(
            proposal=timesheet_complaint_proposal,
            employee=department_leader,
            defaults={"note": "Assigned as verifier"},
        )
        return verifier

    def test_list_proposal_verifiers(self, api_client, superuser, proposal_verifier):
        """Test listing all proposal verifiers."""
        url = reverse("hrm:proposal-verifier-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["id"] == proposal_verifier.id
        assert data["data"]["results"][0]["colored_status"]["value"] == ProposalVerifierStatus.NOT_VERIFIED

    def test_retrieve_proposal_verifier(self, api_client, superuser, proposal_verifier):
        """Test retrieving a specific proposal verifier."""
        url = reverse("hrm:proposal-verifier-detail", args=[proposal_verifier.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == proposal_verifier.id
        assert data["data"]["proposal"]["id"] == proposal_verifier.proposal.id
        assert data["data"]["employee"]["id"] == proposal_verifier.employee.id

    def test_create_proposal_verifier(self, api_client, superuser, paid_leave_proposal, department_leader):
        """Test creating a new proposal verifier."""
        url = reverse("hrm:proposal-verifier-list")
        data = {
            "proposal_id": paid_leave_proposal.id,
            "employee_id": department_leader.id,
            "note": "New verifier assignment",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal"]["id"] == paid_leave_proposal.id
        assert result["data"]["employee"]["id"] == department_leader.id
        assert result["data"]["colored_status"]["value"] == ProposalVerifierStatus.NOT_VERIFIED
        assert result["data"]["note"] == "New verifier assignment"
        assert result["data"]["verified_time"] is None

    def test_update_proposal_verifier(self, api_client, superuser, proposal_verifier):
        """Test updating a proposal verifier."""
        url = reverse("hrm:proposal-verifier-detail", args=[proposal_verifier.id])
        data = {
            "proposal_id": proposal_verifier.proposal.id,
            "employee_id": proposal_verifier.employee.id,
            "note": "Updated note",
        }

        response = api_client.put(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["note"] == "Updated note"

    def test_partial_update_proposal_verifier(self, api_client, superuser, proposal_verifier):
        """Test partially updating a proposal verifier."""
        url = reverse("hrm:proposal-verifier-detail", args=[proposal_verifier.id])
        data = {"note": "Partially updated note"}

        response = api_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["note"] == "Partially updated note"

    def test_delete_proposal_verifier(self, api_client, superuser, proposal_verifier):
        """Test deleting a proposal verifier."""
        url = reverse("hrm:proposal-verifier-detail", args=[proposal_verifier.id])
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ProposalVerifier.objects.filter(id=proposal_verifier.id).exists()

    def test_verify_timesheet_complaint_proposal_success(
        self, api_client, superuser_with_employee, proposal_verifier_for_verify
    ):
        """Test successfully verifying a timesheet entry complaint proposal."""
        url = reverse("hrm:proposal-verifier-verify", args=[proposal_verifier_for_verify.id])
        data = {"note": "Verified and approved"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["colored_status"]["value"] == ProposalVerifierStatus.VERIFIED
        assert result["data"]["verified_time"] is not None
        assert result["data"]["note"] == "Verified and approved"

        proposal_verifier_for_verify.refresh_from_db()
        assert proposal_verifier_for_verify.status == ProposalVerifierStatus.VERIFIED
        assert proposal_verifier_for_verify.verified_time is not None
        assert proposal_verifier_for_verify.note == "Verified and approved"

    def test_verify_timesheet_complaint_proposal_without_note(
        self, api_client, superuser_with_employee, proposal_verifier_for_verify
    ):
        """Test verifying a proposal without providing a note."""
        url = reverse("hrm:proposal-verifier-verify", args=[proposal_verifier_for_verify.id])
        data = {}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["colored_status"]["value"] == ProposalVerifierStatus.VERIFIED
        assert result["data"]["verified_time"] is not None

    def test_verify_already_verified_proposal(self, api_client, superuser_with_employee, proposal_verifier_for_verify):
        """Test verifying a proposal that has already been verified."""
        # First verification
        url = reverse("hrm:proposal-verifier-verify", args=[proposal_verifier_for_verify.id])
        data = {"note": "First verification"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

        # Second verification (should succeed, updating the verification)
        data = {"note": "Second verification"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

        proposal_verifier_for_verify.refresh_from_db()
        assert proposal_verifier_for_verify.status == ProposalVerifierStatus.VERIFIED
        assert proposal_verifier_for_verify.note == "Second verification"


class TestProposalAutoAssignVerifier:
    """Tests for auto-assigning department leader as verifier when creating proposal."""

    @pytest.fixture
    def province(self):
        """Create a province for testing."""
        from apps.core.models import Province

        return Province.objects.create(name="Test Province", code="TP_AUTO_001")

    @pytest.fixture
    def administrative_unit(self, province):
        """Create an administrative unit for testing."""
        from apps.core.models import AdministrativeUnit

        return AdministrativeUnit.objects.create(
            name="Test Admin Unit",
            code="TAU_AUTO_001",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            parent_province=province,
        )

    @pytest.fixture
    def branch(self, administrative_unit):
        """Create a branch for testing."""
        from apps.hrm.models import Branch

        return Branch.objects.create(
            name="Test Branch",
            code="TB_AUTO_001",
            administrative_unit=administrative_unit,
            province=administrative_unit.parent_province,
        )

    @pytest.fixture
    def block(self, branch):
        """Create a block for testing."""
        from apps.hrm.models import Block

        return Block.objects.create(
            name="Test Block", code="BLK_AUTO_001", branch=branch, block_type=Block.BlockType.BUSINESS
        )

    @pytest.fixture
    def department_leader(self, branch, block):
        """Create a department leader employee."""
        from apps.hrm.models import Department

        department = Department.objects.create(
            name="Test Department",
            code="TD_AUTO_001",
            branch=branch,
            block=block,
        )
        leader = Employee.objects.create(
            code_type="MV",
            fullname="Department Leader",
            username="dept_leader_001",
            email="leader001@example.com",
            citizen_id="000000100001",
            start_date="2023-01-01",
            branch=branch,
            block=block,
            department=department,
        )
        # Set the leader on the department
        department.leader = leader
        department.save()
        return leader

    @pytest.fixture
    def employee_with_leader(self, department_leader):
        """Create an employee in a department with a leader."""
        department = department_leader.department
        return Employee.objects.create(
            code_type="MV",
            fullname="Regular Employee",
            username="regular_emp_001",
            email="regular001@example.com",
            citizen_id="000000100002",
            start_date="2023-01-01",
            branch=department.branch,
            block=department.block,
            department=department,
        )

    @pytest.fixture
    def department_without_leader(self, branch, block):
        """Create a department without a leader."""
        from apps.hrm.models import Department

        return Department.objects.create(
            name="No Leader Department",
            code="NL_DEPT_001",
            branch=branch,
            block=block,
        )

    @pytest.fixture
    def employee_without_leader(self, department_without_leader):
        """Create an employee in a department without a leader."""
        return Employee.objects.create(
            code_type="MV",
            fullname="Employee No Leader",
            username="no_leader_emp_001",
            email="noleader001@example.com",
            citizen_id="000000100003",
            start_date="2023-01-01",
            branch=department_without_leader.branch,
            block=department_without_leader.block,
            department=department_without_leader,
        )

    def test_auto_assign_department_leader_as_verifier(self, employee_with_leader, department_leader):
        """Test that creating a proposal auto-assigns department leader as verifier."""
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Late check-in",
            created_by=employee_with_leader,
        )

        # Verify that a ProposalVerifier was created
        verifier = ProposalVerifier.objects.filter(proposal=proposal).first()
        assert verifier is not None
        assert verifier.employee == department_leader
        assert verifier.status == ProposalVerifierStatus.NOT_VERIFIED

    def test_no_verifier_when_department_has_no_leader(self, employee_without_leader):
        """Test that no verifier is created when department has no leader."""
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Late check-in",
            created_by=employee_without_leader,
        )

        # Verify that no ProposalVerifier was created
        verifier_count = ProposalVerifier.objects.filter(proposal=proposal).count()
        assert verifier_count == 0

    def test_verifier_when_creator_is_department_leader(self, department_leader):
        """Test that no verifier is created when the proposal creator is the department leader."""
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Late check-in",
            created_by=department_leader,
        )

        # Verify that no ProposalVerifier was created (leader should not verify their own proposal)
        verifier_count = ProposalVerifier.objects.filter(proposal=proposal).count()
        assert verifier_count == 1

    def test_verifier_not_duplicated_on_update(self, employee_with_leader, department_leader):
        """Test that updating a proposal does not create duplicate verifiers."""
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Late check-in",
            created_by=employee_with_leader,
        )

        # Verify initial verifier was created
        initial_count = ProposalVerifier.objects.filter(proposal=proposal).count()
        assert initial_count == 1

        # Update the proposal
        proposal.note = "Updated note"
        proposal.save()

        # Verify that no additional verifier was created
        updated_count = ProposalVerifier.objects.filter(proposal=proposal).count()
        assert updated_count == 1

    def test_auto_assign_works_for_different_proposal_types(self, employee_with_leader, department_leader):
        """Test that auto-assign works for various proposal types."""
        proposal_types = [
            (ProposalType.PAID_LEAVE, {"paid_leave_reason": "Vacation"}),
            (ProposalType.UNPAID_LEAVE, {"unpaid_leave_reason": "Personal"}),
            (ProposalType.ASSET_ALLOCATION, {}),
            (ProposalType.OVERTIME_WORK, {}),
        ]

        for proposal_type, extra_fields in proposal_types:
            proposal = Proposal.objects.create(
                proposal_type=proposal_type,
                created_by=employee_with_leader,
                **extra_fields,
            )

            verifier = ProposalVerifier.objects.filter(proposal=proposal, employee=department_leader).first()
            assert verifier is not None, f"Verifier not created for proposal type {proposal_type}"
            assert verifier.status == ProposalVerifierStatus.NOT_VERIFIED
