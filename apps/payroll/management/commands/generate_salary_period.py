"""Management command to generate salary period for a specific month."""

from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError

from apps.hrm.models import Employee
from apps.payroll.models import PayrollSlip, SalaryConfig, SalaryPeriod
from apps.payroll.services.payroll_calculation import PayrollCalculationService


class Command(BaseCommand):
    """Management command to generate salary period."""

    help = "Generate salary period for a specific month"

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            type=str,
            help="Month in YYYY-MM format (e.g., 2024-01). If not provided, generates for next month.",
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Delete existing salary period and payroll slips for this month and regenerate",
        )

    def handle(self, *args, **options):
        """Execute command."""
        month_str = options.get("month")
        override = options.get("override", False)

        # Determine target month
        if month_str:
            try:
                year, month = map(int, month_str.split("-"))
                target_month = date(year, month, 1)
            except (ValueError, TypeError):
                raise CommandError("Invalid month format. Use YYYY-MM (e.g., 2024-01)")
        else:
            # Default to next month
            today = date.today()
            target_month = (today + relativedelta(months=1)).replace(day=1)

        self.stdout.write(f"Target month: {target_month.strftime('%Y-%m')}")

        # Check if period exists
        existing_period = SalaryPeriod.objects.filter(month=target_month).first()

        if existing_period and not override:
            raise CommandError(
                f"Salary period for {target_month.strftime('%Y-%m')} already exists. "
                "Use --override flag to delete and regenerate."
            )

        if existing_period and override:
            self.stdout.write(
                self.style.WARNING(f"Deleting existing salary period for {target_month.strftime('%Y-%m')}...")
            )
            # Delete payroll slips first (cascade will handle it, but being explicit)
            PayrollSlip.objects.filter(salary_period=existing_period).delete()
            existing_period.delete()
            self.stdout.write(self.style.SUCCESS("Deleted existing period and payroll slips"))

        # Get latest salary config
        salary_config = SalaryConfig.objects.first()
        if not salary_config:
            raise CommandError("No salary configuration found. Please create one first.")

        self.stdout.write(f"Using salary config ID: {salary_config.id}")

        # Create new period
        salary_period = SalaryPeriod.objects.create(
            month=target_month, salary_config_snapshot=salary_config.config, created_by=None
        )

        self.stdout.write(self.style.SUCCESS(f"Created salary period: {salary_period.code}"))

        # Get employees to create payroll slips for
        # Include all employees except RESIGNED, and RESIGNED employees with resignation_start_date in this period
        active_employees = Employee.objects.exclude(status=Employee.Status.RESIGNED)
        resigned_in_period = Employee.objects.filter(
            status=Employee.Status.RESIGNED,
            resignation_start_date__year=target_month.year,
            resignation_start_date__month=target_month.month,
        )
        employees = active_employees | resigned_in_period

        self.stdout.write(f"Creating payroll slips for {employees.count()} employees...")

        created_count = 0
        for employee in employees:
            payroll_slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)

            # Calculate payroll immediately
            calculator = PayrollCalculationService(payroll_slip)
            calculator.calculate()

            created_count += 1

            if created_count % 10 == 0:
                self.stdout.write(f"  Created and calculated {created_count} payroll slips...")

        # Update employee count
        salary_period.total_employees = created_count
        salary_period.save(update_fields=["total_employees"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully generated salary period for {target_month.strftime('%Y-%m')}:\n"
                f"  - Period code: {salary_period.code}\n"
                f"  - Standard working days: {salary_period.standard_working_days}\n"
                f"  - Total employees: {created_count}\n"
                f"  - All payroll slips calculated"
            )
        )
