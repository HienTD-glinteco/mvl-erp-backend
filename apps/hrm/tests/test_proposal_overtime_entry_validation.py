from datetime import date, time

import pytest
from django.core.exceptions import ValidationError

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import ProposalType
from apps.hrm.models import (
    Block,
    Branch,
    CompensatoryWorkday,
    Department,
    Employee,
    Holiday,
    Position,
    Proposal,
    ProposalOvertimeEntry,
    WorkSchedule,
)
from apps.hrm.utils.work_schedule_cache import invalidate_work_schedule_cache

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_employee(db):
    province = Province.objects.create(name="Test Province", code="TP_TEST")
    admin_unit = AdministrativeUnit.objects.create(
        parent_province=province, name="Test Unit", code="TU_TEST", level=AdministrativeUnit.UnitLevel.DISTRICT
    )
    branch = Branch.objects.create(name="Test Branch", province=province, administrative_unit=admin_unit)
    block = Block.objects.create(name="Test Block", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Test Pos")

    return Employee.objects.create(
        code="EMP001",
        fullname="Test Employee",
        username="testuser",
        email="test@example.com",
        phone="0900000001",
        attendance_code="001",
        citizen_id="001001001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2023, 1, 1),
        status=Employee.Status.ACTIVE,
    )


@pytest.fixture
def work_schedule(db):
    # Standard Monday schedule: 08:00-12:00, 12:00-13:30 (Noon), 13:30-17:30
    # Monday is weekday=2 in WorkSchedule model
    WorkSchedule.objects.create(
        weekday=2,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        noon_start_time=time(12, 0),
        noon_end_time=time(13, 30),
        afternoon_start_time=time(13, 30),
        afternoon_end_time=time(17, 30),
    )
    # Saturday (7) - Morning Only (Official)
    WorkSchedule.objects.create(
        weekday=7,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
    )
    # Sunday (8) - Full Day (For testing dynamic lookup overlap)
    WorkSchedule.objects.create(
        weekday=8,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        afternoon_start_time=time(13, 30),
        afternoon_end_time=time(17, 30),
    )


class TestProposalOvertimeValidation:
    def test_overlap_with_work_schedule_morning(self, test_employee, work_schedule):
        """Test validation fails when overtime overlaps with official morning working hours."""
        d = date(2023, 11, 20)  # Monday
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # 09:00 - 10:00 overlaps with 08:00 - 12:00
        entry = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(9, 0), end_time=time(10, 0))
        with pytest.raises(ValidationError) as excinfo:
            entry.clean()
        assert "official morning working hours" in str(excinfo.value)

    def test_overlap_with_work_schedule_afternoon(self, test_employee, work_schedule):
        """Test validation fails when overtime overlaps with official afternoon working hours."""
        d = date(2023, 11, 20)  # Monday
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # 14:00 - 15:00 overlaps with 13:30 - 17:30
        entry = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(14, 0), end_time=time(15, 0))
        with pytest.raises(ValidationError) as excinfo:
            entry.clean()
        assert "official afternoon working hours" in str(excinfo.value)

    def test_valid_entry_outside_work_schedule(self, test_employee, work_schedule):
        """Test validation passes when overtime is outside official working hours."""
        d = date(2023, 11, 20)  # Monday
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # 18:00 - 19:00 is outside all shifts
        entry = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(18, 0), end_time=time(19, 0))
        entry.clean()  # Should pass

    def test_holiday_bypass_work_schedule(self, test_employee, work_schedule):
        """Test validation passes if date is a Holiday (WorkSchedule checks skipped)."""
        d = date(2023, 11, 20)  # Monday
        Holiday.objects.create(name="Test Holiday", start_date=d, end_date=d)

        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)
        entry = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(9, 0), end_time=time(10, 0))
        entry.clean()  # Should pass

    def test_saturday_compensatory_valid_if_no_official_afternoon(self, test_employee, work_schedule):
        """Test Saturday Compensatory: Valid if checks official hours and finds none (e.g. Afternoon)."""
        d = date(2023, 11, 25)  # Saturday (Has Morning Schedule only in fixture)
        holiday = Holiday.objects.create(name="H", start_date=date(2023, 1, 1), end_date=date(2023, 1, 1))

        # Compensatory Day is Afternoon
        CompensatoryWorkday.objects.create(holiday=holiday, date=d, session=CompensatoryWorkday.Session.AFTERNOON)

        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # Fixture Sat (7) has NO Afternoon hours.
        # So overlap check with `reference_schedule.afternoon` (which is None/Empty) should PASS.
        entry_afternoon = ProposalOvertimeEntry(
            proposal=proposal, date=d, start_time=time(14, 0), end_time=time(15, 0)
        )
        entry_afternoon.clean()  # Should Pass

    def test_saturday_compensatory_invalid_if_overlap_official_afternoon(self, test_employee, work_schedule):
        """Test Saturday Compensatory: Invalid if Official Hours exist and overlap."""
        d = date(2023, 11, 25)  # Saturday
        holiday = Holiday.objects.create(name="H", start_date=date(2023, 1, 1), end_date=date(2023, 1, 1))
        CompensatoryWorkday.objects.create(holiday=holiday, date=d, session=CompensatoryWorkday.Session.AFTERNOON)
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # Update Schedule to have Afternoon hours
        ws_sat = WorkSchedule.objects.get(weekday=7)
        ws_sat.afternoon_start_time = time(13, 0)
        ws_sat.afternoon_end_time = time(17, 0)
        ws_sat.save()
        invalidate_work_schedule_cache()

        # Now overlap should error
        entry_afternoon_fail = ProposalOvertimeEntry(
            proposal=proposal, date=d, start_time=time(14, 0), end_time=time(15, 0)
        )
        with pytest.raises(ValidationError) as excinfo:
            entry_afternoon_fail.clean()
        assert "compensatory" in str(excinfo.value)

    def test_sunday_compensatory_full_day_morning_overlap(self, test_employee, work_schedule):
        """Test Sunday Compensatory (Full Day): Overlap Morning -> Error."""
        d = date(2023, 11, 26)  # Sunday
        holiday = Holiday.objects.create(name="H", start_date=date(2023, 1, 1), end_date=date(2023, 1, 1))
        CompensatoryWorkday.objects.create(holiday=holiday, date=d, session=CompensatoryWorkday.Session.FULL_DAY)

        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # Overlap Morning -> Error
        entry_morning = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(9, 0), end_time=time(10, 0))
        with pytest.raises(ValidationError) as excinfo:
            entry_morning.clean()
        assert "compensatory" in str(excinfo.value)

    def test_sunday_compensatory_full_day_afternoon_overlap(self, test_employee, work_schedule):
        """Test Sunday Compensatory (Full Day): Overlap Afternoon -> Error."""
        d = date(2023, 11, 26)  # Sunday
        holiday = Holiday.objects.create(name="H", start_date=date(2023, 1, 1), end_date=date(2023, 1, 1))
        CompensatoryWorkday.objects.create(holiday=holiday, date=d, session=CompensatoryWorkday.Session.FULL_DAY)
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # Overlap Afternoon -> Error
        entry_afternoon = ProposalOvertimeEntry(
            proposal=proposal, date=d, start_time=time(14, 0), end_time=time(15, 0)
        )
        with pytest.raises(ValidationError) as excinfo:
            entry_afternoon.clean()
        assert "compensatory" in str(excinfo.value)

    def test_sunday_compensatory_full_day_valid_evening(self, test_employee, work_schedule):
        """Test Sunday Compensatory (Full Day): Valid Evening entry."""
        d = date(2023, 11, 26)  # Sunday
        holiday = Holiday.objects.create(name="H", start_date=date(2023, 1, 1), end_date=date(2023, 1, 1))
        CompensatoryWorkday.objects.create(holiday=holiday, date=d, session=CompensatoryWorkday.Session.FULL_DAY)
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # Overlap Evening -> Valid (Outside Full Day Comp hours which match Official Hours)
        entry_evening = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(20, 0), end_time=time(21, 0))
        entry_evening.clean()

    def test_sunday_no_compensatory_overlap_official(self, test_employee, work_schedule):
        """Test Sunday NO Compensatory: Validation falls back to Official Checking -> Error if overlap."""
        d = date(2023, 11, 26)  # Sunday
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        # If Sunday has Official Hours (in our Test Fixture), an OT Morning entry overlaps -> FAIL
        entry = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(9, 0), end_time=time(10, 0))
        with pytest.raises(ValidationError) as excinfo:
            entry.clean()
        assert "official morning working hours" in str(excinfo.value)

    def test_sunday_no_compensatory_valid_evening(self, test_employee, work_schedule):
        """Test Sunday NO Compensatory: Valid if outside official hours."""
        d = date(2023, 11, 26)  # Sunday
        proposal = Proposal.objects.create(proposal_type=ProposalType.OVERTIME_WORK, created_by=test_employee)

        entry_valid = ProposalOvertimeEntry(proposal=proposal, date=d, start_time=time(20, 0), end_time=time(21, 0))
        entry_valid.clean()
