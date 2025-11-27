"""Management command to backfill employee_type from contract_type."""

import csv
import logging
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.hrm.constants import EmployeeType
from apps.hrm.models import Employee
from apps.hrm.utils.employee_type_mapping import (
    get_employee_type_mapping,
    load_custom_mapping_from_file,
    map_contract_type_to_employee_type,
    suggest_employee_type,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Backfill employee_type field from existing contract_type relationships.

    This command populates the employee_type field for Employee records
    that have a contract_type FK set but no employee_type value.

    Features:
    - Safe, idempotent operation (can be run multiple times)
    - Batch processing with configurable batch size
    - Dry-run mode for testing
    - Audit CSV output for tracking changes
    - Custom mapping file support
    - Summary statistics at completion
    """

    help = "Backfill employee_type field from contract_type relationships"

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
            help="Path to output audit CSV file (default: backfill_employee_type_TIMESTAMP.csv)",
        )
        parser.add_argument(
            "--custom-mapping",
            type=str,
            default="",
            help="Path to custom mapping JSON file",
        )
        parser.add_argument(
            "--include-unmapped",
            action="store_true",
            help="Include employees with unmapped contract_type in CSV (for review)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing employee_type values (default: skip if already set)",
        )

    def _load_custom_mapping(self, custom_mapping_path: str) -> dict[str, str] | None:
        """Load custom mapping from file if path is provided."""
        if not custom_mapping_path:
            return None

        mapping_data = load_custom_mapping_from_file(custom_mapping_path)
        if mapping_data:
            custom_mapping = mapping_data.get("name_mapping", mapping_data)
            self.stdout.write(f"Loaded custom mapping from {custom_mapping_path}")
            return custom_mapping

        self.stderr.write(
            self.style.WARNING(f"Could not load custom mapping from {custom_mapping_path}")
        )
        return None

    def _process_employee(
        self,
        employee: Employee,
        custom_mapping: dict[str, str] | None,
        force: bool,
        dry_run: bool,
        stats: dict,
        unmapped_contract_types: dict[str, int],
    ) -> tuple[Employee | None, list]:
        """Process a single employee and return update info."""
        stats["processed"] += 1
        csv_row = []

        contract_type = employee.contract_type
        contract_type_name = contract_type.name if contract_type else None
        contract_type_pk = contract_type.pk if contract_type else None

        # Skip if already has employee_type and not forcing
        if employee.employee_type and not force:
            stats["skipped_already_set"] += 1
            return None, csv_row

        # Try to map contract_type to employee_type
        employee_type, was_mapped = map_contract_type_to_employee_type(
            contract_type_name=contract_type_name,
            contract_type_pk=contract_type_pk,
            custom_mapping=custom_mapping,
        )

        old_employee_type = employee.employee_type

        if was_mapped and employee_type:
            # Found mapping - update employee
            if not dry_run:
                employee.employee_type = employee_type

            stats["updated"] += 1
            status = "updated" if not dry_run else "would_update"
            csv_row = [
                employee.id, employee.code, employee.fullname,
                contract_type_pk, contract_type_name, old_employee_type or "",
                employee_type, status, "",
            ]
            return employee if not dry_run else None, csv_row

        # No mapping found
        stats["skipped_no_mapping"] += 1

        # Track unmapped contract types
        suggestion = None
        if contract_type_name:
            unmapped_contract_types[contract_type_name] = (
                unmapped_contract_types.get(contract_type_name, 0) + 1
            )
            suggestion = suggest_employee_type(contract_type_name)

        csv_row = [
            employee.id, employee.code, employee.fullname,
            contract_type_pk, contract_type_name, old_employee_type or "",
            "", "no_mapping", suggestion or "",
        ]
        return None, csv_row

    def _print_summary(
        self, stats: dict, unmapped_contract_types: dict, dry_run: bool, output_csv: str
    ) -> None:
        """Print the backfill summary."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Backfill Summary"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Total processed:        {stats['processed']}")
        self.stdout.write(f"Updated:                {stats['updated']}")
        self.stdout.write(f"Skipped (no mapping):   {stats['skipped_no_mapping']}")
        self.stdout.write(f"Skipped (already set):  {stats['skipped_already_set']}")
        self.stdout.write(f"Errors:                 {stats['errors']}")

        if not dry_run:
            self.stdout.write(f"\nAudit CSV written to: {output_csv}")

        if unmapped_contract_types:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Unmapped contract types:"))
            for ct_name, count in sorted(unmapped_contract_types.items(), key=lambda x: -x[1]):
                suggestion = suggest_employee_type(ct_name)
                suggestion_str = f" (suggested: {suggestion})" if suggestion else ""
                self.stdout.write(f"  - {ct_name}: {count} employees{suggestion_str}")

        self.stdout.write("")
        self.stdout.write("Available employee_type values:")
        for choice in EmployeeType.choices:
            self.stdout.write(f"  - {choice[0]}: {choice[1]}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("DRY RUN - No changes were made"))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Backfill completed successfully"))

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: C901
        """Execute the backfill command."""
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        output_csv = options["output_csv"]
        include_unmapped = options["include_unmapped"]
        force = options["force"]

        # Generate default CSV path if not provided
        if not output_csv:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_csv = f"backfill_employee_type_{timestamp}.csv"

        custom_mapping = self._load_custom_mapping(options["custom_mapping"])

        # Get current mapping for display
        full_mapping = get_employee_type_mapping(custom_mapping)
        self.stdout.write(f"Using mapping with {len(full_mapping)} entries")

        # Build queryset
        queryset = Employee.objects.select_related("contract_type")
        if not force:
            queryset = queryset.filter(employee_type__isnull=True)
        queryset = queryset.filter(contract_type__isnull=False)

        total_count = queryset.count()
        self.stdout.write(
            f"Found {total_count} employees to process "
            f"(dry_run={dry_run}, force={force}, batch_size={batch_size})"
        )

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No employees to process"))
            return

        stats = {"processed": 0, "updated": 0, "skipped_no_mapping": 0, "skipped_already_set": 0, "errors": 0}
        unmapped_contract_types: dict[str, int] = {}

        csv_file = None
        csv_writer = None
        if not dry_run or include_unmapped:
            csv_file = open(output_csv, "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                "employee_id", "employee_code", "employee_fullname", "contract_type_id",
                "contract_type_name", "old_employee_type", "new_employee_type", "status", "suggestion",
            ])

        try:
            employee_ids = list(queryset.values_list("id", flat=True).order_by("id"))
            processed = 0

            for i in range(0, len(employee_ids), batch_size):
                batch_ids = employee_ids[i : i + batch_size]
                batch_employees = Employee.objects.select_related("contract_type").filter(id__in=batch_ids)
                updates = []

                for employee in batch_employees:
                    updated_emp, csv_row = self._process_employee(
                        employee, custom_mapping, force, dry_run, stats, unmapped_contract_types
                    )
                    if updated_emp:
                        updates.append(updated_emp)
                    if csv_row and csv_writer:
                        if stats.get("_last_was_mapped", True) or include_unmapped:
                            csv_writer.writerow(csv_row)
                        stats["_last_was_mapped"] = csv_row[7] != "no_mapping"

                if updates and not dry_run:
                    with transaction.atomic():
                        Employee.objects.bulk_update(updates, ["employee_type"])

                processed += len(batch_ids)
                self.stdout.write(f"Processed {processed}/{total_count} employees...")

        except Exception as e:
            logger.exception(f"Error during backfill: {e}")
            stats["errors"] += 1
            self.stderr.write(self.style.ERROR(f"Error during backfill: {e}"))
            raise
        finally:
            if csv_file:
                csv_file.close()

        self._print_summary(stats, unmapped_contract_types, dry_run, output_csv)
