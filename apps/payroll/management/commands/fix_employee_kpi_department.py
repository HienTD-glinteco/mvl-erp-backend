"""Management command to fix department field in EmployeeKPIAssessment records.

This command populates the department field for existing EmployeeKPIAssessment records
based on the employee's current department. This is a one-time data migration after adding
the department field to track department snapshots.

Note: This uses the employee's CURRENT department. If historical accuracy is critical
and employees have changed departments, manual review may be needed.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.payroll.models import EmployeeKPIAssessment


class Command(BaseCommand):
    help = "Fix department field in EmployeeKPIAssessment records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            type=int,
            help="Only fix records for specific period ID",
        )
        parser.add_argument(
            "--employee",
            type=int,
            help="Only fix records for specific employee ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of records to update per batch (default: 500)",
        )

    def handle(self, *args, **options):  # noqa: C901
        period_id = options.get("period")
        employee_id = options.get("employee")
        dry_run = options.get("dry_run")
        batch_size = options.get("batch_size")

        # Build queryset for records with NULL department_snapshot
        queryset = EmployeeKPIAssessment.objects.filter(department_snapshot__isnull=True).select_related(
            "employee", "employee__department", "period"
        )

        if period_id:
            queryset = queryset.filter(period_id=period_id)
            self.stdout.write(f"Filtering by period ID: {period_id}")

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
            self.stdout.write(f"Filtering by employee ID: {employee_id}")

        total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✓ All EmployeeKPIAssessment records already have department set!"))
            return

        self.stdout.write(f"Found {total} employee KPI assessments with NULL department")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        updated_count = 0
        skipped_count = 0
        error_count = 0

        # Process in batches for better performance
        for offset in range(0, total, batch_size):
            batch = queryset[offset : offset + batch_size]

            with transaction.atomic():
                for assessment in batch:
                    try:
                        if not assessment.employee:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"✗ Assessment ID {assessment.id}: No employee linked (orphaned record)"
                                )
                            )
                            error_count += 1
                            continue

                        if not assessment.employee.department:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"⚠ Assessment ID {assessment.id}: Employee {assessment.employee.code} "
                                    f"has no department - skipping"
                                )
                            )
                            skipped_count += 1
                            continue

                        # Set department from employee's current department
                        old_dept = assessment.department_snapshot
                        new_dept = assessment.employee.department

                        assessment.department_snapshot = new_dept

                        if not dry_run:
                            assessment.save(update_fields=["department_snapshot"])

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Assessment ID {assessment.id}: Employee {assessment.employee.code} "
                                f"({assessment.period.month.strftime('%Y-%m')}) → {new_dept.name}"
                            )
                        )
                        updated_count += 1

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"✗ Error processing assessment ID {assessment.id}: {str(e)}")
                        )
                        error_count += 1

                if dry_run:
                    # Rollback transaction in dry-run mode
                    transaction.set_rollback(True)

            # Progress update for large datasets
            if (offset + batch_size) < total:
                processed = min(offset + batch_size, total)
                self.stdout.write(f"Processed {processed}/{total}...")

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✓ Total found: {total}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Updated: {updated_count}"))
        self.stdout.write(f"  Skipped (no department): {skipped_count}")

        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Errors: {error_count}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No changes were saved"))
            self.stdout.write("Run without --dry-run to apply changes")
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Department field fixed successfully!"))

            # Suggest updating grade distribution after fixing departments
            self.stdout.write(
                "\nNote: You may want to run 'populate_grade_distribution' command "
                "to update department grade distributions with the corrected data."
            )
