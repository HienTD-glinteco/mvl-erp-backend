"""Tests for Phase 1: Core Timesheet Logic (Models).

This module tests the new timesheet functionality:
- is_manually_corrected field
- calculate_status method
- overtime calculation in calculate_hours_from_schedule
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import TimesheetStatus
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    Position,
    TimeSheetEntry,
    WorkSchedule,
)


@pytest.fixture
def test_employee(db):
    """Create a test employee with all required organizational structure."""
    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test Unit",
        code="TU",
        parent_province=province,
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
        code="MV001",
        fullname="John Doe",
        username="user_mv001",
        email="mv001@example.com",
        attendance_code="00001",
        citizen_id="000000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )
    return employee


@pytest.mark.django_db
class TestTimesheetManualCorrectionField:
    """Test the is_manually_corrected field."""

    def test_is_manually_corrected_default_false(self, test_employee):
        """Test that is_manually_corrected defaults to False."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),
        )
        assert entry.is_manually_corrected is False

    def test_is_manually_corrected_can_be_set_true(self, test_employee):
        """Test that is_manually_corrected can be set to True."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),
            is_manually_corrected=True,
        )
        assert entry.is_manually_corrected is True


@pytest.mark.django_db
class TestCalculateStatus:
    """Test the calculate_status method."""

    @pytest.fixture(autouse=True)
    def setup_work_schedule(self, db):
        """Create a work schedule for testing."""
        # Create Monday work schedule with allowed_late_minutes = 15
        self.work_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 0),
            afternoon_start_time=time(13, 0),
            afternoon_end_time=time(17, 0),
            allowed_late_minutes=15,
        )

    def test_status_absent_when_no_start_time(self, test_employee):
        """Test that status is ABSENT when there is no start_time."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=None,
            end_time=None,
        )
        assert entry.status == TimesheetStatus.ABSENT

    def test_status_on_time_when_arriving_exactly_on_time(self, test_employee):
        """Test that status is ON_TIME when arriving exactly at morning_start_time."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 0, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 17, 0, 0)),
        )
        assert entry.status == TimesheetStatus.ON_TIME

    def test_status_on_time_when_arriving_within_allowed_late_minutes(self, test_employee):
        """Test that status is ON_TIME when arriving within allowed_late_minutes."""
        # Arrive at 8:15 (15 minutes late, within allowed_late_minutes)
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 15, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 17, 0, 0)),
        )
        assert entry.status == TimesheetStatus.ON_TIME

    def test_status_not_on_time_when_arriving_late(self, test_employee):
        """Test that status is NOT_ON_TIME when arriving beyond allowed_late_minutes."""
        # Arrive at 8:16 (16 minutes late, beyond allowed_late_minutes of 15)
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 16, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 17, 0, 0)),
        )
        assert entry.status == TimesheetStatus.NOT_ON_TIME

    def test_status_on_time_when_arriving_early(self, test_employee):
        """Test that status is ON_TIME when arriving before morning_start_time."""
        # Arrive at 7:30 (30 minutes early)
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 7, 30, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 17, 0, 0)),
        )
        assert entry.status == TimesheetStatus.ON_TIME


@pytest.mark.django_db
class TestOvertimeCalculation:
    """Test the overtime calculation in calculate_hours_from_schedule."""

    @pytest.fixture(autouse=True)
    def setup_work_schedule(self, db):
        """Create a work schedule for testing."""
        self.work_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 0),
            afternoon_start_time=time(13, 0),
            afternoon_end_time=time(17, 0),
            allowed_late_minutes=15,
        )

    def test_no_overtime_without_approved_proposal(self, test_employee):
        """Test that overtime is 0 when there is no approved overtime proposal."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 0, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 19, 0, 0)),  # Working 2 hours extra
        )
        entry.calculate_hours_from_schedule(self.work_schedule)
        entry.save()

        # Official hours should be 8 (4 morning + 4 afternoon)
        assert entry.morning_hours == Decimal("4.00")
        assert entry.afternoon_hours == Decimal("4.00")
        assert entry.official_hours == Decimal("8.00")
        # Overtime should be 0 because there's no approved proposal
        assert entry.overtime_hours == Decimal("0.00")

    def test_overtime_with_approved_proposal(self, test_employee):
        """Test that overtime is calculated when there's an approved overtime proposal."""
        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry

        # Create an approved overtime proposal
        proposal = Proposal.objects.create(
            created_by=test_employee,
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
        )

        # Create overtime entry for the proposal (2 hours approved)
        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 12, 1),
            start_time=time(17, 0),
            end_time=time(19, 0),
            description="Overtime work",
        )

        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 0, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 19, 0, 0)),  # 2 hours overtime
        )
        entry.calculate_hours_from_schedule(self.work_schedule)
        entry.save()

        # Official hours should be 8 (4 morning + 4 afternoon)
        assert entry.morning_hours == Decimal("4.00")
        assert entry.afternoon_hours == Decimal("4.00")
        assert entry.official_hours == Decimal("8.00")
        # Overtime should be 2 hours (approved in proposal)
        assert entry.overtime_hours == Decimal("2.00")

    def test_overtime_capped_by_approved_duration(self, test_employee):
        """Test that overtime is capped by the approved duration in the proposal."""
        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry

        # Create an approved overtime proposal
        proposal = Proposal.objects.create(
            created_by=test_employee,
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
        )

        # Create overtime entry for the proposal (only 1 hour approved)
        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 12, 1),
            start_time=time(17, 0),
            end_time=time(18, 0),
            description="Overtime work",
        )

        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 0, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 19, 0, 0)),  # Working 2 hours extra
        )
        entry.calculate_hours_from_schedule(self.work_schedule)
        entry.save()

        # Official hours should be 8 (4 morning + 4 afternoon)
        assert entry.morning_hours == Decimal("4.00")
        assert entry.afternoon_hours == Decimal("4.00")
        assert entry.official_hours == Decimal("8.00")
        # Overtime should be 1 hour (capped by approved duration, even though worked 2 hours extra)
        assert entry.overtime_hours == Decimal("1.00")

    def test_no_overtime_when_working_less_than_schedule(self, test_employee):
        """Test that overtime is 0 when working less than scheduled hours."""
        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry

        # Create an approved overtime proposal
        proposal = Proposal.objects.create(
            created_by=test_employee,
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
        )

        # Create overtime entry for the proposal
        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 12, 1),
            start_time=time(17, 0),
            end_time=time(19, 0),
            description="Overtime work",
        )

        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 0, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 16, 0, 0)),  # 1 hour less than schedule
        )
        entry.calculate_hours_from_schedule(self.work_schedule)
        entry.save()

        # Official hours should be less than 8
        assert entry.morning_hours == Decimal("4.00")
        assert entry.afternoon_hours == Decimal("3.00")
        assert entry.official_hours == Decimal("7.00")
        # Overtime should be 0 (raw_ot is negative, so max(0, -1) = 0)
        assert entry.overtime_hours == Decimal("0.00")

    def test_total_worked_hours_includes_overtime(self, test_employee):
        """Test that total_worked_hours correctly includes overtime."""
        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry

        # Create an approved overtime proposal
        proposal = Proposal.objects.create(
            created_by=test_employee,
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
        )

        # Create overtime entry for the proposal (2 hours approved)
        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 12, 1),
            start_time=time(17, 0),
            end_time=time(19, 0),
            description="Overtime work",
        )

        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 0, 0)),
            end_time=timezone.make_aware(datetime(2025, 12, 1, 19, 0, 0)),  # 2 hours overtime
        )
        entry.calculate_hours_from_schedule(self.work_schedule)
        entry.save()

        # Total worked hours should be official_hours + overtime_hours
        assert entry.official_hours == Decimal("8.00")
        assert entry.overtime_hours == Decimal("2.00")
        assert entry.total_worked_hours == Decimal("10.00")


@pytest.mark.django_db
class TestTimesheetIntegration:
    """Integration tests for timesheet calculations."""

    @pytest.fixture(autouse=True)
    def setup_work_schedule(self, db):
        """Create a work schedule for testing."""
        self.work_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 0),
            afternoon_start_time=time(13, 0),
            afternoon_end_time=time(17, 0),
            allowed_late_minutes=15,
        )

    def test_complete_timesheet_entry_with_all_calculations(self, test_employee):
        """Test a complete timesheet entry with all calculations."""
        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry

        # Create an approved overtime proposal (1.5 hours)
        proposal = Proposal.objects.create(
            created_by=test_employee,
            proposal_type=ProposalType.OVERTIME_WORK,
            proposal_status=ProposalStatus.APPROVED,
        )

        ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2025, 12, 1),
            start_time=time(17, 0),
            end_time=time(18, 30),
            description="Overtime work",
        )

        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 12, 1),  # Monday
            start_time=timezone.make_aware(datetime(2025, 12, 1, 8, 10, 0)),  # 10 minutes late
            end_time=timezone.make_aware(datetime(2025, 12, 1, 18, 30, 0)),  # 1.5 hours overtime
        )

        # Calculate hours from schedule
        entry.calculate_hours_from_schedule(self.work_schedule)
        entry.save()

        # Refresh from DB to ensure all calculations are complete
        entry.refresh_from_db()

        # Verify all fields are correctly calculated
        assert entry.status == TimesheetStatus.ON_TIME  # Within allowed_late_minutes
        assert entry.morning_hours == Decimal("3.83")  # ~3 hours 50 minutes (8:10-12:00)
        assert entry.afternoon_hours == Decimal("4.00")  # 4 hours (13:00-17:00)
        assert entry.official_hours == Decimal("7.83")
        # Raw OT = (10.33 actual - 1 hour break) - 8 standard = 1.33 hours
        # Approved OT = 1.50 hours, so final OT = min(1.33, 1.50) = 1.33
        assert entry.overtime_hours == Decimal("1.33")  # Capped by actual work performed
        assert entry.total_worked_hours == Decimal("9.16")  # 7.83 + 1.33
        assert entry.is_manually_corrected is False
