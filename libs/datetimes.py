from datetime import datetime
from fractions import Fraction

from django.utils import timezone


# Helper to compute intersection duration in hours (as Fraction)
def compute_intersection_hours(start_a, end_a, start_b, end_b):
    latest_start = max(start_a, start_b)
    earliest_end = min(end_a, end_b)
    if latest_start < earliest_end:
        duration_seconds = (earliest_end - latest_start).total_seconds()
        return Fraction(int(duration_seconds), 3600)
    return Fraction(0)


def make_aware(dt):
    if not dt:
        return

    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt)


def combine_datetime(date, time):
    if not time:
        return
    dt = datetime.combine(date, time)
    return make_aware(dt)
