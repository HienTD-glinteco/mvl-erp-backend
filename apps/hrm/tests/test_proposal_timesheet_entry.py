"""Tests for ProposalTimeSheetEntry model and related functionality."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalType, TimesheetStatus
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    Position,
    Proposal,
    ProposalTimeSheetEntry,
    TimeSheetEntry,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(name="Test Province", code="TP")


@pytest.fixture
def admin_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit",
        code="TAU",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch(db, province, admin_unit):
    """Create a test branch."""
    return Branch.objects.create(
        name="Test Branch",
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def block(db, branch):
    """Create a test block."""
    return Block.objects.create(
        name="Test Block",
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )


@pytest.fixture
def department(db, branch, block):
    """Create a test department."""
    return Department.objects.create(
        name="Test Dept",
        branch=branch,
        block=block,
        function=Department.DepartmentFunction.BUSINESS,
    )


@pytest.fixture
def position(db):
    """Create a test position."""
    return Position.objects.create(name="Developer")


@pytest.fixture
def employee(db, branch, block, department, position):
    """Create a test employee."""
    return Employee.objects.create(
        code="MV_TSE_001",
        fullname="Timesheet Test Employee",
        username="user_tse_001",
        email="tse001@example.com",
        phone="0900077001",
        attendance_code="99901",
        citizen_id="999000000901",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )


@pytest.fixture
def timesheet_entry(db, employee):
    """Create a test timesheet entry."""
    entry = TimeSheetEntry(
        employee=employee,
        date=date.today(),
        start_time=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0),
        end_time=datetime.now().replace(hour=17, minute=0, second=0, microsecond=0),
        morning_hours=Decimal("4.00"),
        afternoon_hours=Decimal("4.00"),
        status=TimesheetStatus.ON_TIME,
    )
    entry.save()
    return entry


@pytest.fixture
def another_timesheet_entry(db, employee):
    """Create another test timesheet entry for a different date."""
    entry = TimeSheetEntry(
        employee=employee,
        date=date.today() - timedelta(days=1),
        start_time=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=1),
        end_time=datetime.now().replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=1),
        morning_hours=Decimal("4.00"),
        afternoon_hours=Decimal("4.00"),
        status=TimesheetStatus.ON_TIME,
    )
    entry.save()
    return entry


@pytest.fixture
def complaint_proposal(db, employee):
    """Create a test complaint proposal."""
    return Proposal.objects.create(
        code="DX_TSE_001",
        proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
        timesheet_entry_complaint_complaint_reason="Test complaint reason",
        timesheet_entry_complaint_latitude=Decimal("21.02776"),
        timesheet_entry_complaint_longitude=Decimal("105.85194"),
        timesheet_entry_complaint_address="123 Test Street, Hanoi",
        created_by=employee,
    )


@pytest.fixture
def paid_leave_proposal(db, employee):
    """Create a test paid leave proposal."""
    return Proposal.objects.create(
        code="DX_TSE_002",
        proposal_type=ProposalType.PAID_LEAVE,
        note="Paid leave request",
        created_by=employee,
    )


class TestProposalTimeSheetEntryModel:
    """Tests for ProposalTimeSheetEntry model."""

    def test_create_junction_record(self, complaint_proposal, timesheet_entry):
        """Test creating a junction record between proposal and timesheet entry."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        assert junction.pk is not None
        assert junction.proposal == complaint_proposal
        assert junction.timesheet_entry == timesheet_entry

    def test_str_method(self, complaint_proposal, timesheet_entry):
        """Test the string representation of ProposalTimeSheetEntry."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        expected_str = f"Proposal {complaint_proposal.id} - TimeSheetEntry {timesheet_entry.id}"
        assert str(junction) == expected_str

    def test_related_names(self, complaint_proposal, timesheet_entry):
        """Test the related names are correctly set up."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        # Test accessing from proposal side
        assert junction in complaint_proposal.timesheet_entries.all()

        # Test accessing from timesheet entry side
        assert junction in timesheet_entry.proposals.all()

    def test_cascade_delete_proposal(self, complaint_proposal, timesheet_entry):
        """Test that deleting proposal cascades to junction records."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )
        junction_pk = junction.pk

        complaint_proposal.delete()

        assert not ProposalTimeSheetEntry.objects.filter(pk=junction_pk).exists()

    def test_cascade_delete_timesheet_entry(self, complaint_proposal, timesheet_entry):
        """Test that deleting timesheet entry cascades to junction records."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )
        junction_pk = junction.pk

        timesheet_entry.delete()

        assert not ProposalTimeSheetEntry.objects.filter(pk=junction_pk).exists()


class TestProposalTimeSheetEntryComplaintValidation:
    """Tests for the validation that complaint proposals can only have one timesheet entry."""

    def test_complaint_proposal_allows_first_timesheet_entry(self, complaint_proposal, timesheet_entry):
        """Test that a complaint proposal can be linked to one timesheet entry."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        assert junction.pk is not None

    def test_complaint_proposal_prevents_second_timesheet_entry(
        self, complaint_proposal, timesheet_entry, another_timesheet_entry
    ):
        """Test that a complaint proposal cannot be linked to a second timesheet entry."""
        # Create first junction
        ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        # Attempt to create second junction should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            junction2 = ProposalTimeSheetEntry(
                proposal=complaint_proposal,
                timesheet_entry=another_timesheet_entry,
            )
            junction2.full_clean()  # This should raise ValidationError

        assert "proposal" in exc_info.value.message_dict

    def test_complaint_proposal_validation_on_update(
        self, complaint_proposal, timesheet_entry, another_timesheet_entry
    ):
        """Test that updating an existing junction record still works."""
        junction = ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        # Update the same junction to a different timesheet entry should work
        junction.timesheet_entry = another_timesheet_entry
        junction.full_clean()  # Should not raise
        junction.save()

        assert junction.timesheet_entry == another_timesheet_entry

    def test_different_complaint_proposals_cannot_link_to_same_timesheet_entry(self, employee, timesheet_entry):
        """Test that different complaint proposals cannot link to the same timesheet entry.

        This enforces the bidirectional 1-1 constraint: a timesheet entry can only have
        ONE complaint proposal linked to it.
        """
        proposal1 = Proposal.objects.create(
            code="DX_DIFF_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="First complaint",
            created_by=employee,
        )
        proposal2 = Proposal.objects.create(
            code="DX_DIFF_002",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Second complaint",
            created_by=employee,
        )

        # First junction should succeed
        junction1 = ProposalTimeSheetEntry.objects.create(
            proposal=proposal1,
            timesheet_entry=timesheet_entry,
        )
        assert junction1.pk is not None

        # Second junction with different complaint proposal but same timesheet entry should fail
        with pytest.raises(ValidationError) as exc_info:
            junction2 = ProposalTimeSheetEntry(
                proposal=proposal2,
                timesheet_entry=timesheet_entry,
            )
            junction2.full_clean()

        assert "timesheet_entry" in exc_info.value.message_dict

    def test_update_existing_junction_still_works(self, employee, timesheet_entry, another_timesheet_entry):
        """Test that updating an existing junction to a new timesheet entry still works.

        Even with the bidirectional constraint, updating should work as long as
        the new timesheet entry doesn't already have a complaint proposal.
        """
        proposal = Proposal.objects.create(
            code="DX_UPD_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Complaint reason",
            created_by=employee,
        )

        junction = ProposalTimeSheetEntry.objects.create(
            proposal=proposal,
            timesheet_entry=timesheet_entry,
        )

        # Update to a different timesheet entry should work
        junction.timesheet_entry = another_timesheet_entry
        junction.full_clean()  # Should not raise
        junction.save()

        assert junction.timesheet_entry == another_timesheet_entry

    def test_update_existing_junction_fails_if_new_timesheet_has_complaint(
        self, employee, timesheet_entry, another_timesheet_entry
    ):
        """Test that updating a junction fails if the new timesheet already has a complaint.

        The bidirectional constraint should prevent moving to a timesheet entry
        that already has a complaint proposal linked.
        """
        proposal1 = Proposal.objects.create(
            code="DX_UPF_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="First complaint",
            created_by=employee,
        )
        proposal2 = Proposal.objects.create(
            code="DX_UPF_002",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Second complaint",
            created_by=employee,
        )

        # Create junctions for both proposals to different timesheet entries
        ProposalTimeSheetEntry.objects.create(
            proposal=proposal1,
            timesheet_entry=timesheet_entry,
        )
        junction2 = ProposalTimeSheetEntry.objects.create(
            proposal=proposal2,
            timesheet_entry=another_timesheet_entry,
        )

        # Try to update junction2 to point to the same timesheet as junction1
        junction2.timesheet_entry = timesheet_entry
        with pytest.raises(ValidationError) as exc_info:
            junction2.full_clean()

        assert "timesheet_entry" in exc_info.value.message_dict


class TestProposalTimeSheetEntryUniqueConstraint:
    """Tests for the unique_together constraint on proposal and timesheet_entry."""

    def test_same_proposal_and_timesheet_entry_not_allowed(self, complaint_proposal, timesheet_entry):
        """Test that the same proposal-timesheet_entry pair cannot be created twice."""
        ProposalTimeSheetEntry.objects.create(
            proposal=complaint_proposal,
            timesheet_entry=timesheet_entry,
        )

        with pytest.raises(Exception):  # IntegrityError
            ProposalTimeSheetEntry.objects.create(
                proposal=complaint_proposal,
                timesheet_entry=timesheet_entry,
            )


class TestProposalTimesheetEntryComplaintSerializerFileConfirm:
    """Tests for FileConfirmSerializerMixin integration in ProposalTimesheetEntryComplaintSerializer."""

    def test_serializer_has_file_confirm_fields(self):
        """Test that serializer has file_confirm_fields attribute."""
        from apps.hrm.api.serializers.proposal import ProposalTimesheetEntryComplaintSerializer

        assert hasattr(ProposalTimesheetEntryComplaintSerializer, "file_confirm_fields")
        assert (
            "timesheet_entry_complaint_complaint_image"
            in ProposalTimesheetEntryComplaintSerializer.file_confirm_fields
        )

    def test_serializer_has_files_field(self):
        """Test that serializer instance has 'files' field injected by mixin."""
        from unittest.mock import MagicMock

        from apps.hrm.api.serializers.proposal import ProposalTimesheetEntryComplaintSerializer
        from apps.hrm.constants import ProposalType

        # Create mock context with view
        mock_view = MagicMock()
        mock_view.proposal_type = ProposalType.TIMESHEET_ENTRY_COMPLAINT
        mock_request = MagicMock()

        serializer = ProposalTimesheetEntryComplaintSerializer(context={"view": mock_view, "request": mock_request})

        assert "files" in serializer.fields
        assert serializer.fields["files"].write_only is True
        assert serializer.fields["files"].required is False

    def test_files_field_contains_complaint_image_field(self):
        """Test that files field contains the complaint image field."""
        from unittest.mock import MagicMock

        from apps.hrm.api.serializers.proposal import ProposalTimesheetEntryComplaintSerializer
        from apps.hrm.constants import ProposalType

        # Create mock context
        mock_view = MagicMock()
        mock_view.proposal_type = ProposalType.TIMESHEET_ENTRY_COMPLAINT
        mock_request = MagicMock()

        serializer = ProposalTimesheetEntryComplaintSerializer(context={"view": mock_view, "request": mock_request})

        files_field = serializer.fields["files"]
        # The files field should be a serializer with nested fields
        assert hasattr(files_field, "fields")
        assert "timesheet_entry_complaint_complaint_image" in files_field.fields

    def test_complaint_image_field_in_serializer_meta_fields(self):
        """Test that complaint image field is included in Meta.fields."""
        from apps.hrm.api.serializers.proposal import ProposalTimesheetEntryComplaintSerializer

        assert "timesheet_entry_complaint_complaint_image" in ProposalTimesheetEntryComplaintSerializer.Meta.fields


class TestProposalComplaintImageField:
    """Tests for the timesheet_entry_complaint_complaint_image field in Proposal model."""

    def test_proposal_has_complaint_image_field(self):
        """Test that Proposal model has the complaint image field."""
        from django.db.models import ForeignKey

        from apps.hrm.models import Proposal

        field = Proposal._meta.get_field("timesheet_entry_complaint_complaint_image")
        assert isinstance(field, ForeignKey)
        assert field.null is True
        assert field.blank is True

    def test_proposal_complaint_image_can_be_null(self, employee):
        """Test that complaint proposal can be created without image."""
        proposal = Proposal.objects.create(
            code="DX_IMG_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_reason="Complaint without image",
            created_by=employee,
            timesheet_entry_complaint_complaint_image=None,
        )
        assert proposal.pk is not None
        assert proposal.timesheet_entry_complaint_complaint_image is None

    def test_proposal_complaint_image_related_name(self):
        """Test that FileModel has related_name for complaint proposals."""
        from apps.files.models import FileModel

        # Check the related name exists
        assert hasattr(FileModel, "timesheet_entry_complaint_proposals")
