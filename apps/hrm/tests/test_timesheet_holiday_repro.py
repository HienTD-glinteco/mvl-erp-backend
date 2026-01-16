from datetime import date, time
from decimal import Decimal

import pytest

from apps.hrm.constants import TimesheetDayType
from apps.hrm.models import Holiday, TimeSheetEntry, WorkSchedule
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService


@pytest.mark.django_db
class TestHolidayWorkingDays:
    @pytest.fixture
    def full_day_schedule(self):
        return WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
            is_morning_required=True,
            is_afternoon_required=True,
        )

    @pytest.fixture
    def half_day_schedule(self):
        return WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.SATURDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            # No afternoon
            is_morning_required=True,
            is_afternoon_required=False,
        )

    @pytest.fixture(autouse=True)
    def setup_schedules(self, full_day_schedule, half_day_schedule):
        pass

    def test_holiday_on_full_working_day(self, employee):
        """Holiday on a full working day (Monday) should give 1.0 working days."""
        d = date(2026, 1, 12)  # A Monday
        assert d.weekday() == 0

        Holiday.objects.create(start_date=d, end_date=d, name="Test Holiday Full")

        entry = TimeSheetEntry.objects.create(employee=employee, date=d)

        # Snapshot to detect holiday
        snapshot = TimesheetSnapshotService()
        snapshot.snapshot_data(entry)
        entry.save()  # Persist day_type

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)

        assert entry.day_type == TimesheetDayType.HOLIDAY
        assert entry.working_days == Decimal("1.00")

    def test_holiday_on_half_working_day(self, employee):
        """Holiday on a half working day (Saturday) should give 0.5 working days."""
        d = date(2026, 1, 10)  # A Saturday
        assert d.weekday() == 5

        Holiday.objects.create(start_date=d, end_date=d, name="Test Holiday Half")

        entry = TimeSheetEntry.objects.create(employee=employee, date=d)

        # Snapshot to detect holiday
        snapshot = TimesheetSnapshotService()
        snapshot.snapshot_data(entry)
        entry.save()  # Persist day_type

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)

        assert entry.day_type == TimesheetDayType.HOLIDAY
        # This assertion is expected to fail currently, as logic returns 1.00
        assert entry.working_days == Decimal("0.50"), f"Expected 0.50 but got {entry.working_days}"
