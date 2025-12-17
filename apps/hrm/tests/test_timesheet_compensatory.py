from datetime import date, datetime, time

import pytest
from django.utils import timezone

from apps.hrm.constants import TimesheetStatus, TimesheetDayType
from apps.hrm.models.holiday import CompensatoryWorkday, Holiday
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

pytestmark = pytest.mark.django_db


def make_datetime(d: date, t: time):
    return timezone.make_aware(datetime.combine(d, t))


def test_compensatory_full_day_attendance_sets_on_time():
    # Holiday exists earlier; compensatory workday on a weekend
    holiday = Holiday.objects.create(name="H", start_date=date(2025, 12, 24), end_date=date(2025, 12, 25))
    comp_date = date(2025, 12, 27)  # Saturday
    CompensatoryWorkday.objects.create(holiday=holiday, date=comp_date, session=CompensatoryWorkday.Session.FULL_DAY)

    ts = TimeSheetEntry(employee_id=None, date=comp_date)
    ts.day_type = TimesheetDayType.COMPENSATORY  # Manually set day_type as we skip save()
    ts.start_time = make_datetime(comp_date, time(8, 0))
    ts.end_time = make_datetime(comp_date, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME


def test_compensatory_no_attendance_sets_absent():
    holiday = Holiday.objects.create(name="H2", start_date=date(2025, 12, 24), end_date=date(2025, 12, 25))
    comp_date = date(2025, 12, 28)  # Sunday
    CompensatoryWorkday.objects.create(holiday=holiday, date=comp_date, session=CompensatoryWorkday.Session.FULL_DAY)

    ts = TimeSheetEntry(employee_id=None, date=comp_date)
    ts.day_type = TimesheetDayType.COMPENSATORY  # Manually set day_type as we skip save()
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ABSENT


def test_compensatory_afternoon_only_attendance_sets_on_time():
    holiday = Holiday.objects.create(name="H3", start_date=date(2025, 12, 24), end_date=date(2025, 12, 25))
    comp_date = date(2025, 12, 27)  # Saturday
    CompensatoryWorkday.objects.create(holiday=holiday, date=comp_date, session=CompensatoryWorkday.Session.AFTERNOON)

    ts = TimeSheetEntry(employee_id=None, date=comp_date)
    ts.day_type = TimesheetDayType.COMPENSATORY  # Manually set day_type as we skip save()
    ts.start_time = make_datetime(comp_date, time(13, 0))
    ts.end_time = make_datetime(comp_date, time(17, 0))
    TimesheetCalculator(ts).compute_status()

    assert ts.status == TimesheetStatus.ON_TIME
