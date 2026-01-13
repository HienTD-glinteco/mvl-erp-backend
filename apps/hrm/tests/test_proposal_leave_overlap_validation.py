"""Tests for leave proposal overlap validation.

Tests the _clean_leave_overlap_dates method in Proposal model which prevents
overlapping UNPAID_LEAVE and MATERNITY_LEAVE proposals for the same employee.
"""

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Block, Branch, Department, Employee, Position, Proposal

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_employee(db):
    """Create a test employee for leave overlap tests."""
    from apps.core.models import AdministrativeUnit, Province, User

    province = Province.objects.create(name="Test Province Overlap", code="TPO")
    admin_unit = AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit Overlap",
        code="TAUO",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch Overlap",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block Overlap", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept Overlap", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer Overlap")

    user = User.objects.create_user(
        username="user_overlap_001",
        email="overlap001@example.com",
        password="testpass123",
    )

    employee = Employee.objects.create(
        code="MV_OVERLAP_001",
        fullname="Overlap Test Employee",
        username="user_overlap_001",
        email="overlap001@example.com",
        phone="0988809001",
        attendance_code="88009",
        citizen_id="888000000009",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
        user=user,
    )
    return employee


class TestUnpaidLeaveOverlap:
    """Tests for UNPAID_LEAVE overlap validation."""

    def test_unpaid_leave_overlaps_with_existing_unpaid_leave(self, test_employee):
        """Test that creating an overlapping unpaid leave proposal raises ValidationError."""
        # Create first unpaid leave proposal
        Proposal.objects.create(
            code="DX_UNPAID_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2025, 3, 1),
            unpaid_leave_end_date=date(2025, 3, 15),
            created_by=test_employee,
        )

        # Try to create overlapping unpaid leave proposal
        with pytest.raises(ValidationError) as exc_info:
            Proposal.objects.create(
                code="DX_UNPAID_002",
                proposal_type=ProposalType.UNPAID_LEAVE,
                proposal_status=ProposalStatus.PENDING,
                unpaid_leave_start_date=date(2025, 3, 10),
                unpaid_leave_end_date=date(2025, 3, 20),
                created_by=test_employee,
            )

        assert "unpaid_leave_start_date" in exc_info.value.message_dict

    def test_unpaid_leave_overlaps_with_existing_maternity_leave(self, test_employee):
        """Test that unpaid leave cannot overlap with existing maternity leave."""
        # Create maternity leave proposal
        Proposal.objects.create(
            code="DX_MATERNITY_001",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            maternity_leave_start_date=date(2025, 4, 1),
            maternity_leave_end_date=date(2025, 6, 30),
            created_by=test_employee,
        )

        # Try to create overlapping unpaid leave proposal
        with pytest.raises(ValidationError) as exc_info:
            Proposal.objects.create(
                code="DX_UNPAID_003",
                proposal_type=ProposalType.UNPAID_LEAVE,
                proposal_status=ProposalStatus.PENDING,
                unpaid_leave_start_date=date(2025, 5, 1),
                unpaid_leave_end_date=date(2025, 5, 15),
                created_by=test_employee,
            )

        assert "unpaid_leave_start_date" in exc_info.value.message_dict

    def test_unpaid_leave_no_overlap_with_rejected_proposal(self, test_employee):
        """Test that unpaid leave can overlap with REJECTED proposals."""
        # Create rejected unpaid leave proposal
        Proposal.objects.create(
            code="DX_UNPAID_004",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.REJECTED,
            unpaid_leave_start_date=date(2025, 7, 1),
            unpaid_leave_end_date=date(2025, 7, 15),
            approval_note="Rejected for testing",
            created_by=test_employee,
        )

        # Create overlapping unpaid leave proposal - should succeed
        proposal = Proposal.objects.create(
            code="DX_UNPAID_005",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2025, 7, 5),
            unpaid_leave_end_date=date(2025, 7, 20),
            created_by=test_employee,
        )

        assert proposal.pk is not None

    def test_unpaid_leave_no_overlap_non_intersecting_dates(self, test_employee):
        """Test that non-overlapping unpaid leave proposals are allowed."""
        # Create first unpaid leave proposal
        Proposal.objects.create(
            code="DX_UNPAID_006",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2025, 8, 1),
            unpaid_leave_end_date=date(2025, 8, 10),
            created_by=test_employee,
        )

        # Create non-overlapping unpaid leave proposal - should succeed
        proposal = Proposal.objects.create(
            code="DX_UNPAID_007",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2025, 8, 15),
            unpaid_leave_end_date=date(2025, 8, 20),
            created_by=test_employee,
        )

        assert proposal.pk is not None


class TestMaternityLeaveOverlap:
    """Tests for MATERNITY_LEAVE overlap validation."""

    def test_maternity_leave_overlaps_with_existing_maternity_leave(self, test_employee):
        """Test that creating an overlapping maternity leave proposal raises ValidationError."""
        # Create first maternity leave proposal
        Proposal.objects.create(
            code="DX_MAT_001",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            maternity_leave_start_date=date(2025, 9, 1),
            maternity_leave_end_date=date(2025, 11, 30),
            created_by=test_employee,
        )

        # Try to create overlapping maternity leave proposal
        with pytest.raises(ValidationError) as exc_info:
            Proposal.objects.create(
                code="DX_MAT_002",
                proposal_type=ProposalType.MATERNITY_LEAVE,
                proposal_status=ProposalStatus.PENDING,
                maternity_leave_start_date=date(2025, 10, 1),
                maternity_leave_end_date=date(2025, 12, 31),
                created_by=test_employee,
            )

        assert "maternity_leave_start_date" in exc_info.value.message_dict

    def test_maternity_leave_overlaps_with_existing_unpaid_leave(self, test_employee):
        """Test that maternity leave cannot overlap with existing unpaid leave."""
        # Create unpaid leave proposal
        Proposal.objects.create(
            code="DX_UNPAID_008",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 1, 1),
            unpaid_leave_end_date=date(2026, 1, 31),
            created_by=test_employee,
        )

        # Try to create overlapping maternity leave proposal
        with pytest.raises(ValidationError) as exc_info:
            Proposal.objects.create(
                code="DX_MAT_003",
                proposal_type=ProposalType.MATERNITY_LEAVE,
                proposal_status=ProposalStatus.PENDING,
                maternity_leave_start_date=date(2026, 1, 15),
                maternity_leave_end_date=date(2026, 4, 15),
                created_by=test_employee,
            )

        assert "maternity_leave_start_date" in exc_info.value.message_dict

    def test_maternity_leave_no_overlap_with_rejected_proposal(self, test_employee):
        """Test that maternity leave can overlap with REJECTED proposals."""
        # Create rejected maternity leave proposal
        Proposal.objects.create(
            code="DX_MAT_004",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.REJECTED,
            maternity_leave_start_date=date(2026, 5, 1),
            maternity_leave_end_date=date(2026, 7, 31),
            approval_note="Rejected for testing",
            created_by=test_employee,
        )

        # Create overlapping maternity leave proposal - should succeed
        proposal = Proposal.objects.create(
            code="DX_MAT_005",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            maternity_leave_start_date=date(2026, 6, 1),
            maternity_leave_end_date=date(2026, 8, 31),
            created_by=test_employee,
        )

        assert proposal.pk is not None


class TestLeaveOverlapEdgeCases:
    """Edge case tests for leave overlap validation."""

    def test_adjacent_dates_do_not_overlap(self, test_employee):
        """Test that adjacent date ranges (end_date == start_date - 1 day) are allowed."""
        # Create first proposal ending on March 15
        Proposal.objects.create(
            code="DX_EDGE_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 3, 1),
            unpaid_leave_end_date=date(2026, 3, 15),
            created_by=test_employee,
        )

        # Create second proposal starting on March 16 - should succeed (adjacent, not overlapping)
        proposal = Proposal.objects.create(
            code="DX_EDGE_002",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 3, 16),
            unpaid_leave_end_date=date(2026, 3, 31),
            created_by=test_employee,
        )

        assert proposal.pk is not None

    def test_boundary_dates_do_not_overlap(self, test_employee):
        """Test that boundary dates (end_date == start_date of next) do NOT overlap.

        This is because the overlap check uses strict inequality: max(s1, s2) < min(e1, e2)
        """
        # Create first proposal ending on April 15
        Proposal.objects.create(
            code="DX_EDGE_003",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 4, 1),
            unpaid_leave_end_date=date(2026, 4, 15),
            created_by=test_employee,
        )

        # Create proposal starting on exactly the end date - should succeed
        # because max(Apr 15, Apr 1) < min(Apr 15, Apr 20) => Apr 15 < Apr 15 => False
        proposal = Proposal.objects.create(
            code="DX_EDGE_004",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 4, 15),
            unpaid_leave_end_date=date(2026, 4, 20),
            created_by=test_employee,
        )

        assert proposal.pk is not None

    def test_true_overlap_detected(self, test_employee):
        """Test that a true overlap (shared days in the middle) is detected."""
        # Create first proposal
        Proposal.objects.create(
            code="DX_EDGE_005A",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 6, 1),
            unpaid_leave_end_date=date(2026, 6, 15),
            created_by=test_employee,
        )

        # Try to create proposal that overlaps in the middle
        with pytest.raises(ValidationError) as exc_info:
            Proposal.objects.create(
                code="DX_EDGE_006",
                proposal_type=ProposalType.UNPAID_LEAVE,
                proposal_status=ProposalStatus.PENDING,
                unpaid_leave_start_date=date(2026, 6, 10),
                unpaid_leave_end_date=date(2026, 6, 20),
                created_by=test_employee,
            )

        assert "unpaid_leave_start_date" in exc_info.value.message_dict

    def test_update_proposal_does_not_conflict_with_self(self, test_employee):
        """Test that updating a proposal doesn't trigger overlap with itself."""
        # Create proposal
        proposal = Proposal.objects.create(
            code="DX_EDGE_005",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=date(2026, 5, 1),
            unpaid_leave_end_date=date(2026, 5, 15),
            created_by=test_employee,
        )

        # Update same proposal - should not raise error
        proposal.unpaid_leave_end_date = date(2026, 5, 20)
        proposal.save()

        proposal.refresh_from_db()
        assert proposal.unpaid_leave_end_date == date(2026, 5, 20)
