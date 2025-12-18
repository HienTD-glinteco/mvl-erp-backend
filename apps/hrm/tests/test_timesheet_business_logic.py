from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import (
    EmployeeType,
    ProposalWorkShift,
    TimesheetDayType,
    TimesheetStatus,
)
from apps.hrm.models import Block, Branch, Department, Employee, TimeSheetEntry, WorkSchedule
from apps.hrm.services.timesheet_calculator import TimesheetCalculator


@pytest.fixture
def work_schedule():
    schedule = WorkSchedule.objects.create(
        weekday=WorkSchedule.Weekday.WEDNESDAY,
        morning_start_time=time(8, 0),
        morning_end_time=time(12, 0),
        afternoon_start_time=time(13, 30),
        afternoon_end_time=time(17, 30),
        allowed_late_minutes=5,
    )
    return schedule


@pytest.fixture
def branch():
    province = Province.objects.create(name="Test Province", code="TP")
    admin_unit = AdministrativeUnit.objects.create(
        name="Unit 1", code="U", parent_province=province, level=AdministrativeUnit.UnitLevel.DISTRICT
    )

    return Branch.objects.create(name="Branch", province=province, administrative_unit=admin_unit)


@pytest.fixture
def block(branch):
    return Block.objects.create(name="Block", branch=branch, block_type=Block.BlockType.BUSINESS)


@pytest.fixture
def department(branch, block):
    return Department.objects.create(
        name="Dept", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )


@pytest.fixture
def employee(department):
    employee = Employee.objects.create(
        employee_type=EmployeeType.OFFICIAL,
        code="MV001",
        fullname="Test User Full Name",
        username="testuser_emp",
        email="testuser_emp@example.com",
        personal_email="testuser_personal@example.com",
        phone="0123456789",
        attendance_code="12345",
        date_of_birth="1990-01-01",
        start_date="2024-01-01",
        department=department,
        block=department.block,
        branch=department.branch,
    )
    return employee


@pytest.fixture
def timesheet_entry(employee):
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        employee_id=employee.id,
        date=date(2023, 10, 25),  # Wednesday
        start_time=None,
        end_time=None,
        official_hours=Decimal("0.00"),
        status=None,
        working_days=Decimal("0.00"),
        day_type=TimesheetDayType.OFFICIAL,
        count_for_payroll=True,
        is_full_salary=True,
        absent_reason=None,
    )
    return entry


@pytest.mark.django_db
class TestTimesheetBusinessLogic:
    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_2_shifts(
        self, mock_proposals, mock_compensatory, mock_get_schedule, work_schedule, timesheet_entry
    ):
        # Scenario: 2 shifts (Morning + Afternoon), Single Punch
        # Result should be max 0.5

        mock_get_schedule.return_value = work_schedule
        mock_compensatory.return_value.first.return_value = None

        # No proposals
        mock_proposals.return_value = (False, False, False, 0, None)

        timesheet_entry.status = TimesheetStatus.SINGLE_PUNCH
        # Assume user clocked in at 8:00 AM (start of day)
        # End time missing (Single Punch)
        timesheet_entry.start_time = timezone.make_aware(datetime.combine(timesheet_entry.date, time(8, 0)))

        # The logic should calculate working days based on Start -> Schedule End (17:30)
        # 8:00 to 17:30 minus break (12:00-13:30) = 4 + 4 = 8 hours -> 1.0 day
        # But Cap is 0.5

        calculator = TimesheetCalculator(timesheet_entry)
        calculator.compute_working_days()

        assert timesheet_entry.working_days == Decimal("0.50")

    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_1_shift(
        self, mock_proposals, mock_compensatory, mock_get_schedule, work_schedule, timesheet_entry
    ):
        # Scenario: 1 shift (Morning only), Single Punch
        # Result should be max 0.25

        work_schedule.afternoon_start_time = None
        work_schedule.afternoon_end_time = None
        mock_get_schedule.return_value = work_schedule

        mock_compensatory.return_value.first.return_value = None
        mock_proposals.return_value = (False, False, False, 0, None)

        timesheet_entry.status = TimesheetStatus.SINGLE_PUNCH
        # Clock in 8:00 AM
        timesheet_entry.start_time = timezone.make_aware(datetime.combine(timesheet_entry.date, time(8, 0)))

        # Hypothetical: 8:00 - 12:00 = 4 hours = 0.5 days
        # Cap for 1 shift = 0.25

        calculator = TimesheetCalculator(timesheet_entry)
        calculator.compute_working_days()

        assert timesheet_entry.working_days == Decimal("0.25")

    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_2_shifts_with_leave(
        self, mock_proposals, mock_compensatory, mock_get_schedule, timesheet_entry, work_schedule
    ):
        # Scenario: 2 shifts, but 1 shift leave (e.g. Morning Leave), Single Punch (in Afternoon)
        # Result should be max 0.25 for the work + 0.50 for leave = 0.75

        mock_get_schedule.return_value = work_schedule
        mock_compensatory.return_value.first.return_value = None

        # Half day shift leave (Morning leave -> work AFTERNOON)
        mock_proposals.return_value = (False, False, False, 0, ProposalWorkShift.MORNING)

        timesheet_entry.status = TimesheetStatus.SINGLE_PUNCH
        # Clock in 13:30 (Afternoon start)
        timesheet_entry.start_time = timezone.make_aware(datetime.combine(timesheet_entry.date, time(13, 30)))

        # Hypothetical: 13:30 - 17:30 = 4 hours = 0.5 days
        # Cap for 2 shifts + 1 shift leave = 0.25 (for the work part)
        # Total = 0.5 (Leave) + 0.25 (Work) = 0.75

        calculator = TimesheetCalculator(timesheet_entry)
        calculator.compute_working_days()

        assert timesheet_entry.working_days == Decimal("0.75")

    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_late_start(
        self, mock_proposals, mock_compensatory, mock_get_schedule, timesheet_entry, work_schedule
    ):
        # Scenario: 2 shifts, Single Punch, but VERY late.
        # Start at 16:30 (only 1 hour left).
        # Hypothetical: 1 hour = 0.125 days.
        # Cap: 0.5 days.
        # Min(0.125, 0.5) = 0.125.

        mock_get_schedule.return_value = work_schedule
        mock_compensatory.return_value.first.return_value = None
        mock_proposals.return_value = (False, False, False, 0, None)

        timesheet_entry.status = TimesheetStatus.SINGLE_PUNCH
        timesheet_entry.start_time = timezone.make_aware(datetime.combine(timesheet_entry.date, time(16, 30)))

        calculator = TimesheetCalculator(timesheet_entry)
        calculator.compute_working_days()

        # 1/8 = 0.125. Rounded to 0.13 usually
        assert timesheet_entry.working_days == Decimal("0.13")

    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_maternity_bonus(
        self, mock_proposals, mock_compensatory, mock_get_schedule, timesheet_entry, work_schedule
    ):
        # Scenario: Normal working day + Maternity Mode
        # Official hours: 8 hours (1.0 day)
        # Maternity bonus +0.125
        # Total 1.125 -> Capped at 1.0 (daily max)

        mock_get_schedule.return_value = work_schedule
        mock_compensatory.return_value.first.return_value = None

        # has_maternity_leave = True
        mock_proposals.return_value = (False, False, True, 0, None)

        timesheet_entry.official_hours = Decimal("8.00")
        timesheet_entry.status = TimesheetStatus.ON_TIME

        calculator = TimesheetCalculator(timesheet_entry)
        calculator.compute_working_days()

        assert timesheet_entry.working_days == Decimal("1.00")

        # Scenario: Worked partial day (6 hours = 0.75 day)
        # Maternity bonus +0.125
        # Total = 0.875
        timesheet_entry.official_hours = Decimal("6.00")
        calculator.compute_working_days()
        # 6/8 = 0.75. 0.75 + 0.125 = 0.875 -> 0.88
        assert timesheet_entry.working_days == Decimal("0.88")

    def test_payroll_count_unpaid(self, timesheet_entry, employee):
        # Scenario: Employee is UNPAID_OFFICIAL
        # count_for_payroll should be False

        employee.employee_type = EmployeeType.UNPAID_OFFICIAL
        timesheet_entry.employee = employee

        with patch("apps.hrm.services.timesheet_calculator.Employee.objects.filter") as mock_emp_qs:
            # Just to avoid DB hit if service calls DB
            calculator = TimesheetCalculator(timesheet_entry)
            calculator.compute_status()

        assert timesheet_entry.count_for_payroll is False
