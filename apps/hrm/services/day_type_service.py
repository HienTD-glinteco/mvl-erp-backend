from datetime import date, timedelta
from typing import Dict, Optional

from apps.hrm.constants import TimesheetDayType
from apps.hrm.models.holiday import CompensatoryWorkday, Holiday
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday


def get_day_type_map(start_date: date, end_date: date) -> Dict[date, Optional[str]]:
    """
    Return a map of {date: day_type} for the given range.
    Precedence: COMPENSATORY > HOLIDAY > OFFICIAL > None
    """
    day_map: Dict[date, Optional[str]] = {}

    # Initialize all dates with None or OFFICIAL based on WorkSchedule
    curr = start_date
    while curr <= end_date:
        weekday = curr.isoweekday() + 1  # 1..7 -> 2..8
        ws = get_work_schedule_by_weekday(weekday)
        if ws:
            day_map[curr] = TimesheetDayType.OFFICIAL
        else:
            day_map[curr] = None
        curr += timedelta(days=1)

    # Apply Holidays
    # Optimize: Filter holidays overlapping the range
    holidays = Holiday.objects.filter(start_date__lte=end_date, end_date__gte=start_date)
    for holiday in holidays:
        # Determine intersection of holiday and requested range
        h_start = max(holiday.start_date, start_date)
        h_end = min(holiday.end_date, end_date)

        # Iterate intersection
        d = h_start
        while d <= h_end:
            day_map[d] = TimesheetDayType.HOLIDAY
            d += timedelta(days=1)

    # Apply Compensatory Workdays
    compensatory_days = CompensatoryWorkday.objects.filter(date__range=(start_date, end_date))
    for cw in compensatory_days:
        day_map[cw.date] = TimesheetDayType.COMPENSATORY

    return day_map
