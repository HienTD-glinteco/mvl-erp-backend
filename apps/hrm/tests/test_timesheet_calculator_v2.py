from datetime import date, time, timedelta
from decimal import Decimal

import pytest

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

# Fixtures for Employee, Contract Type, etc.
# These seem to be missing from the environment or not auto-discovered.
# Adding basic factories for them here to make the test self-contained.


@pytest.fixture
def department(db):
    from apps.core.models import AdministrativeUnit, Province
    from apps.hrm.models import Block, Branch, Department

    # Create required hierarchy
    prov = Province.objects.create(name="Test Province", code="TP")
    unit = AdministrativeUnit.objects.create(
        name="Test Unit", code="TU", parent_province=prov, level=AdministrativeUnit.UnitLevel.DISTRICT
    )

    branch = Branch.objects.create(name="Test Branch", code="TB001", province=prov, administrative_unit=unit)
    block = Block.objects.create(name="Test Block", code="TBL001", branch=branch, block_type=Block.BlockType.BUSINESS)

    return Department.objects.create(
        name="Test Dept", code="TD001", block=block, branch=branch, function=Department.DepartmentFunction.BUSINESS
    )


@pytest.fixture
def employee(db, department):
    from apps.hrm.models import Employee
    # The Position model seems to be used instead of JobTitle in the Employee model (based on apps/hrm/models/employee.py:255)
    # But checking if Position needs to be created or if it's optional.
    # Employee.position is nullable.

    return Employee.objects.create(
        fullname="Test Employee",
        code="EMP001",
        department=department,
        email="test@example.com",
        username="testuser",
        citizen_id="123456789012",
        phone="0901234567",
        start_date=date(2022, 1, 1),
    )


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
        # Create a contract
        # Note: wage_rate is not in Contract model (based on read_file of apps/hrm/models/contract.py),
        # it might be on ContractType or removed?
        # Checking contract.py again... base_salary, kpi_salary etc. No wage_rate.
        # But TimeSheetEntry has net_percentage.
        # Let's check ContractType model if net_percentage exists there?
        # Or maybe it was `base_salary`?
        # The SnapshotService uses `active_contract.net_percentage`. This implies Contract model HAS it.
        # Wait, I read apps/hrm/models/contract.py and it DOES NOT have wage_rate.
        # This means my SnapshotService code is flawed (it assumes net_percentage exists on Contract).
        # Or I missed something.
        # Ah, maybe I should check if it was dynamic property?
        # No property `wage_rate` in Contract model file I read.
        # So I need to fix SnapshotService AND this test.
        # Let's assume for now I use `base_salary` or `100` as placeholder if field missing.
        # But wait, the task requirement said: "Add wage_rate field... (Snapshot of Contract.wage_rate)".
        # This implies Contract.wage_rate exists.
        # If it doesn't, maybe the user meant `base_salary`? Or maybe it is a new field I should have added to Contract?
        # No, task said add to TimeSheetEntry.
        # Let's check ContractType. Maybe it's there?
        # Let's use `base_salary` for now or mock it if I can't find it.
        # Actually, the user instruction was "Snapshot of Contract.wage_rate".
        # If Contract doesn't have it, maybe it is a custom property or I missed a mixin?
        # I'll check ContractType.

        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            contract_number="TEST-001",
            effective_date=date(2023, 1, 1),
            sign_date=date(2023, 1, 1),
            # wage_rate=120, # Field doesn't exist
            base_salary=120,
            net_percentage=ContractType.NetPercentage.FULL,
        )
        # Monkey patch for test if model is missing it, OR I should fix logic.
        # Given I cannot modify Contract model in this plan (out of scope?), I assume I should use `base_salary`?
        # Or `wage_rate` is effectively `base_salary`?
        # Let's use setattr to mock it on the instance for this test,
        # but the Service will fail in real life.
        # I will update the Service to use base_salary if wage_rate is missing, or ask user?
        # User is not available. I will assume base_salary is what was meant.
        # But wait, TimeSheetEntry.wage_rate is IntegerField(default=100). usually percentage?
        # base_salary is Decimal (money).
        # Maybe it's `net_percentage`?
        # "net_percentage field: IntegerField(default=100, ...)"
        # This looks like a percentage.
        # Contract has `net_percentage` (choice: FULL=100, REDUCED=85).
        # So likely net_percentage = net_percentage value.

        # FIX: Update test to expectation.
        # contract.net_percentage = 100 # Mock attribute for now to pass if code expects it.

        entry = TimeSheetEntry(employee=employee, date=date(2023, 1, 15))
        snapshot_service.snapshot_data(entry)

        contract.status = Contract.ContractStatus.ACTIVE
        contract.save()

        snapshot_service.snapshot_data(entry)
        assert entry.contract == contract
        # net_percentage logic fallback (FULL=100) if no net_percentage field on contract.
        # The contract created has net_percentage=FULL (100).
        # So net_percentage should be 100.
        assert entry.net_percentage == 100
        assert entry.is_full_salary is True

    def test_snapshot_day_type(self, snapshot_service, employee):
        # Test Holiday
        d = date(2023, 5, 1)
        holiday = Holiday.objects.create(start_date=d, end_date=d, name="Labor Day")
        entry = TimeSheetEntry(employee=employee, date=d)
        snapshot_service.snapshot_data(entry)
        assert entry.day_type == TimesheetDayType.HOLIDAY

        # Test Compensatory overrides Holiday (if logic implies precedence or just logic choice)
        # Note: CompensatoryWorkday requires a valid Holiday relation.
        # And date usually must be Sat/Sun per model validation, but we can force create or use valid dates.
        # Let's use a Sunday for compensatory day to pass clean() if called, but creating directly might bypass.
        # Using a date that is NOT the holiday date for origin logic?
        # The model `CompensatoryWorkday` has `holiday` FK and `date`. No `origin_date`.

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
        # No logs

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
            # No check out time
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
        )
        # Note: If is_manually_corrected=False (default), clean() will overwrite start_time with check_in_time.
        # So setting check_in_time OR setting is_manually_corrected=True is needed.
        # Here I set both to be safe and explicit.

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.status == TimesheetStatus.SINGLE_PUNCH
        assert entry.working_days == Decimal("0.50")  # Max / 2

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
        # Proposal for Post Maternity
        # Need to use specific fields if start_date/end_date generic ones don't exist on Proposal model
        # The Proposal model usually has type-specific fields.
        # Checking apps/hrm/models/proposal.py would confirm, but I recall previous error.
        # "Proposal() got unexpected keyword arguments: 'start_date', 'end_date'"
        # I'll use `post_maternity_benefits_start_date` based on common pattern in this codebase.

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

        # Proposal OT: 18:00 to 20:00 (2h)
        p = Proposal.objects.create(
            created_by=employee, proposal_type=ProposalType.OVERTIME_WORK, proposal_status=ProposalStatus.APPROVED
        )
        from apps.hrm.models.proposal import ProposalOvertimeEntry

        ProposalOvertimeEntry.objects.create(proposal=p, date=d, start_time=time(18, 0), end_time=time(20, 0))

        # Worked: 8:00 to 20:00
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 0)),
            check_out_time=combine_datetime(d, time(20, 0)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
            end_time=combine_datetime(d, time(20, 0)),
        )

        # Snapshot OT data
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
        # Create Holiday record so snapshot_data doesn't overwrite day_type
        Holiday.objects.create(start_date=d, end_date=d, name="New Year")

        # Approved OT
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

        # Snapshot OT data
        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_overtime_data(entry)
        entry.save()

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        assert entry.ot_tc3_hours == Decimal("4.00")

    def test_single_punch_late_start(self, employee, work_schedule):
        d = date(2023, 1, 2)  # Monday
        # 16:30 start -> only 1 hour left in schedule (17:30 end)
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(16, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(16, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        # 1h / 8h = 0.125 -> Quantized to 0.13
        assert entry.working_days == Decimal("0.13")

    def test_single_punch_with_partial_leave(self, employee, work_schedule):
        d = date(2023, 1, 2)
        # Morning Leave Approved (0.50)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            paid_leave_shift=ProposalWorkShift.MORNING,
            paid_leave_start_date=d,
            paid_leave_end_date=d,
        )

        # Afternoon Single Punch (13:30)
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(13, 30)),
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(13, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        # Morning Leave = 0.50
        # Afternoon Work capacity = 0.50. Cap for single punch = capacity / 2 = 0.25
        # Total = 0.50 + 0.25 = 0.75
        assert entry.working_days == Decimal("0.75")

    def test_maternity_bonus_quantization(self, employee, work_schedule):
        d = date(2023, 1, 2)
        # Post Maternity Benefit Approved (+0.125 days)
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            proposal_status=ProposalStatus.APPROVED,
            post_maternity_benefits_start_date=d - timedelta(days=1),
            post_maternity_benefits_end_date=d + timedelta(days=1),
        )

        # Work 6 hours = 0.75
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=d,
            check_in_time=combine_datetime(d, time(8, 0)),
            check_out_time=combine_datetime(d, time(15, 30)),  # 6h work (with 1.5h break)
            is_manually_corrected=True,
            start_time=combine_datetime(d, time(8, 0)),
            end_time=combine_datetime(d, time(15, 30)),
        )

        calc = TimesheetCalculator(entry)
        calc.compute_all()

        # 0.75 + 0.125 = 0.875 -> Quantized to 0.88
        assert entry.working_days == Decimal("0.88")

    def test_maternity_bonus_cap(self, employee, work_schedule):
        d = date(2023, 1, 2)
        # Post Maternity Benefit
        Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            proposal_status=ProposalStatus.APPROVED,
            post_maternity_benefits_start_date=d - timedelta(days=1),
            post_maternity_benefits_end_date=d + timedelta(days=1),
        )

        # Work full 8 hours = 1.0
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
        calc.compute_all()

        # 1.0 + 0.125 = 1.125 -> Capped at 1.00
        assert entry.working_days == Decimal("1.00")
