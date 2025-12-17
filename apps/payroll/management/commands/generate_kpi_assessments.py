"""Management command to generate monthly KPI assessments.

This command generates KPI assessments for employees and departments for a specified month.
It creates snapshots of current KPI criteria and initializes assessments with default values.

Example usage:
    python manage.py generate_kpi_assessments --month 2025-12 --target sales
    python manage.py generate_kpi_assessments --month 2025-12 --all
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.payroll.models import (
    KPIAssessmentPeriod,
    KPIConfig,
)
from apps.payroll.utils import (
    generate_department_assessments_for_period,
    generate_employee_assessments_for_period,
)


class Command(BaseCommand):
    """Management command to generate monthly KPI assessments."""

    help = "Generate monthly KPI assessments for employees and departments"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--month",
            type=str,
            required=True,
            help="Month in YYYY-MM format (e.g., 2025-12)",
        )
        parser.add_argument(
            "--target",
            type=str,
            help="Target group (sales/backoffice) - generates assessments only for this target",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Generate for all targets",
        )
        parser.add_argument(
            "--employee-ids",
            type=str,
            help="Comma-separated employee IDs to generate for (optional)",
        )
        parser.add_argument(
            "--department-ids",
            type=str,
            help="Comma-separated department IDs to generate for (optional)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Skip if assessment already exists (default: True)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        month_str = options["month"]
        target = options.get("target")
        generate_all = options.get("all")
        employee_ids_str = options.get("employee_ids")
        department_ids_str = options.get("department_ids")
        skip_existing = options.get("skip_existing")

        # Parse month
        try:
            year, month = map(int, month_str.split("-"))
            month_date = date(year, month, 1)
        except (ValueError, AttributeError):
            raise CommandError("Invalid month format. Use YYYY-MM (e.g., 2025-12)")

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            raise CommandError("No KPI configuration found. Please create one first.")

        self.stdout.write(f"Generating KPI assessments for {month_str}")
        self.stdout.write(f"Using KPI Config version: {kpi_config.version}")

        # Create or get assessment period
        period, created = KPIAssessmentPeriod.objects.get_or_create(
            month=month_date,
            defaults={
                "kpi_config_snapshot": kpi_config.config,
                "finalized": False,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created new assessment period for {month_str}"))
        else:
            self.stdout.write(f"Using existing assessment period for {month_str}")

        # Determine targets
        targets = []
        if generate_all:
            targets = ["sales", "backoffice"]
        elif target:
            targets = [target]
        else:
            raise CommandError("Please specify --target or --all")

        # Parse employee IDs if provided
        employee_ids = None
        if employee_ids_str:
            try:
                employee_ids = [int(x.strip()) for x in employee_ids_str.split(",")]
            except ValueError:
                raise CommandError("Invalid employee_ids format")

        # Parse department IDs if provided
        department_ids = None
        if department_ids_str:
            try:
                department_ids = [int(x.strip()) for x in department_ids_str.split(",")]
            except ValueError:
                raise CommandError("Invalid department_ids format")

        # Generate employee assessments
        self.stdout.write("\n--- Generating Employee Assessments ---")
        employee_count = generate_employee_assessments_for_period(
            period=period,
            targets=targets,
            employee_ids=employee_ids,
            skip_existing=skip_existing,
        )
        self.stdout.write(f"Created {employee_count} employee assessments")

        # Generate department assessments
        self.stdout.write("\n--- Generating Department Assessments ---")
        department_count = generate_department_assessments_for_period(
            period=period,
            department_ids=department_ids,
            skip_existing=skip_existing,
        )
        self.stdout.write(f"Created {department_count} department assessments")

        self.stdout.write(self.style.SUCCESS("\nAssessment generation completed successfully"))
