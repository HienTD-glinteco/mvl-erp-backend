"""Management command to backfill employee_type - DEPRECATED.

This command was used to populate employee_type from historical contract_type values.
The contract_type field has been removed from the Employee model.
This command is kept for historical reference but is no longer functional.
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.hrm.constants import EmployeeType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Backfill employee_type field - DEPRECATED.

    This command was used to populate the employee_type field for Employee records
    from existing contract_type relationships. The contract_type field has been
    removed from the Employee model, so this command is no longer functional.

    This command is kept for historical reference only.
    """

    help = "DEPRECATED: Backfill employee_type field (contract_type has been removed)"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command arguments."""
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of employees to process per batch (default: 500)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the backfill without making changes",
        )
        parser.add_argument(
            "--output-csv",
            type=str,
            default="",
            help="Path to output audit CSV file",
        )
        parser.add_argument(
            "--include-unmapped",
            action="store_true",
            help="Include employees with unmapped values in CSV",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing employee_type values",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the backfill command."""
        self.stderr.write(
            self.style.WARNING(
                "This command is DEPRECATED. The contract_type field has been removed from "
                "the Employee model. The employee_type field should be populated directly "
                "during employee creation or import."
            )
        )
        self.stdout.write("")
        self.stdout.write("Available employee_type values:")
        for choice in EmployeeType.choices:
            self.stdout.write(f"  - {choice[0]}: {choice[1]}")
