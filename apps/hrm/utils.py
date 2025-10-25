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
