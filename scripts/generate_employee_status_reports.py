#!/usr/bin/env python3
"""
Generate synthetic EmployeeStatusBreakdownReport data for testing.

Usage (from repo root):
  python scripts/generate_employee_status_reports.py --days 300 --start-date 2024-01-01 --seed 42

This script bootstraps Django using the project's settings and then
creates/updates EmployeeStatusBreakdownReport rows for every Department
found in the database for a consecutive range of dates.

Notes:
- Filters out departments missing block/branch references.
- Distributes resigned counts across Employee.ResignationReason values.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.local")

import django

django.setup()

from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.hrm.models.employee import Employee  # noqa: E402
from apps.hrm.models.employee_report import EmployeeStatusBreakdownReport  # noqa: E402
from apps.hrm.models.organization import Department  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate EmployeeStatusBreakdownReport test data")
    p.add_argument("--days", type=int, default=300, help="Number of consecutive days to generate (default: 300)")
    p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="ISO start date YYYY-MM-DD. Defaults to today - days + 1",
    )
    p.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible data")
    return p.parse_args()


def distribute_resigned_reasons(count_resigned: int, resignation_reasons: list) -> dict:
    """Distribute resigned counts across resignation reasons."""
    remaining = count_resigned
    reasons_dist: dict = {}
    if resignation_reasons:
        for i, reason in enumerate(resignation_reasons):
            if i == len(resignation_reasons) - 1:
                reasons_dist[reason] = remaining
            else:
                v = random.randint(0, remaining)
                reasons_dist[reason] = v
                remaining -= v
    return reasons_dist


def generate_random_counts() -> dict:
    """Generate random employee counts for different statuses."""
    return {
        "count_active": random.randint(0, 200),
        "count_onboarding": random.randint(0, 20),
        "count_maternity_leave": random.randint(0, 5),
        "count_unpaid_leave": random.randint(0, 5),
        "count_resigned": random.randint(0, 10),
    }


def process_department_report(dept, report_date, resignation_reasons):
    """Process a single department report for a given date."""
    block = getattr(dept, "block", None)
    branch = getattr(block, "branch", None) if block else None

    if block is None or branch is None:
        return None

    counts = generate_random_counts()
    total_not_resigned = (
        counts["count_active"]
        + counts["count_onboarding"]
        + counts["count_maternity_leave"]
        + counts["count_unpaid_leave"]
    )

    reasons_dist = distribute_resigned_reasons(counts["count_resigned"], resignation_reasons)

    defaults = {
        **counts,
        "total_not_resigned": total_not_resigned,
        "count_resigned_reasons": reasons_dist,
    }

    obj, created = EmployeeStatusBreakdownReport.objects.update_or_create(
        report_date=report_date,
        branch=branch,
        block=block,
        department=dept,
        defaults=defaults,
    )
    return created


def main():
    args = parse_args()
    days = args.days
    seed = args.seed

    if seed is not None:
        random.seed(seed)

    today = timezone.localdate()
    if args.start_date:
        try:
            start = datetime.fromisoformat(args.start_date).date()
        except Exception:
            print("Invalid start-date format, expected YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)
    else:
        start = today - timedelta(days=days - 1)

    departments = list(Department.objects.select_related("block__branch").all())
    if not departments:
        print("No departments found. Aborting.")
        return

    resignation_reasons = [c.value for c in Employee.ResignationReason]
    dates = [start + timedelta(days=i) for i in range(days)]

    processed = 0
    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for report_date in dates:
            for dept in departments:
                created = process_department_report(dept, report_date, resignation_reasons)
                if created is not None:
                    processed += 1
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

    print(
        f"Processed {processed} report entries for {days} days and {len(departments)} departments. "
        f"Created: {created_count}; Updated: {updated_count}"
    )


if __name__ == "__main__":
    main()
