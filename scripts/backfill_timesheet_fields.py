import os
import sys
import django
from django.conf import settings

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.base")  # Adjust if settings path is different
django.setup()

from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

def backfill_timesheets():
    """
    Backfill snapshot fields and recalculate metrics for all existing timesheet entries.
    """
    print("Starting backfill process...")

    entries = TimeSheetEntry.objects.all().order_by('date')
    total = entries.count()
    print(f"Found {total} entries to process.")

    snapshot_service = TimesheetSnapshotService()

    count = 0
    for entry in entries.iterator(chunk_size=1000):
        try:
            # 1. Backfill Snapshot Data
            snapshot_service.snapshot_data(entry)

            # 2. Recalculate Logic (using new Calculator)
            calc = TimesheetCalculator(entry)
            calc.compute_all()

            entry.save()
            count += 1
            if count % 100 == 0:
                print(f"Processed {count}/{total} entries...")
        except Exception as e:
            print(f"Error processing entry {entry.id}: {e}")

    print("Backfill completed.")

if __name__ == "__main__":
    backfill_timesheets()
