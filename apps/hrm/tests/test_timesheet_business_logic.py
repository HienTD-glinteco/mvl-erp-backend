import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.utils import timezone
from apps.hrm.models import (
    Employee, TimeSheetEntry, WorkSchedule, Contract,
    Proposal, Holiday, CompensatoryWorkday,
    ContractType
)
from apps.hrm.constants import (
    TimesheetStatus, TimesheetDayType, EmployeeType,
    ProposalType, ProposalStatus, ProposalWorkShift,
    STANDARD_WORKING_HOURS_PER_DAY
)
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

@pytest.fixture
def mock_work_schedule():
    schedule = MagicMock(spec=WorkSchedule)
    schedule.morning_start_time = time(8, 0)
    schedule.morning_end_time = time(12, 0)
    schedule.afternoon_start_time = time(13, 30)
    schedule.afternoon_end_time = time(17, 30)
    schedule.allowed_late_minutes = 5
    return schedule

@pytest.fixture
def mock_employee():
    employee = MagicMock(spec=Employee)
    employee.id = 1
    employee.employee_type = EmployeeType.OFFICIAL
    return employee

@pytest.fixture
def timesheet_entry(mock_employee):
    entry = MagicMock(spec=TimeSheetEntry)
    entry.employee = mock_employee
    entry.employee_id = mock_employee.id
    entry.date = date(2023, 10, 25) # Wednesday
    entry.start_time = None
    entry.end_time = None
    entry.official_hours = Decimal("0.00")
    entry.status = None
    entry.working_days = Decimal("0.00")
    entry.day_type = TimesheetDayType.OFFICIAL
    entry.count_for_payroll = True
    entry.is_full_salary = True
    entry.absent_reason = None
    return entry

@pytest.mark.django_db
class TestTimesheetBusinessLogic:

    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.Holiday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_2_shifts(self, mock_proposals, mock_holiday, mock_compensatory, mock_get_schedule, timesheet_entry, mock_work_schedule):
        # Scenario: 2 shifts (Morning + Afternoon), Single Punch
        # Result should be max 0.5

        mock_get_schedule.return_value = mock_work_schedule
        mock_holiday.return_value.exists.return_value = False
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
    @patch("apps.hrm.services.timesheet_calculator.Holiday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_1_shift(self, mock_proposals, mock_holiday, mock_compensatory, mock_get_schedule, timesheet_entry, mock_work_schedule):
        # Scenario: 1 shift (Morning only), Single Punch
        # Result should be max 0.25

        mock_work_schedule.afternoon_start_time = None
        mock_work_schedule.afternoon_end_time = None
        mock_get_schedule.return_value = mock_work_schedule

        mock_holiday.return_value.exists.return_value = False
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
    @patch("apps.hrm.services.timesheet_calculator.Holiday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_2_shifts_with_leave(self, mock_proposals, mock_holiday, mock_compensatory, mock_get_schedule, timesheet_entry, mock_work_schedule):
        # Scenario: 2 shifts, but 1 shift leave (e.g. Morning Leave), Single Punch (in Afternoon)
        # Result should be max 0.25 for the work + 0.50 for leave = 0.75

        mock_get_schedule.return_value = mock_work_schedule
        mock_holiday.return_value.exists.return_value = False
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
    @patch("apps.hrm.services.timesheet_calculator.Holiday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_single_punch_late_start(self, mock_proposals, mock_holiday, mock_compensatory, mock_get_schedule, timesheet_entry, mock_work_schedule):
        # Scenario: 2 shifts, Single Punch, but VERY late.
        # Start at 16:30 (only 1 hour left).
        # Hypothetical: 1 hour = 0.125 days.
        # Cap: 0.5 days.
        # Min(0.125, 0.5) = 0.125.

        mock_get_schedule.return_value = mock_work_schedule
        mock_holiday.return_value.exists.return_value = False
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
    @patch("apps.hrm.services.timesheet_calculator.Holiday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_maternity_bonus(self, mock_proposals, mock_holiday, mock_compensatory, mock_get_schedule, timesheet_entry, mock_work_schedule):
        # Scenario: Normal working day + Maternity Mode
        # Official hours: 8 hours (1.0 day)
        # Maternity bonus +0.125
        # Total 1.125 -> Capped at 1.0 (daily max)

        mock_get_schedule.return_value = mock_work_schedule
        mock_holiday.return_value.exists.return_value = False
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

    @patch("apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday")
    @patch("apps.hrm.services.timesheet_calculator.CompensatoryWorkday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.Holiday.objects.filter")
    @patch("apps.hrm.services.timesheet_calculator.TimesheetCalculator._fetch_approved_proposals_flags")
    def test_compensatory_day_type(self, mock_proposals, mock_holiday, mock_compensatory, mock_get_schedule, timesheet_entry, mock_work_schedule):
        # Scenario: Compensatory day
        # Ensure day_type is COMPENSATORY

        mock_get_schedule.return_value = mock_work_schedule
        mock_holiday.return_value.exists.return_value = False
        mock_proposals.return_value = (False, False, False, 0, None)

        # Compensatory exists
        mock_comp_day = MagicMock(spec=CompensatoryWorkday)
        mock_comp_day.session = CompensatoryWorkday.Session.FULL_DAY
        mock_compensatory.return_value.first.return_value = mock_comp_day

        calculator = TimesheetCalculator(timesheet_entry)
        calculator.compute_status()

        assert timesheet_entry.day_type == TimesheetDayType.COMPENSATORY

    def test_payroll_count_unpaid(self, timesheet_entry, mock_employee):
        # Scenario: Employee is UNPAID_OFFICIAL
        # count_for_payroll should be False

        mock_employee.employee_type = EmployeeType.UNPAID_OFFICIAL
        timesheet_entry.employee = mock_employee

        with patch("apps.hrm.services.timesheet_calculator.Employee.objects.filter") as mock_emp_qs:
             # Just to avoid DB hit if service calls DB
             calculator = TimesheetCalculator(timesheet_entry)
             calculator.compute_status()

        assert timesheet_entry.count_for_payroll is False
