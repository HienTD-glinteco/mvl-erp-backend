import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.payroll.models import SalaryConfig


def load_default_fixtures():
    """Load default salary configuration from fixtures file."""
    fixtures_path = Path(__file__).parent.parent.parent / "fixtures" / "default_salary_config.json"
    with open(fixtures_path, "r") as f:
        return json.load(f)


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

        # Load default fixtures from JSON file
        default_config = load_default_fixtures()

        if reset:
            # Delete all existing configurations
            count = SalaryConfig.objects.count()
            if count > 0:
                SalaryConfig.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Deleted {count} existing salary configuration(s)"))

        # Create new configuration with default fixtures
        config = SalaryConfig.objects.create(config=default_config)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created salary configuration v{config.version} with default fixtures")
        )

        # Display summary
        self.stdout.write("\nConfiguration summary:")
        self.stdout.write(f"  - Insurance types: {len(default_config['insurance_contributions'])}")
        self.stdout.write(f"  - Tax brackets: {len(default_config['personal_income_tax']['progressive_levels'])}")
        self.stdout.write(f"  - KPI tiers: {len(default_config['kpi_salary']['tiers'])}")
        self.stdout.write(
            f"  - Business commission tiers: {len(default_config['business_progressive_salary']['tiers'])}"
        )
