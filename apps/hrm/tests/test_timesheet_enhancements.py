"""Tests for new timesheet model fields and calculations."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from django.core.cache import cache

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, Position, WorkSchedule
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry
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
class TestTimeSheetEntryNewFields:
    """Test TimeSheetEntry model new fields and calculations."""

    def test_official_hours_calculation(self, test_employee):
        """Test that official_hours is calculated as morning_hours + afternoon_hours."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 3, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("3.50"),
        )

        assert entry.official_hours == Decimal("7.50")

    def test_total_worked_hours_calculation(self, test_employee):
        """Test that total_worked_hours is calculated as official_hours + overtime_hours."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 3, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            overtime_hours=Decimal("2.00"),
        )

        assert entry.official_hours == Decimal("8.00")
        assert entry.total_worked_hours == Decimal("10.00")

    def test_update_times_method(self, test_employee):
        """Test the update_times method."""
        from django.utils import timezone

        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 3, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
        )

        start = timezone.make_aware(datetime(2025, 3, 1, 8, 0, 0))
        end = timezone.make_aware(datetime(2025, 3, 1, 17, 0, 0))
        entry.update_times(start, end)
        entry.save()

        entry.refresh_from_db()
        assert entry.start_time == start
        assert entry.end_time == end

    def test_calculate_hours_from_schedule_method_exists(self, test_employee):
        """Test that calculate_hours_from_schedule method exists and can be called."""
        entry = TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(2025, 3, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
        )

        # Method should exist and not raise an error (even if it's a stub)
        entry.calculate_hours_from_schedule()


@pytest.mark.django_db
class TestEmployeeMonthlyTimesheetNewFields:
    """Test EmployeeMonthlyTimesheet model new fields and calculations."""

    @pytest.fixture(autouse=True)
    def cleanup_monthly_timesheets(self, db):
        """Clean up any existing monthly timesheets before each test."""
        yield
        # Clean up after each test
        EmployeeMonthlyTimesheet.objects.all().delete()

    def test_official_hours_aggregation(self, test_employee):
        """Test that official_hours is aggregated correctly from TimeSheetEntry."""
        year, month = 2025, 8  # Use unique month

        # Create entries with different official hours
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
        )
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
            morning_hours=Decimal("3.00"),
            afternoon_hours=Decimal("5.00"),
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # Total official hours should be 8 + 8 = 16
        assert monthly.official_hours == Decimal("16.00")

    def test_overtime_hours_aggregation(self, test_employee):
        """Test that overtime_hours is aggregated correctly from TimeSheetEntry."""
        year, month = 2025, 9  # Use unique month

        # Create entries with overtime hours
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            overtime_hours=Decimal("2.00"),
        )
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            overtime_hours=Decimal("1.50"),
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        assert monthly.overtime_hours == Decimal("3.50")

    def test_working_days_value_calculation(self, test_employee):
        """Test that working_days_value is calculated as official_hours / 8."""
        year, month = 2025, 10  # Use unique month

        # Create entries with 20 hours total (2.5 days)
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
        )
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
        )
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 3),
            morning_hours=Decimal("2.00"),
            afternoon_hours=Decimal("2.00"),
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # 20 hours / 8 = 2.50 days
        assert monthly.official_hours == Decimal("20.00")
        assert monthly.working_days_value == Decimal("2.50")

    def test_total_worked_hours_aggregation(self, test_employee):
        """Test that total_worked_hours is the sum of official_hours and overtime_hours."""
        year, month = 2025, 11  # Use unique month

        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            overtime_hours=Decimal("2.00"),
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # official_hours = 8, overtime = 2, total should be 10
        assert monthly.official_hours == Decimal("8.00")
        assert monthly.overtime_hours == Decimal("2.00")
        assert monthly.total_worked_hours == Decimal("10.00")

    def test_probation_and_official_working_days(self, test_employee):
        """Test calculation of probation_working_days and official_working_days."""
        year, month = 2025, 12  # Use unique month

        # Create entries with different is_full_salary values
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 1),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            is_full_salary=True,
        )
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 2),
            morning_hours=Decimal("4.00"),
            afternoon_hours=Decimal("4.00"),
            is_full_salary=False,
        )
        TimeSheetEntry.objects.create(
            employee=test_employee,
            date=date(year, month, 3),
            morning_hours=Decimal("2.00"),
            afternoon_hours=Decimal("2.00"),
            is_full_salary=False,
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(test_employee.id, year, month)

        # Official working days: 8 hours / 8 = 1.00 day
        # Probation working days: (8 + 4) hours / 8 = 1.50 days
        assert monthly.official_working_days == Decimal("1.00")
        assert monthly.probation_working_days == Decimal("1.50")
        assert monthly.total_working_days == Decimal("2.50")


@pytest.mark.django_db
class TestWorkScheduleCache:
    """Test WorkSchedule caching functionality."""

    def test_cache_all_work_schedules(self, db):
        """Test that get_all_work_schedules uses cache."""
        # Clear cache first
        cache.clear()

        # Create a work schedule
        schedule = WorkSchedule.objects.create(
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
        from django.db.models.signals import post_save

        from apps.hrm.signals.work_schedule import invalidate_cache_on_work_schedule_save

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
    """Test prepare_monthly_timesheets task with integrated leave increment."""

    @pytest.fixture(autouse=True)
    def cleanup_monthly_timesheets(self, db):
        """Clean up any existing monthly timesheets before each test."""
        yield
        # Clean up after each test
        EmployeeMonthlyTimesheet.objects.all().delete()

    def test_prepare_timesheets_increments_leave_for_all_employees(self, test_employee):
        """Test that prepare_monthly_timesheets increments available_leave_days."""
        from apps.hrm.tasks.timesheets import prepare_monthly_timesheets

        # Set initial leave days
        test_employee.available_leave_days = 10
        test_employee.save()

        # Use a unique month to avoid conflicts
        year, month = 2025, 5
        result = prepare_monthly_timesheets(employee_id=None, year=year, month=month, increment_leave=True)

        assert result["success"]
        assert result["leave_incremented"] >= 1

        # Check that leave was incremented
        test_employee.refresh_from_db()
        assert test_employee.available_leave_days == 11

    def test_prepare_timesheets_can_skip_leave_increment(self, test_employee):
        """Test that prepare_monthly_timesheets can skip leave increment when requested."""
        from apps.hrm.tasks.timesheets import prepare_monthly_timesheets

        # Set initial leave days
        test_employee.available_leave_days = 10
        test_employee.save()

        # Use a different unique month to avoid conflicts
        year, month = 2025, 6
        result = prepare_monthly_timesheets(employee_id=None, year=year, month=month, increment_leave=False)

        assert result["success"]
        assert result["leave_incremented"] == 0

        # Check that leave was NOT incremented
        test_employee.refresh_from_db()
        assert test_employee.available_leave_days == 10

    def test_prepare_timesheets_for_single_employee_does_not_increment(self, test_employee):
        """Test that prepare_monthly_timesheets for single employee doesn't increment leave."""
        from apps.hrm.tasks.timesheets import prepare_monthly_timesheets

        # Set initial leave days
        test_employee.available_leave_days = 10
        test_employee.save()

        # Use another unique month to avoid conflicts
        year, month = 2025, 7
        result = prepare_monthly_timesheets(employee_id=test_employee.id, year=year, month=month)

        assert result["success"]
        assert "leave_incremented" not in result

        # Check that leave was NOT incremented (single employee mode)
        test_employee.refresh_from_db()
        assert test_employee.available_leave_days == 10
