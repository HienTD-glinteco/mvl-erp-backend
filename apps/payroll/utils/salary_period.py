"""Utility functions for salary period management."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from apps.hrm.models.holiday import Holiday


def calculate_standard_working_days(year: int, month: int) -> Decimal:
    """Calculate standard working days in a month.

    Calculates the total number of working days (weekdays excluding holidays)
    in a given month.

    Args:
        year: Year of the month
        month: Month number (1-12)

    Returns:
        Decimal: Number of standard working days in the month
    """
    # Get first and last day of month
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # Count weekdays (Monday=0 to Friday=4)
    working_days = 0
    current_date = first_day

    while current_date <= last_day:
        # Monday=0, Sunday=6
        if current_date.weekday() < 5:  # Monday to Friday
            working_days += 1
        current_date += timedelta(days=1)

    # Subtract holidays that fall on weekdays
    holidays = Holiday.objects.filter(start_date__lte=last_day, end_date__gte=first_day)

    for holiday in holidays:
        # Get the overlap between holiday and the month
        holiday_start = max(holiday.start_date, first_day)
        holiday_end = min(holiday.end_date, last_day)

        current_date = holiday_start
        while current_date <= holiday_end:
            # Only subtract if it's a weekday
            if current_date.weekday() < 5:
                working_days -= 1

            current_date += timedelta(days=1)

    return Decimal(str(working_days))


def generate_salary_period_code(year: int, month: int) -> str:
    """Generate salary period code in format SP-YYYYMM.

    Args:
        year: Year of the salary period
        month: Month number (1-12)

    Returns:
        str: Generated code (e.g., "SP-202401")
    """
    return f"SP-{year:04d}{month:02d}"
