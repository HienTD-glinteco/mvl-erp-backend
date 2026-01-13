"""Script to trigger sales revenue aggregation for all data."""

import os
import sys

import django
from django.utils import timezone

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from apps.payroll.models import SalesRevenue, SalesRevenueReportFlatModel
from apps.payroll.tasks import aggregate_sales_revenue_report_task


def run():
    """Run aggregation for all existing sales revenue data."""
    print("Starting sales revenue aggregation fix...")

    # Check current counts
    revenue_count = SalesRevenue.objects.count()
    report_count = SalesRevenueReportFlatModel.objects.count()
    print(f"Current SalesRevenue records: {revenue_count}")
    print(f"Current Report records: {report_count}")

    # Trigger aggregation (synchronously for the script by calling the aggregator directly?
    # No, let's use the task but maybe we can wait for it if we want result,
    # or just fire it. The task returns a dict.)

    # Since we are in a script, calling .delay() might just queue it if Celery is running,
    # or run eager if CELERY_TASK_ALWAYS_EAGER is True.
    # To be safe and see output, let's call the function directly (bypassing Celery wrapper)
    # or call the aggregator service directly.
    # But the plan said "trigger aggregate_sales_revenue_report_task.delay()".
    # However, running .delay() in a script without a worker might just do nothing if not eager.

    # Let's call the task function directly (it's decorated but still callable in Python usually,
    # or we can access the underlying function).
    # But actually, calling the task function directly `aggregate_sales_revenue_report_task()`
    # works in recent Celery versions as a normal function call if not using .delay().

    print("Triggering aggregation task (all months)...")
    try:
        # Calling without .delay executes it synchronously in the same process
        # (unless it's bound and uses self, but this one is shared_task without bind=True for this specific task?
        # Checking tasks.py: @shared_task def aggregate_sales_revenue_report_task(...) -> it is NOT bound)
        target_months = [
            timezone.datetime(2026, 1, 1).date().isoformat(),
            timezone.datetime(2025, 12, 1).date().isoformat(),
            timezone.datetime(2025, 11, 1).date().isoformat(),
        ]
        result = aggregate_sales_revenue_report_task()
        print(f"Task completed. Result: {result}")

        # Verify new count
        new_report_count = SalesRevenueReportFlatModel.objects.count()
        print(f"New Report records: {new_report_count}")
        print(f"Records added/updated: {new_report_count - report_count}")

    except Exception as e:
        print(f"Error executing task: {e}")


if __name__ == "__main__":
    run()
