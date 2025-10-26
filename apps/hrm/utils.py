"""Utility functions for HRM module."""

from datetime import date, timedelta

from django.utils.translation import gettext as _


def get_experience_category(years_of_experience):
    """Categorize years of experience into predefined ranges.

    Args:
        years_of_experience: Number of years of work experience

    Returns:
        str: Experience category label
    """
    if years_of_experience is None:
        return _("Unknown")

    if years_of_experience < 1:
        return _("0-1 years")
    elif years_of_experience < 3:
        return _("1-3 years")
    elif years_of_experience < 5:
        return _("3-5 years")
    else:
        return _("5+ years")


def get_current_month_range():
    """Get the first and last day of the current month.

    Returns:
        tuple: (first_day, last_day) of current month
    """
    today = date.today()
    first_day = date(today.year, today.month, 1)

    # Get last day of month
    if today.month == 12:
        last_day = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)

    return first_day, last_day


def get_current_week_range():
    """Get the first (Monday) and last (Sunday) day of the current week.

    Returns:
        tuple: (monday, sunday) of current week
    """
    today = date.today()
    # Monday is 0, Sunday is 6
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    return monday, sunday


def get_last_6_months_range():
    """
    Get the first day of the month 6 months ago and the last day of the current month.

    Returns:
        tuple: (first_day, last_day) covering the last 6 full months up to the end of this month.
    """
    today = date.today()
    # Calculate the first day of the month 6 months ago
    year = today.year
    month = today.month - 5  # include current month as the 6th
    if month <= 0:
        year -= 1
        month += 12
    first_day = date(year, month, 1)

    # Calculate the last day of the current month
    if today.month == 12:
        last_day = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)

    return first_day, last_day


def get_week_key_from_date(report_date):
    """Generate week key from a date.

    Week key format: "Tuần W - MM/YYYY" where W is the week number in the month.

    Args:
        report_date: A date object

    Returns:
        str: Week key in format "Tuần W - MM/YYYY" (e.g., "Tuần 1 - 07/2025")
    """
    # Get the Monday of the week containing report_date
    monday = report_date - timedelta(days=report_date.weekday())

    # Calculate week number within the month
    # Week 1 starts on the first Monday of the month
    first_day_of_month = date(monday.year, monday.month, 1)
    first_monday = first_day_of_month
    while first_monday.weekday() != 0:  # 0 is Monday
        first_monday += timedelta(days=1)

    # Calculate week number
    if monday < first_monday:
        # This week spans the previous month
        # Use the previous month and its last week
        if monday.month == 1:
            prev_month = 12
            prev_year = monday.year - 1
        else:
            prev_month = monday.month - 1
            prev_year = monday.year

        # Get the last day of previous month
        last_day_prev_month = first_day_of_month - timedelta(days=1)
        # Get its Monday
        prev_monday = last_day_prev_month - timedelta(days=last_day_prev_month.weekday())
        return get_week_key_from_date(prev_monday)

    week_diff = (monday - first_monday).days
    week_number = (week_diff // 7) + 1

    return f"Tuần {week_number} - {monday.month:02d}/{monday.year}"


def get_week_label_from_date_range(start_date, end_date):
    """Generate week label from date range.

    Args:
        start_date: Monday of the week
        end_date: Sunday of the week

    Returns:
        str: Week label in format "DD/MM - DD/MM" (e.g., "12/05 - 18/05")
    """
    return f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}"
