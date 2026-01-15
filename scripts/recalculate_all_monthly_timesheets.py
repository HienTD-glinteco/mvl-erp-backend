"""
Script to recalculate all monthly timesheets with updated leave balance logic.

Run with:
    cd /home/dev/Projects/Work/maivietland/backend && source venv/bin/activate
    python scripts/recalculate_all_monthly_timesheets.py

This script:
1. Iterates through all existing EmployeeMonthlyTimesheet records
2. Recalculates opening_balance_leave_days and remaining_leave_days using new logic
3. Processes months in chronological order to ensure correct carry-over

IMPORTANT: Monthly timesheets MUST be processed in chronological order (year/month)
because opening_balance depends on the previous month's remaining_leave_days.
"""

import os
import sys

import django

# Setup Django before imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from collections import defaultdict

from apps.hrm.models import Employee, EmployeeMonthlyTimesheet
from apps.hrm.services.timesheets import create_monthly_timesheet_for_employee  # noqa: E402


def recalculate_all_monthly_timesheets():
    """Recalculate all monthly timesheets with new leave balance logic."""
    # Get all unique (employee_id, year, month) combinations, ordered chronologically
    records = (
        EmployeeMonthlyTimesheet.objects.all()
        .values_list("employee_id", "report_date__year", "report_date__month")
        .order_by("report_date__year", "report_date__month", "employee_id")
    )

    # Group by (year, month) to process in correct order
    months_map = defaultdict(list)
    for emp_id, year, month in records:
        months_map[(year, month)].append(emp_id)

    total_months = len(months_map)
    print(f"Found {total_months} unique months to process...")

    processed = 0
    errors = 0

    for (year, month), employee_ids in sorted(months_map.items()):
        print(f"\nProcessing {year}/{month:02d} ({len(employee_ids)} employees)...")

        for emp_id in employee_ids:
            try:
                create_monthly_timesheet_for_employee(emp_id, year, month)
                processed += 1
            except Exception as e:
                print(f"  Error for employee {emp_id}: {e}")
                errors += 1

        print(f"  Done {year}/{month:02d}")

    print("\n=== Summary ===")
    print(f"Processed: {processed}")
    print(f"Errors: {errors}")


def recalculate_for_year(year: int):
    """Recalculate all monthly timesheets for a specific year."""
    employees = Employee.objects.exclude(status=Employee.Status.RESIGNED)
    emp_ids = list(employees.values_list("id", flat=True))

    print(f"Recalculating for {len(emp_ids)} employees, year {year}...")

    for month in range(1, 13):
        print(f"\nProcessing {year}/{month:02d}...")
        count = 0
        for emp_id in emp_ids:
            try:
                create_monthly_timesheet_for_employee(emp_id, year, month)
                count += 1
            except Exception as e:
                print(f"  Error for employee {emp_id}: {e}")

        print(f"  Done: {count} records")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Recalculate monthly timesheets")
    parser.add_argument("--year", type=int, help="Specific year to recalculate")
    parser.add_argument("--all", action="store_true", help="Recalculate all existing records")

    args = parser.parse_args()

    if args.year:
        recalculate_for_year(args.year)
    elif args.all:
        recalculate_all_monthly_timesheets()
    else:
        print("Usage:")
        print("  python scripts/recalculate_all_monthly_timesheets.py --all")
        print("  python scripts/recalculate_all_monthly_timesheets.py --year 2026")
