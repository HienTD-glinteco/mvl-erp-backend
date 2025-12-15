from datetime import date, datetime, time

import pytest
from django.utils import timezone

from apps.hrm.constants import TimesheetStatus
from apps.hrm.models.holiday import Holiday
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

pytestmark = pytest.mark.django_db


def make_datetime(d: date, t: time):
    return timezone.make_aware(datetime.combine(d, t))


def test_non_working_day_no_attendance_sets_status_none(settings):
    d = date(2025, 12, 7)  # Sunday

    ts = TimeSheetEntry(employee_id=None, date=d)
    TimesheetCalculator(ts).compute_status()

    assert ts.status is None


def test_non_working_day_with_attendance_sets_on_time(settings):
    d = date(2025, 12, 7)  # Sunday

    ts = TimeSheetEntry(employee_id=None, date=d)
    ts.start_time = make_datetime(d, time(9, 0))
    ts.end_time = make_datetime(d, time(12, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME


def test_holiday_no_attendance_sets_status_none(settings):
    d = date(2025, 12, 25)

    # Create a holiday covering the date
    Holiday.objects.create(name="Xmas", start_date=d, end_date=d)

    ts = TimeSheetEntry(employee_id=None, date=d)
    TimesheetCalculator(ts).compute_status()

    assert ts.status is None


def test_holiday_with_attendance_sets_on_time(settings):
    d = date(2025, 12, 25)

    Holiday.objects.create(name="Xmas", start_date=d, end_date=d)

    ts = TimeSheetEntry(employee_id=None, date=d)
    ts.start_time = make_datetime(d, time(8, 0))
    ts.end_time = make_datetime(d, time(12, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME
