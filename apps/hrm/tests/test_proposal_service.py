from datetime import date, time
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.hrm.constants import ProposalStatus, ProposalType, TimesheetReason, TimesheetStatus
from apps.hrm.models import (
    AttendanceRecord,
    Block,
    Branch,
    Department,
    Employee,
    Position,
    Proposal,
    ProposalOvertimeEntry,
    ProposalTimeSheetEntry,
    TimeSheetEntry,
)
from apps.hrm.services.proposal_service import ProposalExecutionError, ProposalService

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_employee(db):
    """Create a test employee for proposal service tests."""
    from apps.core.models import AdministrativeUnit, Province, User

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

    # Create user for employee
    user = User.objects.create_user(
        username="user_svc_001",
        email="svc001@example.com",
        password="testpass123",
    )

    employee = Employee.objects.create(
        code="MV_SVC_001",
        fullname="Service Test Employee",
        username="user_svc_001",
        email="svc001@example.com",
        phone="0988801001",
        attendance_code="88001",
        citizen_id="888000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
        user=user,
    )
    return employee


class TestPaidLeaveProposal:
    """Tests for PAID_LEAVE proposal execution."""

    def test_execute_paid_leave_single_day(self, test_employee):
        """Test executing a single-day paid leave proposal."""
        # Create a paid leave proposal
        proposal = Proposal.objects.create(
            code="DX_LEAVE_001",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=date(2025, 1, 15),
            paid_leave_end_date=date(2025, 1, 15),
            paid_leave_shift="full_day",
            created_by=test_employee,
        )

        # Execute the proposal
        ProposalService.execute_approved_proposal(proposal)

        # Verify timesheet entry was created and marked as absent
        entry = TimeSheetEntry.objects.get(employee=test_employee, date=date(2025, 1, 15))
        assert entry.status == TimesheetStatus.ABSENT
        assert entry.absent_reason == TimesheetReason.PAID_LEAVE
        assert entry.official_hours == 0
        assert entry.overtime_hours == 0

    def test_execute_paid_leave_multiple_days(self, test_employee):
        """Test executing a multi-day paid leave proposal."""
        # Create a 3-day paid leave proposal
        proposal = Proposal.objects.create(
            code="DX_LEAVE_002",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=date(2025, 1, 20),
            paid_leave_end_date=date(2025, 1, 22),
            paid_leave_shift="full_day",
            created_by=test_employee,
        )

        # Execute the proposal
        ProposalService.execute_approved_proposal(proposal)

        # Verify all three days are marked as absent
        for day in [20, 21, 22]:
            entry = TimeSheetEntry.objects.get(employee=test_employee, date=date(2025, 1, day))
            assert entry.status == TimesheetStatus.ABSENT
            assert entry.absent_reason == TimesheetReason.PAID_LEAVE
            assert entry.official_hours == 0


class TestUnpaidLeaveProposal:
    """Tests for UNPAID_LEAVE proposal execution."""

    def test_execute_unpaid_leave(self, test_employee):
        """Test executing an unpaid leave proposal."""
        # Create an unpaid leave proposal
        proposal = Proposal.objects.create(
            code="DX_LEAVE_003",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            unpaid_leave_start_date=date(2025, 2, 10),
            unpaid_leave_end_date=date(2025, 2, 11),
            unpaid_leave_shift="full_day",
            created_by=test_employee,
        )

        # Execute the proposal
        ProposalService.execute_approved_proposal(proposal)

        # Verify days are marked as unpaid leave
        for day in [10, 11]:
            entry = TimeSheetEntry.objects.get(employee=test_employee, date=date(2025, 2, day))
            assert entry.status == TimesheetStatus.ABSENT
            assert entry.absent_reason == TimesheetReason.UNPAID_LEAVE


class TestMaternityLeaveProposal:
    """Tests for MATERNITY_LEAVE proposal execution."""

    def test_execute_maternity_leave(self, test_employee):
        """Test executing a maternity leave proposal."""
        # Create a maternity leave proposal
        proposal = Proposal.objects.create(
            code="DX_LEAVE_004",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            maternity_leave_start_date=date(2025, 3, 1),
            maternity_leave_end_date=date(2025, 3, 5),
            created_by=test_employee,
        )

        # Execute the proposal
        ProposalService.execute_approved_proposal(proposal)

        # Verify all days are marked as maternity leave
        for day in range(1, 6):
            entry = TimeSheetEntry.objects.get(employee=test_employee, date=date(2025, 3, day))
            assert entry.status == TimesheetStatus.ABSENT
            assert entry.absent_reason == TimesheetReason.MATERNITY_LEAVE


class TestComplaintProposalCorrection:
    """Tests for TIMESHEET_ENTRY_COMPLAINT proposal execution (correction case)."""

    def test_execute_complaint_with_correction(self, test_employee):
        """Test executing a complaint proposal with approved correction times."""
        # Create a timesheet entry with incorrect times
        existing_entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 1, 10),
            start_time=timezone.make_aware(timezone.datetime(2025, 1, 10, 9, 30)),
            end_time=timezone.make_aware(timezone.datetime(2025, 1, 10, 17, 0)),
        )

        # Create a complaint proposal with approved times
        proposal = Proposal.objects.create(
            code="DX_COMPLAINT_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.APPROVED,
            timesheet_entry_complaint_complaint_reason="Forgot to check in on time",
            timesheet_entry_complaint_proposed_check_in_time=time(8, 0),
            timesheet_entry_complaint_proposed_check_out_time=time(17, 0),
            timesheet_entry_complaint_approved_check_in_time=time(8, 0),
            timesheet_entry_complaint_approved_check_out_time=time(17, 0),
            created_by=test_employee,
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(proposal=proposal, timesheet_entry=existing_entry)

        # Execute the proposal
        ProposalService.execute_approved_proposal(proposal)

        # Verify timesheet entry was updated with approved times
        existing_entry.refresh_from_db()
        # Convert to local timezone before comparing times to avoid UTC offset issues
        local_start_time = timezone.localtime(existing_entry.start_time).time()
        local_end_time = timezone.localtime(existing_entry.end_time).time()
        assert local_start_time == time(8, 0)
        assert local_end_time == time(17, 0)
        assert existing_entry.is_manually_corrected is True

    def test_manually_corrected_entry_not_overwritten_by_signal(self, test_employee):
        """Test that manually corrected entries are not overwritten by attendance signals."""
        # Create a timesheet entry
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 1, 12),
            start_time=timezone.make_aware(timezone.datetime(2025, 1, 12, 8, 0)),
            end_time=timezone.make_aware(timezone.datetime(2025, 1, 12, 17, 0)),
            is_manually_corrected=True,
        )

        # Create an attendance record (simulating a late arrival)
        AttendanceRecord.objects.create(
            attendance_type="biometric_device",
            employee=test_employee,
            attendance_code=test_employee.attendance_code,
            timestamp=timezone.make_aware(timezone.datetime(2025, 1, 12, 9, 30)),
        )

        # Verify the timesheet entry was not changed
        entry.refresh_from_db()
        # Convert to local timezone before comparing times to avoid UTC offset issues
        local_start_time = timezone.localtime(entry.start_time).time()
        local_end_time = timezone.localtime(entry.end_time).time()
        assert local_start_time == time(8, 0)
        assert local_end_time == time(17, 0)
        assert entry.is_manually_corrected is True


class TestComplaintProposalError:
    """Tests for TIMESHEET_ENTRY_COMPLAINT proposal execution errors."""

    def test_complaint_without_approved_times_raises_error(self, test_employee):
        """Test that complaint without approved times raises an error."""
        existing_entry = TimeSheetEntry.objects.create(employee=test_employee, date=date(2025, 1, 15))

        # Create a complaint proposal without approved times
        # Even if proposed times are present, it should fail if approved times are missing
        proposal = Proposal.objects.create(
            code="DX_COMPLAINT_004",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.APPROVED,
            timesheet_entry_complaint_complaint_reason="Missing approved times",
            timesheet_entry_complaint_proposed_check_in_time=time(8, 0),
            timesheet_entry_complaint_proposed_check_out_time=time(17, 0),
            created_by=test_employee,
        )

        ProposalTimeSheetEntry.objects.create(proposal=proposal, timesheet_entry=existing_entry)

        # Execute the proposal and expect an error
        with pytest.raises(ProposalExecutionError):
            ProposalService.execute_approved_proposal(proposal)


class TestOvertimeProposal:
    """Tests for OVERTIME_WORK proposal execution."""

    def test_execute_overtime_proposal(self, test_employee):
        """Test executing an overtime work proposal."""
        # Create an overtime proposal
        proposal = Proposal.objects.create(
            code="DX_OT_001",
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
        )

        # Add overtime entries
        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 1, 25),
            start_time=time(18, 0),
            end_time=time(21, 0),
            description="Project deadline",
        )

        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 1, 26),
            start_time=time(19, 0),
            end_time=time(22, 0),
            description="Continue project work",
        )

        # Execute the proposal
        ProposalService.execute_approved_proposal(proposal)

        # Verify timesheet entries were created for overtime dates
        entry_25 = TimeSheetEntry.objects.get(employee=test_employee, date=date(2025, 1, 25))
        entry_26 = TimeSheetEntry.objects.get(employee=test_employee, date=date(2025, 1, 26))

        # Entries should exist (overtime calculation happens in calculate_hours_from_schedule)
        assert entry_25 is not None
        assert entry_26 is not None

    def test_overtime_proposal_without_entries_raises_error(self, test_employee):
        """Test that overtime proposal without entries raises an error."""
        # Create an overtime proposal without entries
        proposal = Proposal.objects.create(
            code="DX_OT_002",
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
        )

        # Execute the proposal and expect an error
        with pytest.raises(ProposalExecutionError):
            ProposalService.execute_approved_proposal(proposal)


class TestProposalExecutionErrors:
    """Tests for error handling in proposal execution."""

    def test_complaint_without_linked_entry_raises_error(self, test_employee):
        """Test that complaint proposal without linked timesheet entry raises an error."""
        # Create a complaint proposal without linking to a timesheet entry
        proposal = Proposal.objects.create(
            code="DX_ERR_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.APPROVED,
            timesheet_entry_complaint_complaint_reason="Test error",
            timesheet_entry_complaint_approved_check_in_time=time(8, 0),
            timesheet_entry_complaint_approved_check_out_time=time(17, 0),
            created_by=test_employee,
        )

        # Execute the proposal and expect an error
        with pytest.raises(ProposalExecutionError):
            ProposalService.execute_approved_proposal(proposal)

    def test_leave_without_dates_raises_error(self, test_employee):
        """Test that leave proposal without dates raises an error."""
        # Create a leave proposal without dates
        proposal = Proposal.objects.create(
            code="DX_ERR_002",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            created_by=test_employee,
        )

        # Execute the proposal and expect an error
        with pytest.raises(ProposalExecutionError):
            ProposalService.execute_approved_proposal(proposal)

    def test_unsupported_proposal_type_does_nothing(self, test_employee):
        """Test that unsupported proposal types are safely ignored."""
        # Create a proposal type that doesn't have execution logic
        proposal = Proposal.objects.create(
            code="DX_UNSUP_001",
            proposal_type=ProposalType.LATE_EXEMPTION,
            proposal_status=ProposalStatus.APPROVED,
            late_exemption_start_date=date(2025, 2, 1),
            late_exemption_end_date=date(2025, 2, 28),
            late_exemption_minutes=30,
            created_by=test_employee,
        )

        # Execute the proposal - should not raise an error, just do nothing
        ProposalService.execute_approved_proposal(proposal)


@pytest.fixture
def approver_employee(test_employee):
    """Create an approver employee for notification tests."""
    from apps.core.models import User

    # Create user for approver
    user = User.objects.create_user(
        username="approver_001",
        email="approver001@example.com",
        password="testpass123",
    )

    approver = Employee.objects.create(
        code="MV_APPROVER_001",
        fullname="Approver Employee",
        username="approver_001",
        email="approver001@example.com",
        phone="0988802001",
        attendance_code="88002",
        citizen_id="888000000002",
        branch=test_employee.branch,
        block=test_employee.block,
        department=test_employee.department,
        position=test_employee.position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
        user=user,
    )
    return approver


class TestNotifyProposalApproval:
    """Tests for notify_proposal_approval method."""

    @patch("apps.hrm.services.proposal_service.create_notification")
    def test_notify_complaint_proposal_approval_sends_notification(
        self, mock_create_notification, test_employee, approver_employee
    ):
        """Test that notification is sent for approved timesheet entry complaint."""
        # Create a timesheet entry
        existing_entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 1, 10),
            start_time=timezone.make_aware(timezone.datetime(2025, 1, 10, 9, 30)),
            end_time=timezone.make_aware(timezone.datetime(2025, 1, 10, 17, 0)),
        )

        # Create a complaint proposal with approved times
        proposal = Proposal.objects.create(
            code="DX_NOTIFY_001",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.APPROVED,
            timesheet_entry_complaint_complaint_reason="Forgot to check in on time",
            timesheet_entry_complaint_proposed_check_in_time=time(8, 0),
            timesheet_entry_complaint_proposed_check_out_time=time(17, 0),
            timesheet_entry_complaint_approved_check_in_time=time(8, 0),
            timesheet_entry_complaint_approved_check_out_time=time(17, 0),
            created_by=test_employee,
            approved_by=approver_employee,
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(proposal=proposal, timesheet_entry=existing_entry)

        # Call notify_proposal_approval
        ProposalService.notify_proposal_approval(proposal)

        # Assert create_notification was called with correct arguments
        mock_create_notification.assert_called_once()
        call_kwargs = mock_create_notification.call_args.kwargs
        assert call_kwargs["actor"] == approver_employee.user
        assert call_kwargs["recipient"] == test_employee.user
        assert "Approved" in call_kwargs["verb"]
        assert "08:00:00" in call_kwargs["message"]
        assert "17:00:00" in call_kwargs["message"]
        assert call_kwargs["extra_data"]["proposal_id"] == str(proposal.id)

    @patch("apps.hrm.services.proposal_service.create_notification")
    def test_notify_complaint_proposal_rejection_sends_notification(
        self, mock_create_notification, test_employee, approver_employee
    ):
        """Test that notification is sent for rejected timesheet entry complaint."""
        # Create a timesheet entry
        existing_entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 1, 11),
        )

        # Create a complaint proposal that was rejected
        proposal = Proposal.objects.create(
            code="DX_NOTIFY_002",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.REJECTED,
            timesheet_entry_complaint_complaint_reason="Forgot to check in on time",
            timesheet_entry_complaint_proposed_check_in_time=time(8, 0),
            timesheet_entry_complaint_proposed_check_out_time=time(17, 0),
            created_by=test_employee,
            approved_by=approver_employee,
            approval_note="Rejected due to policy violation",
        )

        # Link proposal to timesheet entry
        ProposalTimeSheetEntry.objects.create(proposal=proposal, timesheet_entry=existing_entry)

        # Call notify_proposal_approval
        ProposalService.notify_proposal_approval(proposal)

        # Assert create_notification was called with correct arguments
        mock_create_notification.assert_called_once()
        call_kwargs = mock_create_notification.call_args.kwargs
        assert call_kwargs["actor"] == approver_employee.user
        assert call_kwargs["recipient"] == test_employee.user
        assert "Rejected" in call_kwargs["verb"]

    @patch("apps.hrm.services.proposal_service.create_notification")
    def test_notify_complaint_proposal_without_approver_does_not_send_notification(
        self, mock_create_notification, test_employee
    ):
        """Test that no notification is sent when approved_by is not set."""
        # Create a complaint proposal without approved_by
        proposal = Proposal.objects.create(
            code="DX_NOTIFY_003",
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.APPROVED,
            timesheet_entry_complaint_complaint_reason="Forgot to check in on time",
            timesheet_entry_complaint_proposed_check_in_time=time(8, 0),
            timesheet_entry_complaint_proposed_check_out_time=time(17, 0),
            timesheet_entry_complaint_approved_check_in_time=time(8, 0),
            timesheet_entry_complaint_approved_check_out_time=time(17, 0),
            created_by=test_employee,
            approved_by=None,
        )

        # Call notify_proposal_approval
        ProposalService.notify_proposal_approval(proposal)

        # Assert create_notification was NOT called
        mock_create_notification.assert_not_called()

    @patch("apps.hrm.services.proposal_service.create_notification")
    def test_notify_unsupported_proposal_type_does_nothing(self, mock_create_notification, test_employee):
        """Test that unsupported proposal types do not send notifications."""
        # Create a proposal type that doesn't have notification logic
        proposal = Proposal.objects.create(
            code="DX_NOTIFY_004",
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=date(2025, 1, 15),
            paid_leave_end_date=date(2025, 1, 15),
            paid_leave_shift="full_day",
            created_by=test_employee,
        )

        # Call notify_proposal_approval
        ProposalService.notify_proposal_approval(proposal)

        # Assert create_notification was NOT called (no handler for PAID_LEAVE)
        mock_create_notification.assert_not_called()
