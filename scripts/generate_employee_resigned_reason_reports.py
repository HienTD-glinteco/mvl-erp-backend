#!/usr/bin/env python3
"""
Generate synthetic EmployeeResignedReasonReport data for testing.

Usage (from repo root):
  python scripts/generate_employee_resigned_reason_reports.py --days 300 --start-date 2024-01-01 --seed 42

This script bootstraps Django using the project's settings and then
creates/updates EmployeeResignedReasonReport rows for every Department
found in the database for a consecutive range of dates.

Notes:
- Filters out departments missing block/branch references.
- Distributes resigned counts across 12 fixed resignation reason columns.
"""

import argparse
import random
import sys
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.hrm.models.employee import Employee
from apps.hrm.models.employee_report import EmployeeResignedReasonReport
from apps.hrm.models.organization import Department

# Mapping from Employee.ResignationReason enum values to EmployeeResignedReasonReport field names
REASON_FIELD_MAP = {
    Employee.ResignationReason.AGREEMENT_TERMINATION: "agreement_termination",
    Employee.ResignationReason.PROBATION_FAIL: "probation_fail",
    Employee.ResignationReason.JOB_ABANDONMENT: "job_abandonment",
    Employee.ResignationReason.DISCIPLINARY_TERMINATION: "disciplinary_termination",
    Employee.ResignationReason.WORKFORCE_REDUCTION: "workforce_reduction",
    Employee.ResignationReason.UNDERPERFORMING: "underperforming",
    Employee.ResignationReason.CONTRACT_EXPIRED: "contract_expired",
    Employee.ResignationReason.VOLUNTARY_HEALTH: "voluntary_health",
    Employee.ResignationReason.VOLUNTARY_PERSONAL: "voluntary_personal",
    Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE: "voluntary_career_change",
    Employee.ResignationReason.VOLUNTARY_OTHER: "voluntary_other",
    Employee.ResignationReason.OTHER: "other",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate EmployeeResignedReasonReport test data")
    p.add_argument("--days", type=int, default=300, help="Number of consecutive days to generate (default: 300)")
    p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="ISO start date YYYY-MM-DD. Defaults to today - days + 1",
    )
    p.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible data")
    return p.parse_args()


def main():  # noqa: C901
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

    # Collect resignation reason enum values
    resignation_reasons = list(Employee.ResignationReason)

    dates = [start + timedelta(days=i) for i in range(days)]

    processed = 0
    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for report_date in dates:
            for dept in departments:
                block = getattr(dept, "block", None)
                branch = getattr(block, "branch", None) if block else None

                if block is None or branch is None:
                    # skip departments without full hierarchy
                    continue

                # Generate total resigned count (0 to 10 per day)
                count_resigned = random.randint(0, 10)

                # Distribute resigned count across the 12 reason fields
                remaining = count_resigned
                reason_counts = {}

                for i, reason_enum in enumerate(resignation_reasons):
                    field_name = REASON_FIELD_MAP[reason_enum]
                    if i == len(resignation_reasons) - 1:
                        # Last reason gets all remaining
                        reason_counts[field_name] = remaining
                    else:
                        # Random allocation
                        v = random.randint(0, remaining)
                        reason_counts[field_name] = v
                        remaining -= v

                # Build defaults dict with all 12 reason fields
                defaults = {
                    "count_resigned": count_resigned,
                    "agreement_termination": reason_counts.get("agreement_termination", 0),
                    "probation_fail": reason_counts.get("probation_fail", 0),
                    "job_abandonment": reason_counts.get("job_abandonment", 0),
                    "disciplinary_termination": reason_counts.get("disciplinary_termination", 0),
                    "workforce_reduction": reason_counts.get("workforce_reduction", 0),
                    "underperforming": reason_counts.get("underperforming", 0),
                    "contract_expired": reason_counts.get("contract_expired", 0),
                    "voluntary_health": reason_counts.get("voluntary_health", 0),
                    "voluntary_personal": reason_counts.get("voluntary_personal", 0),
                    "voluntary_career_change": reason_counts.get("voluntary_career_change", 0),
                    "voluntary_other": reason_counts.get("voluntary_other", 0),
                    "other": reason_counts.get("other", 0),
                }

                obj, created = EmployeeResignedReasonReport.objects.update_or_create(
                    report_date=report_date,
                    branch=branch,
                    block=block,
                    department=dept,
                    defaults=defaults,
                )

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
