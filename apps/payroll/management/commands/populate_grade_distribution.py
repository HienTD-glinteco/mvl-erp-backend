"""Management command to populate grade_distribution for existing department assessments.

This command recalculates and populates the grade_distribution field for all
existing DepartmentKPIAssessment records based on employee grades.

Priority: grade_hrm > grade_manager
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment


class Command(BaseCommand):
    help = "Populate grade_distribution for existing department assessments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            type=int,
            help="Only populate for specific period ID",
        )
        parser.add_argument(
            "--department",
            type=int,
            help="Only populate for specific department ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )

    def handle(self, *args, **options):  # noqa: C901
        period_id = options.get("period")
        department_id = options.get("department")
        dry_run = options.get("dry_run")

        # Build queryset
        queryset = DepartmentKPIAssessment.objects.all()

        if period_id:
            queryset = queryset.filter(period_id=period_id)
            self.stdout.write(f"Filtering by period ID: {period_id}")

        if department_id:
            queryset = queryset.filter(department_id=department_id)
            self.stdout.write(f"Filtering by department ID: {department_id}")

        total = queryset.count()
        self.stdout.write(f"Found {total} department assessments to process")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for dept_assessment in queryset.select_related("period", "department"):
                # Count grades for this department and period
                # Priority: hrm_grade > manager_grade
                grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}

                employee_assessments = EmployeeKPIAssessment.objects.filter(
                    period=dept_assessment.period, employee__department=dept_assessment.department
                )

                for emp_assessment in employee_assessments:
                    grade = emp_assessment.grade_hrm or emp_assessment.grade_manager
                    if grade in grade_counts:
                        grade_counts[grade] += 1

                # Check if distribution changed
                if dept_assessment.grade_distribution != grade_counts:
                    old_distribution = dept_assessment.grade_distribution
                    dept_assessment.grade_distribution = grade_counts

                    if not dry_run:
                        dept_assessment.save(update_fields=["grade_distribution"])

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Updated {dept_assessment.department.name} "
                            f"({dept_assessment.period.month.strftime('%Y-%m')}): "
                            f"{old_distribution} → {grade_counts}"
                        )
                    )
                    updated_count += 1
                else:
                    skipped_count += 1

            if dry_run:
                # Rollback transaction in dry-run mode
                transaction.set_rollback(True)

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✓ Total processed: {total}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Updated: {updated_count}"))
        self.stdout.write(f"  Skipped (unchanged): {skipped_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No changes were saved"))
            self.stdout.write("Run without --dry-run to apply changes")
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Grade distribution populated successfully!"))
