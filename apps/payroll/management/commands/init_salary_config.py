import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.payroll.models import SalaryConfig


def load_default_initial_data():
    """Load default salary configuration from initial_data file."""
    initial_data_path = Path(__file__).parent.parent.parent / "initial_data" / "default_salary_config.json"
    with open(initial_data_path, "r") as f:
        return json.load(f)


class Command(BaseCommand):
    help = "Initialize salary configuration with default initial_data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing configurations before creating new one",
        )

    def handle(self, *args, **options):
        reset = options.get("reset", False)

        # Load default initial_data from JSON file
        default_config = load_default_initial_data()

        if reset:
            # Delete all existing configurations
            count = SalaryConfig.objects.count()
            if count > 0:
                SalaryConfig.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Deleted {count} existing salary configuration(s)"))

        # Create new configuration with default initial_data
        config = SalaryConfig.objects.create(config=default_config)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created salary configuration v{config.version} with default initial_data"
            )
        )

        # Display summary
        self.stdout.write("\nConfiguration summary:")
        self.stdout.write(f"  - Insurance types: {len(default_config['insurance_contributions'])}")
        self.stdout.write(f"  - Tax brackets: {len(default_config['personal_income_tax']['progressive_levels'])}")
        self.stdout.write(f"  - KPI tiers: {len(default_config['kpi_salary']['tiers'])}")
        self.stdout.write(
            f"  - Business commission tiers: {len(default_config['business_progressive_salary']['tiers'])}"
        )
