import uuid
from datetime import date, datetime, time
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalStatus, ProposalType, ProposalWorkShift, TimesheetStatus
from apps.hrm.models.employee import Employee
from apps.hrm.models.organization import Block, Branch, Department
from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry, ProposalTimeSheetEntry
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.signals.proposal_timesheet_entry import link_timesheet_entries_to_proposal_task
from apps.hrm.tasks.timesheets import link_proposals_to_timesheet_entry_task

pytestmark = pytest.mark.django_db


def make_datetime(d: date, t: time):
    return timezone.make_aware(datetime.combine(d, t))


def _create_employee():
    # Minimal related org objects
    prov = Province.objects.create(
        code=str(uuid.uuid4())[:2], name="P", english_name="P", level=Province.ProvinceLevel.CENTRAL_CITY, enabled=True
    )
    admin = AdministrativeUnit.objects.create(
        code=str(uuid.uuid4())[:3],
        name="AU",
        parent_province=prov,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
        enabled=True,
    )
    branch = Branch.objects.create(name="B", code=str(uuid.uuid4())[:3], province=prov, administrative_unit=admin)
    block = Block.objects.create(
        name="BL", code=str(uuid.uuid4())[:3], block_type=Block.BlockType.SUPPORT, branch=branch
    )
    dept = Department.objects.create(name="D", code=str(uuid.uuid4())[:3], branch=branch, block=block)

    unique = str(uuid.uuid4())[:8]
    emp = Employee.objects.create(
        code=f"MV{unique}",
        fullname="Test Employee",
        attendance_code="12345",
        username=f"u_{unique}",
        email=f"{unique}@example.com",
        personal_email=f"{unique}.personal@example.com",
        branch=branch,
        block=block,
        department=dept,
        start_date=date(2020, 1, 1),
        citizen_id=str(uuid.uuid4().int)[:12],
        phone="0123456789",
    )
    return emp


def _create_monday_schedule():
    # Weekday 2 = Monday
    return WorkSchedule.objects.create(
        weekday=2,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        noon_start_time=time(12, 0),
        noon_end_time=time(13, 0),
        afternoon_start_time=time(13, 0),
        afternoon_end_time=time(17, 0),
        allowed_late_minutes=5,
    )


def test_late_exemption_allows_late_arrival(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)  # Monday

    # Create approved late exemption covering this date
    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.LATE_EXEMPTION,
        late_exemption_start_date=d,
        late_exemption_end_date=d,
        late_exemption_minutes=60,
    )

    ts = TimeSheetEntry(employee=emp, date=d)
    ts.start_time = make_datetime(d, time(9, 0))
    ts.end_time = make_datetime(d, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME


def test_maternity_leave_marks_on_time(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.MATERNITY_LEAVE,
        maternity_leave_start_date=d,
        maternity_leave_end_date=d,
    )

    ts = TimeSheetEntry(employee=emp, date=d)

    # For future dates (is_finalizing=False), leave should show as None (gray/empty)
    TimesheetCalculator(ts).compute_all(is_finalizing=False)
    assert ts.status is None

    # For past/finalized dates (is_finalizing=True), maternity leave should keep status=None
    # (employee is on approved leave, not "absent")
    TimesheetCalculator(ts).compute_all(is_finalizing=True)
    assert ts.status is None


def test_maternity_leave_with_attendance_marks_on_time(settings):
    """If employee has attendance during maternity leave, status should be based on attendance."""
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.MATERNITY_LEAVE,
        maternity_leave_start_date=d,
        maternity_leave_end_date=d,
    )

    ts = TimeSheetEntry(employee=emp, date=d)
    ts.start_time = make_datetime(d, time(8, 0))
    ts.end_time = make_datetime(d, time(17, 30))

    TimesheetCalculator(ts).compute_status(is_finalizing=True)

    # Should be ON_TIME (not ABSENT) since there are attendance records
    assert ts.status == TimesheetStatus.ON_TIME


def test_half_day_paid_leave_allows_afternoon_only(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    # Paid leave for morning only
    Proposal.objects.create(
        created_by=emp,
        proposal_status=ProposalStatus.APPROVED,
        proposal_type=ProposalType.PAID_LEAVE,
        paid_leave_start_date=d,
        paid_leave_end_date=d,
        paid_leave_shift=ProposalWorkShift.MORNING,
    )

    ts = TimeSheetEntry(employee=emp, date=d)
    # attend only afternoon
    ts.start_time = make_datetime(d, time(13, 5))
    ts.end_time = make_datetime(d, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME


def test_single_punch_marks_not_on_time(settings):
    emp = _create_employee()
    _create_monday_schedule()

    d = date(2025, 3, 3)

    ts = TimeSheetEntry(employee=emp, date=d)
    ts.start_time = make_datetime(d, time(8, 30))
    ts.end_time = None
    # Use is_finalizing=True to get SINGLE_PUNCH status (end of day logic)
    TimesheetCalculator(ts).compute_status(is_finalizing=True)

    assert ts.status == TimesheetStatus.SINGLE_PUNCH


class TestTimeSheetProposalLinking:
    @pytest.fixture
    def employee(self):
        return _create_employee()

    def test_link_paid_leave_proposal(self, employee):
        # Create Approved Paid Leave Proposal covering today
        today = timezone.localdate()
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=today,
            paid_leave_end_date=today,
            paid_leave_reason="Vacation",
        )

        # Create TimeSheetEntry
        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Run task directly (bypass signal/celery for logic test)
        result = link_proposals_to_timesheet_entry_task(entry.id)

        # Assert
        assert result["success"] is True
        assert result["added"] == 1
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_link_overtime_proposal(self, employee):
        today = timezone.localdate()

        # Create Approved Overtime Proposal
        proposal = Proposal.objects.create(
            created_by=employee, proposal_type=ProposalType.OVERTIME_WORK, proposal_status=ProposalStatus.APPROVED
        )
        ProposalOvertimeEntry.objects.create(
            proposal=proposal, date=today, start_time=time(18, 0), end_time=time(20, 0)
        )

        # Create TimeSheetEntry
        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Run task
        result = link_proposals_to_timesheet_entry_task(entry.id)

        # Assert
        assert result["added"] == 1
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_link_complaint_proposal(self, employee):
        today = timezone.localdate()

        # Create Complaint Proposal
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.PENDING,
            timesheet_entry_complaint_complaint_date=today,
            timesheet_entry_complaint_complaint_reason="Missed punch",
        )

        # Create TimeSheetEntry
        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Run task
        result = link_proposals_to_timesheet_entry_task(entry.id)

        # Assert
        assert result["added"] == 1
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_links_rejected_proposal(self, employee):
        today = timezone.localdate()

        # Create Rejected Proposal
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.REJECTED,
            paid_leave_start_date=today,
            paid_leave_end_date=today,
            approval_note="Rejected",
        )

        # Create TimeSheetEntry
        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Run task
        result = link_proposals_to_timesheet_entry_task(entry.id)

        # Assert should be linked now (due to removal of status filter)
        assert result["added"] == 1
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_sync_proposals_removes_outdated_links(self, employee):
        today = timezone.localdate()

        # 1. Create a proposal that WAS valid but now might not be (e.g., date changed or we force link it)
        # For simplicity, we create a proposal that matches nothing
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=today,  # Valid
            paid_leave_end_date=today,
            paid_leave_reason="Vacation",
        )

        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Manually link it first
        ProposalTimeSheetEntry.objects.create(proposal=proposal, timesheet_entry=entry)

        # Now change the proposal dates so it NO LONGER matches
        proposal.paid_leave_start_date = today.replace(year=today.year - 1)
        proposal.paid_leave_end_date = today.replace(year=today.year - 1)
        proposal.save()

        # Run task
        result = link_proposals_to_timesheet_entry_task(entry.id)

        # Assert removed
        assert result["removed"] == 1
        assert not ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_sync_proposals_adds_new_links(self, employee):
        today = timezone.localdate()
        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Create new proposal matching
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=today,
            paid_leave_end_date=today,
        )

        # Run task
        result = link_proposals_to_timesheet_entry_task(entry.id)

        # Assert added
        assert result["added"] == 1
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_signal_triggers_task(self, employee, django_capture_on_commit_callbacks):
        # Verify signal triggers the task
        today = timezone.localdate()

        with patch("apps.hrm.tasks.timesheets.link_proposals_to_timesheet_entry_task.delay") as mock_delay:
            # Create TimeSheetEntry should trigger signal which uses transaction.on_commit
            with django_capture_on_commit_callbacks(execute=True):
                entry = TimeSheetEntry.objects.create(employee=employee, date=today)

            # Assert that the task was called
            mock_delay.assert_called_with(entry.id)


class TestProposalToTimeSheetEntryLinking:
    @pytest.fixture
    def employee(self):
        return _create_employee()

    def test_link_timesheets_to_proposal(self, employee):
        today = timezone.localdate()
        entry = TimeSheetEntry.objects.create(employee=employee, date=today)

        # Create Proposal covering today
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=today,
            paid_leave_end_date=today,
        )

        # Run task
        result = link_timesheet_entries_to_proposal_task(proposal.id)

        # Assert
        assert result["success"] is True
        assert result["added"] == 1
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry).exists()

    def test_proposal_date_change_syncs_links(self, employee):
        day1 = timezone.localdate()
        day2 = day1.replace(year=day1.year - 1)

        entry1 = TimeSheetEntry.objects.create(employee=employee, date=day1)
        entry2 = TimeSheetEntry.objects.create(employee=employee, date=day2)

        # Create Proposal covering day1
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_start_date=day1,
            paid_leave_end_date=day1,
        )

        # Initial Link
        link_timesheet_entries_to_proposal_task(proposal.id)
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry1).exists()
        assert not ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry2).exists()

        # Change Proposal to cover day2
        proposal.paid_leave_start_date = day2
        proposal.paid_leave_end_date = day2
        proposal.save()

        # Sync again
        result = link_timesheet_entries_to_proposal_task(proposal.id)

        # Assert
        assert result["removed"] == 1  # Removed entry1
        assert result["added"] == 1  # Added entry2
        assert not ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry1).exists()
        assert ProposalTimeSheetEntry.objects.filter(proposal=proposal, timesheet_entry=entry2).exists()

    def test_proposal_signal_triggers_task(self, employee, django_capture_on_commit_callbacks):
        today = timezone.localdate()

        with patch("apps.hrm.signals.proposal_timesheet_entry.link_timesheet_entries_to_proposal_task") as mock_task:
            with django_capture_on_commit_callbacks(execute=True):
                proposal = Proposal.objects.create(
                    created_by=employee,
                    proposal_type=ProposalType.PAID_LEAVE,
                    proposal_status=ProposalStatus.APPROVED,
                    paid_leave_start_date=today,
                    paid_leave_end_date=today,
                )

            mock_task.assert_called_with(proposal.id)
