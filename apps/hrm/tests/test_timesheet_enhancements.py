"""Tests for new timesheet model fields and calculations."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.db.models.signals import post_save

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
    EmployeeMonthlyTimesheet,
    Position,
    TimeSheetEntry,
    WorkSchedule,
)
from apps.hrm.services.timesheets import calculate_generated_leave, create_monthly_timesheet_for_employee
from apps.hrm.signals.work_schedule import invalidate_cache_on_work_schedule_save
from apps.hrm.tasks.timesheets import prepare_monthly_timesheets
from apps.hrm.utils.work_schedule_cache import (
    get_all_work_schedules,
    get_work_schedule_by_weekday,
    invalidate_work_schedule_cache,
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
        personal_email="mv001@example.com",
        phone="0900100001",
        attendance_code="00001",
        citizen_id="000000000001",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
    )

    # Create Contract
    contract_type = ContractType.objects.create(name="Full Time", code="FT")
    Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=date(2020, 1, 1),
        effective_date=date(2020, 1, 1),
        status=Contract.ContractStatus.ACTIVE,
        annual_leave_days=12,
        base_salary=10000000,
    )

    return employee


@pytest.mark.django_db
class TestEmployeeMonthlyTimesheetNewFields:
    """Test EmployeeMonthlyTimesheet model new fields and calculations."""

    def test_official_hours_aggregation(self, test_employee):
        """Test that official_hours is aggregated correctly from TimeSheetEntry."""
        year, month = 2025, 8  # Use unique month

        # Create entries with different official hours
        # Use .update() to bypass snapshot reset and force data for aggregation test
        e1 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
        )
        TimeSheetEntry.objects.filter(pk=e1.pk).update(
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
            is_manually_corrected=True,
        )

        e2 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
        )
        TimeSheetEntry.objects.filter(pk=e2.pk).update(
            morning_hours=Decimal("3.00"),
            afternoon_hours=Decimal("5.00"),
            official_hours=Decimal("8.00"),
            is_manually_corrected=True,
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # Total official hours should be 8 + 8 = 16
        assert monthly.official_hours == Decimal("16.00")

    def test_overtime_hours_aggregation(self, test_employee):
        """Test that overtime_hours is aggregated correctly from TimeSheetEntry."""
        year, month = 2025, 9  # Use unique month

        # Create entries with overtime hours
        # Use .update() to bypass snapshot reset
        e1 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
        )
        TimeSheetEntry.objects.filter(pk=e1.pk).update(
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
            overtime_hours=Decimal("2.00"),
            total_worked_hours=Decimal("10.00"),
            is_manually_corrected=True,
        )

        e2 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
        )
        TimeSheetEntry.objects.filter(pk=e2.pk).update(
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
            overtime_hours=Decimal("1.50"),
            total_worked_hours=Decimal("9.50"),
            is_manually_corrected=True,
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        assert monthly.overtime_hours == Decimal("3.50")

    def test_total_worked_hours_aggregation(self, test_employee):
        """Test that total_worked_hours is the sum of official_hours and overtime_hours."""
        year, month = 2025, 11  # Use unique month

        # Use .update() to bypass snapshot reset
        e1 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
        )
        TimeSheetEntry.objects.filter(pk=e1.pk).update(
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
            overtime_hours=Decimal("2.00"),
            total_worked_hours=Decimal("10.00"),
            is_manually_corrected=True,
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # official_hours = 8, overtime = 2, total should be 10
        assert monthly.official_hours == Decimal("8.00")
        assert monthly.overtime_hours == Decimal("2.00")
        assert monthly.total_worked_hours == Decimal("10.00")

    def test_probation_and_official_working_days(self, test_employee):
        """Test calculation of probation and official working days from underlying entries."""
        from apps.hrm.models import Contract, ContractType

        year, month = 2025, 12  # Use unique month

        # Create a Probation Contract starting from 2025-12-02
        # This ensures that entries on or after this date have is_full_salary=False
        # (simulating the manual setting in a strictly snapshotted environment)
        probation_type = ContractType.objects.get(name="Full Time")
        Contract.objects.create(
            employee=test_employee,
            contract_type=probation_type,
            sign_date=date(2025, 12, 2),
            effective_date=date(2025, 12, 2),
            status=Contract.ContractStatus.ACTIVE,
            net_percentage=ContractType.NetPercentage.REDUCED,  # 85%
            base_salary=8500000,
        )

        # 1. Official Day (Day 1)
        e1 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
        )
        TimeSheetEntry.objects.filter(pk=e1.pk).update(
            working_day_type=TimeSheetEntry.WorkingDayType.OFFICIAL,
            working_days=Decimal("1.00"),
            is_full_salary=True,
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
        )

        # 2. Probation Day (Day 2)
        e2 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
        )
        TimeSheetEntry.objects.filter(pk=e2.pk).update(
            working_day_type=TimeSheetEntry.WorkingDayType.PROBATION,
            working_days=Decimal("1.00"),
            is_full_salary=False,
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
        )

        # 3. Probation Day (Day 3)
        e3 = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 3),
        )
        TimeSheetEntry.objects.filter(pk=e3.pk).update(
            working_day_type=TimeSheetEntry.WorkingDayType.PROBATION,
            working_days=Decimal("1.00"),
            is_full_salary=False,
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            official_hours=Decimal("8.00"),
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # Official working days: 8 hours / 8 = 1.00 day (is_full_salary=True)
        # Probation working days: (8 + 8) hours / 8 = 2.00 days (is_full_salary=False)
        # Total working days: (8 + 8 + 8) hours / 8 = 3.00 days
        assert monthly.official_working_days == Decimal("1.00")
        assert monthly.probation_working_days == Decimal("2.00")
        assert monthly.total_working_days == Decimal("3.00")


@pytest.mark.django_db
class TestWorkScheduleCache:
    """Test WorkSchedule caching functionality."""

    def test_cache_all_work_schedules(self, db):
        """Test that get_all_work_schedules uses cache."""
        # Clear cache first
        cache.clear()

        # Create a work schedule
        _ = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )

        # First call should query database and cache
        schedules1 = get_all_work_schedules()
        assert len(schedules1) == 1

        # Delete all schedules from database (not cache)
        WorkSchedule.objects.all().delete()

        # But cache is now invalidated by delete signal, so call will return empty
        schedules_after_delete = get_all_work_schedules()
        assert len(schedules_after_delete) == 0

    def test_cache_by_weekday(self, db):
        """Test that get_work_schedule_by_weekday uses cache."""
        # Disable signals temporarily for this test to test caching behavior
        cache.clear()

        schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )

        # First call caches the result
        cached_schedule = get_work_schedule_by_weekday(WorkSchedule.Weekday.MONDAY)
        assert cached_schedule.id == schedule.id

        # Disconnect signal temporarily
        post_save.disconnect(invalidate_cache_on_work_schedule_save, sender=WorkSchedule)

        # Update the schedule without invalidating cache
        schedule.allowed_late_minutes = 15
        schedule.save()

        # Cached result should still have old value
        cached_schedule2 = get_work_schedule_by_weekday(WorkSchedule.Weekday.MONDAY)
        assert cached_schedule2.allowed_late_minutes is None

        # Reconnect signal
        post_save.connect(invalidate_cache_on_work_schedule_save, sender=WorkSchedule)

        # Bypass cache should return updated value
        fresh_schedule = get_work_schedule_by_weekday(WorkSchedule.Weekday.MONDAY, use_cache=False)
        assert fresh_schedule.allowed_late_minutes == 15

    def test_cache_invalidation_on_save(self, db):
        """Test that cache is invalidated when a WorkSchedule is saved."""
        cache.clear()

        schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )

        # Cache the schedule
        get_all_work_schedules()
        get_work_schedule_by_weekday(WorkSchedule.Weekday.MONDAY)

        # Update the schedule (signal should invalidate cache)
        schedule.allowed_late_minutes = 20
        schedule.save()

        # Cache should be invalidated, so next call should return fresh data
        schedules = get_all_work_schedules()
        assert len(schedules) == 1
        assert schedules[0].allowed_late_minutes == 20

    def test_cache_invalidation_on_delete(self, db):
        """Test that cache is invalidated when a WorkSchedule is deleted."""
        cache.clear()

        schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )

        # Cache the schedules
        get_all_work_schedules()

        # Delete the schedule (signal should invalidate cache)
        schedule.delete()

        # Cache should be invalidated
        schedules = get_all_work_schedules()
        assert len(schedules) == 0

    def test_manual_cache_invalidation(self, db):
        """Test manual cache invalidation."""
        cache.clear()

        WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )

        # Cache the data
        get_all_work_schedules()

        # Manually invalidate cache
        invalidate_work_schedule_cache()

        # After invalidation, next call should query database again
        schedules = get_all_work_schedules()
        assert len(schedules) == 1


@pytest.mark.django_db(transaction=True)
class TestPrepareMonthlyTimesheetsTask:
    """Test prepare_monthly_timesheets task with integrated leave calculation."""

    @pytest.fixture(autouse=True)
    def cleanup_monthly_timesheets(self, db):
        """Clean up any existing monthly timesheets before each test."""
        yield
        # Clean up after each test
        EmployeeMonthlyTimesheet.objects.all().delete()

    def test_prepare_timesheets_updates_leave_for_all_employees(self, test_employee):
        """Test that prepare_monthly_timesheets calculates and updates available_leave_days."""
        # Use a unique month
        year, month = 2025, 5

        # Create a previous month timesheet to simulate opening balance
        # April 2025 (month=4)
        EmployeeMonthlyTimesheet.objects.create(
            employee=test_employee,
            report_date=date(2025, 4, 1),
            month_key="202504",
            remaining_leave_days=Decimal("10.00"),
        )

        # Run task
        result = prepare_monthly_timesheets(employee_id=None, year=year, month=month, increment_leave=True)

        assert result["success"]
        assert result["leave_updated"] >= 1

        # Check that leave was updated
        # Opening (10) + Generated (1) - Consumed (0) = 11
        test_employee.refresh_from_db()
        assert test_employee.available_leave_days == Decimal("11.00")

    def test_prepare_timesheets_can_skip_leave_update(self, test_employee):
        """Test that prepare_monthly_timesheets can skip leave update when requested."""
        # Set initial leave days to something different from what calculation would produce
        test_employee.available_leave_days = Decimal("100.00")
        test_employee.save()

        # Use a different unique month
        year, month = 2025, 6

        # No previous month, so Opening=0, Generated=1 -> Remaining=1.
        # If we skip update, it should stay 100.

        result = prepare_monthly_timesheets(employee_id=None, year=year, month=month, increment_leave=False)

        assert result["success"]
        assert result["leave_updated"] == 0

        # Check that leave was NOT updated
        test_employee.refresh_from_db()
        assert test_employee.available_leave_days == Decimal("100.00")

    def test_prepare_timesheets_for_single_employee_does_not_update_global_leave(self, test_employee):
        """Test that prepare_monthly_timesheets for single employee doesn't update global leave counters."""
        test_employee.available_leave_days = Decimal("10.00")
        test_employee.save()

        year, month = 2025, 7
        result = prepare_monthly_timesheets(employee_id=test_employee.id, year=year, month=month)

        assert result["success"]
        assert "leave_updated" not in result

        # Check that leave was NOT updated via the bulk update mechanism
        test_employee.refresh_from_db()
        assert test_employee.available_leave_days == Decimal("10.00")


@pytest.mark.django_db
class TestLeaveCalculation:
    """Test specific leave calculation logic."""

    def test_start_date_partial_month(self, test_employee):
        """Test that generated leave is 0 if start date is in same month and day > 15."""
        # Modify contract effective date to after mid-month (day 16+)
        contract = test_employee.contracts.first()
        contract.effective_date = date(2025, 3, 16)
        contract.save()

        # Check March 2025 - should be 0 since start date is after the 15th
        gen = calculate_generated_leave(test_employee.id, 2025, 3)
        assert gen == Decimal("0.00")

        # Check April 2025 - should get leave
        gen_apr = calculate_generated_leave(test_employee.id, 2025, 4)
        assert gen_apr == Decimal("1.00")

    def test_start_date_first_of_month(self, test_employee):
        """Test that generated leave is calculated if start date is 1st of month."""
        contract = test_employee.contracts.first()
        contract.effective_date = date(2025, 3, 1)
        contract.save()

        # Check March 2025
        gen = calculate_generated_leave(test_employee.id, 2025, 3)
        assert gen == Decimal("1.00")

    def test_start_date_on_15th_gets_leave(self, test_employee):
        """Test that generated leave is calculated if start date is 15th of month."""
        contract = test_employee.contracts.first()
        contract.effective_date = date(2025, 3, 15)
        contract.save()

        # Check March 2025 - should get leave since day <= 15
        gen = calculate_generated_leave(test_employee.id, 2025, 3)
        assert gen == Decimal("1.00")

    def test_april_expiration_of_carried_over(self, test_employee):
        """Test that carried over leave expires in April if unused."""
        # Setup:
        # Jan 2025: Carried Over = 5.
        # Used Jan-Mar = 2.
        # April Opening should expire 3.

        # Create Jan timesheet
        EmployeeMonthlyTimesheet.objects.create(
            employee=test_employee,
            report_date=date(2025, 1, 1),
            month_key="202501",
            carried_over_leave=Decimal("5.00"),
            consumed_leave_days=Decimal("1.00"),
            remaining_leave_days=Decimal("4.00"),  # simplified
        )

        # Create Feb timesheet
        EmployeeMonthlyTimesheet.objects.create(
            employee=test_employee,
            report_date=date(2025, 2, 1),
            month_key="202502",
            consumed_leave_days=Decimal("1.00"),
            remaining_leave_days=Decimal("3.00"),
        )

        # Create Mar timesheet
        # Remaining from Feb is 3. New Gen=1. Consumed=0. Total Remaining = 4.
        EmployeeMonthlyTimesheet.objects.create(
            employee=test_employee,
            report_date=date(2025, 3, 1),
            month_key="202503",
            remaining_leave_days=Decimal("4.00"),
        )

        # Create Apr timesheet
        ts_apr = create_monthly_timesheet_for_employee(test_employee.id, 2025, 4)

        # Calculations:
        # Initial Carried (Jan) = 5.
        # Total Consumed Jan-Mar = 1+1+0 = 2.
        # Unused Carried = 5 - 2 = 3.
        # Prev Remaining (Mar) = 4.
        # Base Opening (Apr) = Prev Remaining - Unused Carried = 4 - 3 = 1.
        # Generated (Apr) = 1 (from contract: 12 annual leave days / 12 months).
        # Opening (Apr) = Base Opening + Generated = 1 + 1 = 2.

        assert ts_apr.opening_balance_leave_days == Decimal("2.00")
        assert ts_apr.carried_over_leave == Decimal("0.00")

    def test_refresh_updates_opening_balance(self, test_employee):
        """Test that refreshing a timesheet updates opening/generated balance based on contract/prev month."""
        year, month = 2025, 5

        # 1. Initial State: 12 days/year -> 1 day/month
        ts = create_monthly_timesheet_for_employee(test_employee.id, year, month)
        assert ts.generated_leave_days == Decimal("1.00")
        # Opening = Generated (1) + Prev Remaining (0) = 1
        assert ts.opening_balance_leave_days == Decimal("1.00")

        # 2. Modify Contract: 24 days/year -> 2 days/month
        contract = test_employee.contracts.first()
        contract.annual_leave_days = 24
        contract.save()

        # 3. Refresh
        refreshed_ts = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # 4. Verify
        assert refreshed_ts.generated_leave_days == Decimal("2.00")
        assert refreshed_ts.opening_balance_leave_days == Decimal("2.00")
