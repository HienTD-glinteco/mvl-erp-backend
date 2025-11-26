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
            complaint_reason="Incorrect check-in time",
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

        return Department.objects.create(
            name="Test Department",
            code="TD002",
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
            citizen_id="000000001002",
            start_date="2023-01-01",
            branch=branch,
            block=block,
            department=department,
        )

    @pytest.fixture
    def timesheet_complaint_proposal(self, employee):
        """Create a timesheet entry complaint proposal for testing."""
        return Proposal.objects.create(
            code="DX000003",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            complaint_reason="Incorrect check-in time",
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

    def test_list_proposal_verifiers(self, api_client, superuser, proposal_verifier):
        """Test listing all proposal verifiers."""
        url = reverse("hrm:proposal-verifier-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["id"] == proposal_verifier.id
        assert data["data"]["results"][0]["status"] == ProposalVerifierStatus.NOT_VERIFIED

    def test_retrieve_proposal_verifier(self, api_client, superuser, proposal_verifier):
        """Test retrieving a specific proposal verifier."""
        url = reverse("hrm:proposal-verifier-detail", args=[proposal_verifier.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == proposal_verifier.id
        assert data["data"]["proposal"] == proposal_verifier.proposal.id
        assert data["data"]["employee"] == proposal_verifier.employee.id

    def test_create_proposal_verifier(self, api_client, superuser, timesheet_complaint_proposal, employee):
        """Test creating a new proposal verifier."""
        url = reverse("hrm:proposal-verifier-list")
        data = {
            "proposal": timesheet_complaint_proposal.id,
            "employee": employee.id,
            "note": "New verifier assignment",
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["success"] is True
        assert result["data"]["proposal"] == timesheet_complaint_proposal.id
        assert result["data"]["employee"] == employee.id
        assert result["data"]["status"] == ProposalVerifierStatus.NOT_VERIFIED
        assert result["data"]["note"] == "New verifier assignment"
        assert result["data"]["verified_time"] is None

    def test_update_proposal_verifier(self, api_client, superuser, proposal_verifier):
        """Test updating a proposal verifier."""
        url = reverse("hrm:proposal-verifier-detail", args=[proposal_verifier.id])
        data = {
            "proposal": proposal_verifier.proposal.id,
            "employee": proposal_verifier.employee.id,
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

    def test_verify_timesheet_complaint_proposal_success(self, api_client, superuser, proposal_verifier):
        """Test successfully verifying a timesheet entry complaint proposal."""
        url = reverse("hrm:proposal-verifier-verify", args=[proposal_verifier.id])
        data = {"note": "Verified and approved"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["status"] == ProposalVerifierStatus.VERIFIED
        assert result["data"]["verified_time"] is not None
        assert result["data"]["note"] == "Verified and approved"

        proposal_verifier.refresh_from_db()
        assert proposal_verifier.status == ProposalVerifierStatus.VERIFIED
        assert proposal_verifier.verified_time is not None
        assert proposal_verifier.note == "Verified and approved"

    def test_verify_timesheet_complaint_proposal_without_note(self, api_client, superuser, proposal_verifier):
        """Test verifying a proposal without providing a note."""
        url = reverse("hrm:proposal-verifier-verify", args=[proposal_verifier.id])
        data = {}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["data"]["status"] == ProposalVerifierStatus.VERIFIED
        assert result["data"]["verified_time"] is not None

    def test_verify_non_complaint_proposal_fails(self, api_client, superuser, paid_leave_proposal, employee):
        """Test that verifying a non-complaint proposal raises an error."""
        verifier = ProposalVerifier.objects.create(
            proposal=paid_leave_proposal,
            employee=employee,
        )

        url = reverse("hrm:proposal-verifier-verify", args=[verifier.id])
        data = {"note": "Attempting to verify"}

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        result = response.json()
        assert result["success"] is False
        assert "timesheet entry complaint" in str(result["error"]).lower()

    def test_verify_already_verified_proposal(self, api_client, superuser, proposal_verifier):
        """Test verifying a proposal that has already been verified."""
        # First verification
        url = reverse("hrm:proposal-verifier-verify", args=[proposal_verifier.id])
        data = {"note": "First verification"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

        # Second verification (should succeed, updating the verification)
        data = {"note": "Second verification"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

        proposal_verifier.refresh_from_db()
        assert proposal_verifier.status == ProposalVerifierStatus.VERIFIED
        assert proposal_verifier.note == "Second verification"

    def test_create_duplicate_proposal_verifier_fails(
        self, api_client, superuser, timesheet_complaint_proposal, employee
    ):
        """Test that creating a duplicate proposal verifier fails due to unique constraint."""
        # Create first verifier
        ProposalVerifier.objects.create(
            proposal=timesheet_complaint_proposal,
            employee=employee,
        )

        # Try to create duplicate
        url = reverse("hrm:proposal-verifier-list")
        data = {
            "proposal": timesheet_complaint_proposal.id,
            "employee": employee.id,
        }

        response = api_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
