"""Management command to generate monthly KPI assessments.

This command generates KPI assessments for employees and departments for a specified month.
It creates snapshots of current KPI criteria and initializes assessments with default values.

Example usage:
    python manage.py generate_kpi_assessments --month 2025-12 --target sales
    python manage.py generate_kpi_assessments --month 2025-12 --all
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hrm.models import Department, Employee
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
    KPICriterion,
)
from apps.payroll.utils import (
    create_assessment_items_from_criteria,
    recalculate_assessment_scores,
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

        # Generate employee assessments
        self.generate_employee_assessments(
            period=period,
            targets=targets,
            employee_ids_str=employee_ids_str,
            skip_existing=skip_existing,
        )

        # Generate department assessments
        self.generate_department_assessments(
            period=period,
            department_ids_str=department_ids_str,
            skip_existing=skip_existing,
        )

        self.stdout.write(self.style.SUCCESS("Assessment generation completed successfully"))

    def generate_employee_assessments(
        self,
        period,
        targets,
        employee_ids_str=None,
        skip_existing=True,
    ):
        """Generate employee KPI assessments."""
        self.stdout.write("\n--- Generating Employee Assessments ---")

        created_count = 0
        skipped_count = 0
        error_count = 0

        for target in targets:
            self.stdout.write(f"\nProcessing target: {target}")

            # Get active criteria for target
            criteria = KPICriterion.objects.filter(target=target, active=True).order_by("evaluation_type", "order")

            if not criteria.exists():
                self.stdout.write(self.style.WARNING(f"No active criteria found for target: {target}"))
                continue

            self.stdout.write(f"Found {criteria.count()} active criteria")

            # Get employees based on target
            # Target 'sales' = employees where department.function == BUSINESS
            # Target 'backoffice' = employees where department.function != BUSINESS
            employees_qs = Employee.objects.exclude(status=Employee.Status.RESIGNED)

            if target == "sales":
                employees_qs = employees_qs.filter(department__function=Department.DepartmentFunction.BUSINESS)
            elif target == "backoffice":
                employees_qs = employees_qs.exclude(department__function=Department.DepartmentFunction.BUSINESS)

            if employee_ids_str:
                try:
                    employee_ids = [int(x.strip()) for x in employee_ids_str.split(",")]
                    employees_qs = employees_qs.filter(id__in=employee_ids)
                except ValueError:
                    raise CommandError("Invalid employee_ids format")

            self.stdout.write(f"Found {employees_qs.count()} employees for target {target}")

            # Process each employee
            for employee in employees_qs:
                try:
                    # Check if assessment exists
                    if (
                        skip_existing
                        and EmployeeKPIAssessment.objects.filter(
                            employee=employee,
                            period=period,
                        ).exists()
                    ):
                        skipped_count += 1
                        continue

                    with transaction.atomic():
                        # Create assessment
                        assessment = EmployeeKPIAssessment.objects.create(
                            employee=employee,
                            period=period,
                        )

                        # Create items from criteria
                        create_assessment_items_from_criteria(assessment, list(criteria))

                        # Calculate totals
                        recalculate_assessment_scores(assessment)

                        created_count += 1
                        self.stdout.write(f"  ✓ Created assessment for {employee.code} - {employee.user.username}")

                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ Error creating assessment for {employee.code}: {str(e)}"))

        self.stdout.write("\nEmployee Assessments Summary:")
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Errors: {error_count}")

    def generate_department_assessments(
        self,
        period,
        department_ids_str=None,
        skip_existing=True,
    ):
        """Generate department KPI assessments."""
        self.stdout.write("\n--- Generating Department Assessments ---")

        # Get departments
        departments_qs = Department.objects.filter(is_active=True)
        if department_ids_str:
            try:
                department_ids = [int(x.strip()) for x in department_ids_str.split(",")]
                departments_qs = departments_qs.filter(id__in=department_ids)
            except ValueError:
                raise CommandError("Invalid department_ids format")

        created_count = 0
        skipped_count = 0
        error_count = 0

        for department in departments_qs:
            try:
                # Check if assessment exists
                if (
                    skip_existing
                    and DepartmentKPIAssessment.objects.filter(
                        department=department,
                        period=period,
                    ).exists()
                ):
                    skipped_count += 1
                    continue

                # Create department assessment with default grade 'C'
                DepartmentKPIAssessment.objects.create(
                    department=department,
                    period=period,
                    grade="C",
                    default_grade="C",
                )

                created_count += 1
                self.stdout.write(f"  ✓ Created assessment for {department.name}")

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"  ✗ Error creating assessment for {department.name}: {str(e)}"))

        self.stdout.write("\nDepartment Assessments Summary:")
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Errors: {error_count}")
