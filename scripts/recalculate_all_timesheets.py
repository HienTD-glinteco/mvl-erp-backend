"""
Script to recalculate all timesheet entries with snapshot and compute_all.

Run with:
    poetry run python scripts/recalculate_all_timesheets.py

Uses 4 workers for parallel processing.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import close_old_connections

from apps.hrm.models import TimeSheetEntry
from apps.hrm.services.timesheet_calculator import TimesheetCalculator


def process_entry(entry_id):
    """Process a single entry - run snapshot and compute_all."""
    # Close stale connections at start of thread execution
    close_old_connections()
    try:
        entry = TimeSheetEntry.objects.get(id=entry_id)

        # Compute all metrics
        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=entry.is_work_day_finalizing())

        # Save changes
        entry.save()

        return entry_id, True, None
    except Exception as e:
        return entry_id, False, str(e)
    finally:
        # Close connections when returning to pool
        close_old_connections()


def recalculate_all_timesheets(num_workers=4):
    """Recalculate all timesheet entries using parallel workers."""
    entry_ids = list(TimeSheetEntry.objects.values_list("id", flat=True))
    total = len(entry_ids)

    print(f"Found {total} entries to process with {num_workers} workers...")

    success_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_entry, eid): eid for eid in entry_ids}

        for i, future in enumerate(as_completed(futures), 1):
            entry_id, success, error = future.result()

            if success:
                success_count += 1
            else:
                error_count += 1
                print(f"  Error on entry {entry_id}: {error}")

            if i % 100 == 0:
                print(f"  Progress: {i}/{total} ({i * 100 // total}%)")

    print(f"\nDone! Success: {success_count}, Errors: {error_count}")
