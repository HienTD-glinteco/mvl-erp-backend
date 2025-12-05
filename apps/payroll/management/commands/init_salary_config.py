from django.core.management.base import BaseCommand

from apps.payroll.models import SalaryConfig

# Default fixtures for salary configuration
DEFAULT_SALARY_CONFIG = {
    "insurance_contributions": {
        "social_insurance": {"employee_rate": 0.08, "employer_rate": 0.17, "salary_ceiling": 46800000},
        "health_insurance": {"employee_rate": 0.015, "employer_rate": 0.03, "salary_ceiling": 46800000},
        "unemployment_insurance": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
        "union_fee": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
        "accident_occupational_insurance": {"employee_rate": 0, "employer_rate": 0.005, "salary_ceiling": None},
    },
    "personal_income_tax": {
        "standard_deduction": 11000000,
        "dependent_deduction": 4400000,
        "progressive_levels": [
            {"up_to": 5000000, "rate": 0.05},
            {"up_to": 10000000, "rate": 0.1},
            {"up_to": 18000000, "rate": 0.15},
            {"up_to": 32000000, "rate": 0.2},
            {"up_to": 52000000, "rate": 0.25},
            {"up_to": 80000000, "rate": 0.3},
            {"up_to": None, "rate": 0.35},
        ],
    },
    "kpi_salary": {
        "apply_on": "base_salary",
        "tiers": [
            {"code": "A", "percentage": 0.1, "description": "Excellent"},
            {"code": "B", "percentage": 0.05, "description": "Good"},
            {"code": "C", "percentage": 0, "description": "Average"},
            {"code": "D", "percentage": -0.05, "description": "Below Average"},
        ],
    },
    "business_progressive_salary": {
        "apply_on": "base_salary",
        "tiers": [
            {
                "code": "M0",
                "amount": 0,
                "criteria": [{"name": "transaction_count", "min": 1}, {"name": "revenue", "min": 50000000}],
            },
            {
                "code": "M1",
                "amount": 7000000,
                "criteria": [{"name": "transaction_count", "min": 2}, {"name": "revenue", "min": 200000000}],
            },
            {
                "code": "M2",
                "amount": 9000000,
                "criteria": [{"name": "transaction_count", "min": 3}, {"name": "revenue", "min": 300000000}],
            },
            {
                "code": "M3",
                "amount": 11000000,
                "criteria": [{"name": "transaction_count", "min": 4}, {"name": "revenue", "min": 400000000}],
            },
            {
                "code": "M4",
                "amount": 13000000,
                "criteria": [{"name": "transaction_count", "min": 5}, {"name": "revenue", "min": 500000000}],
            },
        ],
    },
}


class Command(BaseCommand):
    help = "Initialize salary configuration with default fixtures"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing configurations before creating new one",
        )

    def handle(self, *args, **options):
        reset = options.get("reset", False)

        if reset:
            # Delete all existing configurations
            count = SalaryConfig.objects.count()
            if count > 0:
                SalaryConfig.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Deleted {count} existing salary configuration(s)"))

        # Create new configuration with default fixtures
        config = SalaryConfig.objects.create(config=DEFAULT_SALARY_CONFIG)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created salary configuration v{config.version} with default fixtures")
        )

        # Display summary
        self.stdout.write("\nConfiguration summary:")
        self.stdout.write(f"  - Insurance types: {len(DEFAULT_SALARY_CONFIG['insurance_contributions'])}")
        self.stdout.write(
            f"  - Tax brackets: {len(DEFAULT_SALARY_CONFIG['personal_income_tax']['progressive_levels'])}"
        )
        self.stdout.write(f"  - KPI tiers: {len(DEFAULT_SALARY_CONFIG['kpi_salary']['tiers'])}")
        self.stdout.write(
            f"  - Business commission tiers: {len(DEFAULT_SALARY_CONFIG['business_progressive_salary']['tiers'])}"
        )
