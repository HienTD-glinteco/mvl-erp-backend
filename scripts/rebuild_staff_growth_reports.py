#!/usr/bin/env python
"""Rebuild StaffGrowthReport data with deduplication logic.

Usage:
    poetry run python scripts/rebuild_staff_growth_reports.py [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD]

Example:
    poetry run python scripts/rebuild_staff_growth_reports.py --from-date 2025-01-01 --to-date 2026-01-31
"""
import argparse
import os
import sys
from datetime import date, timedelta

import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from django.db import transaction
from django.db.models import F

from apps.hrm.models import (
    Employee,
    EmployeeWorkHistory,
    RecruitmentCandidate,
    StaffGrowthEventLog,
    StaffGrowthReport,
)


def get_timeframe_keys(event_date: date) -> tuple[str, str]:
    """Calculate week_key and month_key from date."""
    week_number = event_date.isocalendar()[1]
    year = event_date.isocalendar()[0]
    week_key = f"W{week_number:02d}-{year}"
    month_key = event_date.strftime("%m/%Y")
    return week_key, month_key


def _get_timeframe_keys_in_range(from_date: date, to_date: date) -> list[str]:
    """Generate list of timeframe keys for date range."""
    keys = []
    current = from_date

    # Week keys
    while current <= to_date:
        week_number = current.isocalendar()[1]
        year = current.isocalendar()[0]
        keys.append(f"W{week_number:02d}-{year}")
        current += timedelta(days=7)

    current = from_date.replace(day=1)
    # Month keys
    while current <= to_date:
        keys.append(current.strftime("%m/%Y"))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    return list(set(keys))


def _record_staff_growth_event(employee, event_type, event_date, branch, block, department):
    """Record event with deduplication (same logic as helpers.py)."""
    week_key, month_key = get_timeframe_keys(event_date)

    counter_field_map = {
        "resignation": "num_resignations",
        "transfer": "num_transfers",
        "return": "num_returns",
        "introduction": "num_introductions",
        "recruitment_source": "num_recruitment_source",
    }
    counter_field = counter_field_map[event_type]

    timeframes = [
        (StaffGrowthReport.TimeframeType.WEEK, week_key),
        (StaffGrowthReport.TimeframeType.MONTH, month_key),
    ]

    for timeframe_type, timeframe_key in timeframes:
        report, _ = StaffGrowthReport.objects.get_or_create(
            timeframe_type=timeframe_type,
            timeframe_key=timeframe_key,
            branch=branch,
            block=block,
            department=department,
            defaults={"report_date": event_date}
        )

        _, log_created = StaffGrowthEventLog.objects.get_or_create(
            report=report,
            employee=employee,
            event_type=event_type,
            defaults={"event_date": event_date},
        )

        if log_created:
            StaffGrowthReport.objects.filter(pk=report.pk).update(
                **{counter_field: F(counter_field) + 1}
            )


def rebuild_reports(from_date: date, to_date: date, dry_run: bool = False):
    """Rebuild StaffGrowthReport from EmployeeWorkHistory and RecruitmentCandidate."""
    print(f"Rebuilding StaffGrowthReport from {from_date} to {to_date}")

    if not dry_run:
        # Clear existing data for affected timeframes only
        keys = _get_timeframe_keys_in_range(from_date, to_date)
        print(f"Clearing existing data for {len(keys)} timeframes...")

        # StaffGrowthEventLog has CASCADE delete from StaffGrowthReport
        StaffGrowthReport.objects.filter(timeframe_key__in=keys).delete()

    # 1. Process EmployeeWorkHistory events (Resignations, Transfers, Returns)
    events = EmployeeWorkHistory.objects.filter(
        date__range=(from_date, to_date),
    ).select_related("employee", "branch", "block", "department")

    print(f"Processing {events.count()} work history events...")

    # Process each event type
    event_mappings = [
        # (filter_kwargs, event_type)
        ({"name": EmployeeWorkHistory.EventType.TRANSFER}, "transfer"),
        (
            {
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "status": Employee.Status.RESIGNED,
            },
            "resignation",
        ),
    ]

    # Process mapped events
    for filter_kwargs, event_type in event_mappings:
        filtered_events = events.filter(**filter_kwargs)
        print(f"  Processing {filtered_events.count()} {event_type} events...")

        for event in filtered_events:
            # Check OS code type
            if event.employee.code_type == Employee.CodeType.OS:
                continue

            if dry_run:
                print(f"    Would record: {event.employee.code} - {event_type} - {event.date}")
            else:
                _record_staff_growth_event(
                    employee=event.employee,
                    event_type=event_type,
                    event_date=event.date,
                    branch=event.branch,
                    block=event.block,
                    department=event.department,
                )

    # Process Returns (Special case)
    return_events = events.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.ACTIVE
    )

    count_returns = 0
    for event in return_events:
        if event.employee.code_type == Employee.CodeType.OS:
            continue

        prev_status = (event.previous_data or {}).get("status")
        if prev_status in Employee.Status.get_leave_statuses():
            if dry_run:
                print(f"    Would record: {event.employee.code} - return - {event.date}")
            else:
                _record_staff_growth_event(
                    employee=event.employee,
                    event_type="return",
                    event_date=event.date,
                    branch=event.branch,
                    block=event.block,
                    department=event.department,
                )
            count_returns += 1

    print(f"  Processing {count_returns} return events...")

    # 2. Process RecruitmentCandidate events (Hires: Introductions and Recruitment Sources)
    # Filter candidates HIRED within the date range
    candidates = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date__range=(from_date, to_date),
    ).select_related(
        "recruitment_source",
        "branch", "block", "department"
    ).prefetch_related("employees") # Need to access related employee

    print(f"Processing {candidates.count()} hired candidates...")

    count_introductions = 0
    count_recruitment_source = 0
    count_skipped_no_employee = 0

    for candidate in candidates:
        if not candidate.onboard_date:
            continue

        # Determine event type
        is_referral = candidate.recruitment_source and candidate.recruitment_source.allow_referral
        event_type = "introduction" if is_referral else "recruitment_source"

        # Find linked employee
        # Since 'employees' is a reverse relation, use .first()
        employee = candidate.employees.first()

        if not employee:
            # Try to find by ID if direct relation fails or not prefetched correctly
            employee = Employee.objects.filter(recruitment_candidate=candidate).first()

        if not employee:
            if dry_run:
                print(f"    SKIPPED (No Employee): Candidate {candidate.id} - {event_type} - {candidate.onboard_date}")
            count_skipped_no_employee += 1
            continue

        if employee.code_type == Employee.CodeType.OS:
            continue

        if dry_run:
            print(f"    Would record: {employee.code} - {event_type} - {candidate.onboard_date}")
        else:
            _record_staff_growth_event(
                employee=employee,
                event_type=event_type,
                event_date=candidate.onboard_date,
                branch=candidate.branch,
                block=candidate.block,
                department=candidate.department,
            )

        if event_type == "introduction":
            count_introductions += 1
        else:
            count_recruitment_source += 1

    print(f"  Processing {count_introductions} introduction events...")
    print(f"  Processing {count_recruitment_source} recruitment source events...")
    if count_skipped_no_employee > 0:
        print(f"  WARNING: Skipped {count_skipped_no_employee} candidates because no linked Employee record was found.")

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild StaffGrowthReport data")
    parser.add_argument("--from-date", type=str, default="2020-01-01") # Default broad range
    parser.add_argument("--to-date", type=str, default="2030-12-31")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")

    args = parser.parse_args()

    from_date = date.fromisoformat(args.from_date)
    to_date = date.fromisoformat(args.to_date)

    with transaction.atomic():
        rebuild_reports(from_date, to_date, dry_run=args.dry_run)
