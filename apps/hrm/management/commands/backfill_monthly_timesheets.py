from typing import List

from django.core.management.base import BaseCommand

from apps.hrm.models.employee import Employee
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet


class Command(BaseCommand):
    help = "Backfill employee monthly timesheets in batches"

    def add_arguments(self, parser):
        parser.add_argument("--start-year", type=int, required=True)
        parser.add_argument("--start-month", type=int, required=True)
        parser.add_argument("--end-year", type=int, required=True)
        parser.add_argument("--end-month", type=int, required=True)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true", help="Do not write to DB; just simulate", default=True)

    def handle(self, *args, **options):
        start_year = options["start_year"]
        start_month = options["start_month"]
        end_year = options["end_year"]
        end_month = options["end_month"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        # build months list
        months: List[tuple] = []
        y, m = start_year, start_month
        while (y, m) <= (end_year, end_month):
            months.append((y, m))
            if m == 12:
                y += 1
                m = 1
            else:
                m += 1

        self.stdout.write(f"Backfilling months: {months} (batch_size={batch_size}, dry_run={dry_run})")

        qs = Employee.objects.values_list("id", flat=True).order_by("id")
        buffer: List[int] = []
        processed = 0

        for emp_id in qs.iterator():
            buffer.append(emp_id)
            if len(buffer) >= batch_size:
                self._process_batch(buffer, months, dry_run)
                processed += len(buffer)
                self.stdout.write(f"Processed {processed} employees...")
                buffer = []

        # remaining
        if buffer:
            self._process_batch(buffer, months, dry_run)
            processed += len(buffer)

        self.stdout.write(self.style.SUCCESS(f"Backfill complete — processed {processed} employees."))

    def _process_batch(self, emp_ids: List[int], months: List[tuple], dry_run: bool = True) -> None:
        for emp_id in emp_ids:
            self._process_employee_batch(emp_id, months, dry_run)

    def _process_employee_batch(self, employee_id: int, months: list[tuple], dry_run: bool = True):
        for yr, mo in months:
            try:
                if dry_run:
                    # Compute only, do not persist
                    result = EmployeeMonthlyTimesheet.compute_aggregates(employee_id, yr, mo)
                    self.stdout.write(
                        self.style.SUCCESS(f"Result for Employee id: {employee_id}, year: {yr}, month: {mo}: {result}")
                    )
                else:
                    EmployeeMonthlyTimesheet.refresh_for_employee_month(employee_id, yr, mo)
            except Exception as exc:  # pragma: no cover - operational error handling
                # Fail fast: log and re-raise so the operator can see the problem
                self.stderr.write(f"Error processing employee {employee_id} {yr}-{mo}: {exc}")
                raise
