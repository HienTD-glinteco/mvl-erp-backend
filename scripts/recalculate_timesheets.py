from datetime import date, timedelta
from apps.hrm.models import TimeSheetEntry, Employee
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
import logging

logger = logging.getLogger(__name__)

def recalculate_timesheets_range(employee_id=None, start_date=None, end_date=None):
    """
    Recalculate timesheets for a given range.
    If employee_id is None, processes all employees.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = TimeSheetEntry.objects.filter(date__gte=start_date, date__lte=end_date)

    if employee_id:
        query = query.filter(employee_id=employee_id)

    entries = query.all()
    count = 0
    total = entries.count()

    print(f"Recalculating {total} entries from {start_date} to {end_date}...")

    for entry in entries:
        try:
            # Check if this is a "finalize" pass or just a refresh
            # Usually for historical data, we treat it as finalized if date < today
            is_finalizing = entry.date < date.today()

            calc = TimesheetCalculator(entry)
            calc.compute_all(is_finalizing=is_finalizing)
            entry.save()
            count += 1
            if count % 100 == 0:
                print(f"Processed {count}/{total}")
        except Exception as e:
            print(f"Error processing entry {entry.id}: {e}")

    print(f"Done. Recalculated {count} entries.")

if __name__ == "__main__":
    # This block allows running the script standalone if Django environment is setup,
    # but typically you'd run this via: python manage.py shell < scripts/recalculate_timesheets.py
    # or import it in a shell.
    pass
