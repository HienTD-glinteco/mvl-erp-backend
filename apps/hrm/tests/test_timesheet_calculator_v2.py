from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.hrm.constants import (
    ProposalStatus,
    ProposalType,
    ProposalWorkShift,
    TimesheetDayType,
    TimesheetStatus,
)
from apps.hrm.models import (
    AttendanceExemption,
    CompensatoryWorkday,
    Contract,
    ContractType,
    Holiday,
    Proposal,
    TimeSheetEntry,
    WorkSchedule,
)
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService
from libs.datetimes import combine_datetime


@pytest.fixture
def contract_type(db):
    from apps.hrm.models import ContractType

    return ContractType.objects.create(name="Full Time", code="FT001")


@pytest.fixture
def snapshot_service():
    return TimesheetSnapshotService()


@pytest.fixture
def timesheet_entry(employee):
    # Minimal entry
    return TimeSheetEntry(employee=employee, date=date(2023, 1, 1))


@pytest.fixture
def calculator(timesheet_entry):
    return TimesheetCalculator(timesheet_entry)


@pytest.mark.django_db
class TestTimesheetSnapshotService:
    def test_snapshot_contract_data(self, snapshot_service, employee, contract_type):
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            contract_number="TEST-001",
            effective_date=date(2023, 1, 1),
            sign_date=date(2023, 1, 1),
            base_salary=120,
            net_percentage=ContractType.NetPercentage.FULL,
        )

        entry = TimeSheetEntry(employee=employee, date=date(2023, 1, 15))
        snapshot_service.snapshot_data(entry)

        contract.status = Contract.ContractStatus.ACTIVE
        contract.save()

        snapshot_service.snapshot_data(entry)
        assert entry.contract == contract
        assert entry.net_percentage == 100
        assert entry.is_full_salary is True

    def test_snapshot_day_type(self, snapshot_service, employee):
        # Test Holiday
        d = date(2023, 5, 1)
        holiday = Holiday.objects.create(start_date=d, end_date=d, name="Labor Day")
        entry = TimeSheetEntry(employee=employee, date=d)
        snapshot_service.snapshot_data(entry)
        assert entry.day_type == TimesheetDayType.HOLIDAY

        # Test Compensatory overrides Holiday
        comp_date = date(2023, 5, 7)  # Sunday
        CompensatoryWorkday.objects.create(holiday=holiday, date=comp_date)

        entry_comp = TimeSheetEntry(employee=employee, date=comp_date)
        snapshot_service.snapshot_data(entry_comp)
        assert entry_comp.day_type == TimesheetDayType.COMPENSATORY

    def test_snapshot_exemption(self, snapshot_service, employee):
        d = date(2023, 6, 1)
        AttendanceExemption.objects.create(employee=employee, effective_date=date(2023, 1, 1))

        entry = TimeSheetEntry(employee=employee, date=d)
        snapshot_service.snapshot_data(entry)
        assert entry.is_exempt is True


@pytest.mark.django_db
class TestTimesheetCalculatorV2:
    @pytest.fixture
    def work_schedule(self):
        return WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
            allowed_late_minutes=5,
        )

    def test_exempt_logic(self, employee, work_schedule):
        d = date(2023, 1, 2)  # Monday
        entry = TimeSheetEntry.objects.create(employee=employee, date=d, is_exempt=True)

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.status == TimesheetStatus.ON_TIME
        assert entry.working_days == Decimal("1.00")
        assert entry.late_minutes == 0

    def test_single_punch_logic(self, employee, work_schedule):
        d = date(2023, 1, 2)  # Monday
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 0)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
        )

        calc = TimesheetCalculator(entry)

        # Real-time mode (is_finalizing=False)
        calc.compute_all(is_finalizing=False)
        assert entry.status == TimesheetStatus.NOT_ON_TIME
        assert entry.working_days is None

        # Finalization mode (is_finalizing=True)
        calc.compute_all(is_finalizing=True)
        assert entry.status == TimesheetStatus.SINGLE_PUNCH
        assert entry.working_days == Decimal("0.50")

    def test_late_penalty_standard(self, employee, work_schedule):
        d = date(2023, 1, 2)
        # 8:10 start -> 10 mins late. Grace 5.
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 10)),
            check_out_time=combine_datetime(d, time(17, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 10)),
            end_time=combine_datetime(d, time(17, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.late_minutes == 10
        assert entry.is_punished is True
        assert entry.status == TimesheetStatus.NOT_ON_TIME

    def test_late_penalty_maternity(self, employee, work_schedule):
        d = date(2023, 1, 2)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            proposal_status=ProposalStatus.APPROVED,
            post_maternity_benefits_start_date=d - timedelta(days=10),
            post_maternity_benefits_end_date=d + timedelta(days=10),
        )

        # 8:45 start -> 45 mins late. Grace 65.
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 45)),
            check_out_time=combine_datetime(d, time(17, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 45)),
            end_time=combine_datetime(d, time(17, 30)),
        )

        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_data(entry)

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.late_minutes == 45
        assert entry.is_punished is False
        assert entry.status == TimesheetStatus.ON_TIME

    def test_overtime_tc1(self, employee, work_schedule):
        d = date(2023, 1, 2)  # Monday (Weekday)

        p = Proposal.objects.create(
            created_by=employee, proposal_type=ProposalType.OVERTIME_WORK, proposal_status=ProposalStatus.APPROVED
        )
        from apps.hrm.models.proposal import ProposalOvertimeEntry

        ProposalOvertimeEntry.objects.create(proposal=p, date=d, start_time=time(18, 0), end_time=time(20, 0))

        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 0)),
            check_out_time=combine_datetime(d, time(20, 0)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
            end_time=combine_datetime(d, time(20, 0)),
        )

        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_overtime_data(entry)
        entry.save()

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.ot_tc1_hours == Decimal("2.00")
        assert entry.ot_tc2_hours == Decimal("0.00")
        assert entry.overtime_hours == Decimal("2.00")

    def test_overtime_tc3_holiday(self, employee):
        d = date(2023, 1, 2)
        Holiday.objects.create(start_date=d, end_date=d, name="New Year")

        p = Proposal.objects.create(
            created_by=employee, proposal_type=ProposalType.OVERTIME_WORK, proposal_status=ProposalStatus.APPROVED
        )
        from apps.hrm.models.proposal import ProposalOvertimeEntry

        ProposalOvertimeEntry.objects.create(proposal=p, date=d, start_time=time(8, 0), end_time=time(12, 0))

        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            day_type=TimesheetDayType.HOLIDAY,
            check_in_time=combine_datetime(d, time(8, 0)),
            check_out_time=combine_datetime(d, time(12, 0)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
            end_time=combine_datetime(d, time(12, 0)),
        )

        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_overtime_data(entry)
        entry.save()

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.ot_tc3_hours == Decimal("4.00")

    def test_single_punch_late_start(self, employee, work_schedule):
        d = date(2023, 1, 2)  # Monday
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(16, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(16, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)

        assert entry.working_days == Decimal("0.50")

    def test_single_punch_with_partial_leave(self, employee, work_schedule):
        d = date(2023, 1, 2)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_shift=ProposalWorkShift.MORNING,
            paid_leave_start_date=d,
            paid_leave_end_date=d,
        )

        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(13, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(13, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)

        assert entry.working_days == Decimal("0.50")

    def test_maternity_bonus_quantization(self, employee, work_schedule):
        d = date(2023, 1, 2)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            proposal_status=ProposalStatus.APPROVED,
            post_maternity_benefits_start_date=d - timedelta(days=1),
            post_maternity_benefits_end_date=d + timedelta(days=1),
        )

        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 0)),
            check_out_time=combine_datetime(d, time(15, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
            end_time=combine_datetime(d, time(15, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)  # Past date with complete attendance

        assert entry.working_days == Decimal("0.88")

    def test_maternity_bonus_cap(self, employee, work_schedule):
        d = date(2023, 1, 2)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            proposal_status=ProposalStatus.APPROVED,
            post_maternity_benefits_start_date=d - timedelta(days=1),
            post_maternity_benefits_end_date=d + timedelta(days=1),
        )

        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 0)),
            check_out_time=combine_datetime(d, time(17, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
            end_time=combine_datetime(d, time(17, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)  # Past date with complete attendance

        assert entry.working_days == Decimal("1.00")

    def test_maternity_bonus_no_attendance(self, employee, work_schedule):
        """Maternity bonus should not apply when there's no attendance."""
        d = date(2023, 1, 2)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            proposal_status=ProposalStatus.APPROVED,
            post_maternity_benefits_start_date=d - timedelta(days=1),
            post_maternity_benefits_end_date=d + timedelta(days=1),
        )

        entry = TimeSheetEntry.objects.create(employee=employee, date=d)

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=False)

        # Without attendance and not finalizing, working_days should be None (preview mode)
        assert entry.working_days is None

    def test_compensatory_day_compensation(self, employee):
        d = date(2023, 1, 8)  # Sunday

        WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.SUNDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
        )

        h_date = date(2023, 1, 1)
        holiday = Holiday.objects.create(start_date=h_date, end_date=h_date, name="New YearHoliday")
        CompensatoryWorkday.objects.create(holiday=holiday, date=d)

        entry = TimeSheetEntry.objects.create(employee=employee, date=d)

        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_data(entry)
        entry.save()

        assert entry.day_type == TimesheetDayType.COMPENSATORY

        entry.check_in_time = combine_datetime(d, time(8, 0))
        entry.check_out_time = combine_datetime(d, time(17, 30))
        entry.save()

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)  # Past date with complete attendance

        assert entry.working_days == Decimal("1.00")
        assert entry.compensation_value == Decimal("0.00")

    def test_finalization_status_absent(self, employee, work_schedules):
        # Use a future Thursday so is_finalizing=False initially
        today = timezone.localdate()
        days_until_thursday = (3 - today.weekday()) % 7 + 7  # Next Thursday
        future_thursday = today + timedelta(days=days_until_thursday)

        entry = TimeSheetEntry.objects.create(employee=employee, date=future_thursday)

        # Initially status should be None (preview mode for future date)
        calc = TimesheetCalculator(entry)
        calc.compute_status(is_finalizing=False)
        assert entry.status is None

        # When finalized, status should be ABSENT
        calc.compute_status(is_finalizing=True)
        assert entry.status == TimesheetStatus.ABSENT
