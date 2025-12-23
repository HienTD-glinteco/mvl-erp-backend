import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.payroll.models import KPIConfig


def load_default_initial_data():
    """Load default KPI configuration from initial_data file."""
    initial_data_path = Path(__file__).parent.parent.parent / "initial_data" / "default_kpi_config.json"
    with open(initial_data_path, "r") as f:
        return json.load(f)


class Command(BaseCommand):
    help = "Initialize KPI configuration with default initial_data"

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
            count = KPIConfig.objects.count()
            if count > 0:
                KPIConfig.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Deleted {count} existing KPI configuration(s)"))

        # Create new configuration with default initial_data
        config = KPIConfig.objects.create(config=default_config)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created KPI configuration v{config.version} with default initial_data")
        )

        # Display summary
        self.stdout.write("\nConfiguration summary:")
        self.stdout.write(f"  - Name: {default_config['name']}")
        self.stdout.write(f"  - Ambiguous assignment policy: {default_config['ambiguous_assignment']}")
        self.stdout.write(f"  - Grade thresholds: {len(default_config['grade_thresholds'])}")
        self.stdout.write(f"  - Unit types: {len(default_config['unit_control'])}")
