"""Management command to migrate FileModel paths to include storage prefix."""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.files.models import FileModel
from apps.files.utils import S3FileUploadService
from apps.files.utils.storage_utils import get_storage_prefix

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Migrate FileModel file_path values to REMOVE storage prefix.

    This command scans all FileModel records and removes the storage prefix
    (AWS_LOCATION) from file_path values. The prefix should NOT be stored in
    the database because default_storage automatically adds it when accessing files.

    This fixes the issue where default_storage.open(file_path) was failing because
    it was double-prefixing: default_storage adds prefix to "media/uploads/file.pdf"
    resulting in "media/media/uploads/file.pdf" in S3.

    Usage:
        # Dry run (report what would be changed)
        python manage.py files_migrate_paths --dry-run

        # Apply changes
        python manage.py files_migrate_paths --apply

        # Limit number of records to process
        python manage.py files_migrate_paths --apply --limit 100
    """

    help = "Migrate FileModel file_path values to remove storage prefix"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be changed without making changes",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the migration changes",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of records to process (for testing)",
        )

    def handle(self, *args, **options):  # noqa: C901
        """Execute the migration command."""
        dry_run = options["dry_run"]
        apply = options["apply"]
        limit = options["limit"]

        if not dry_run and not apply:
            self.stdout.write(self.style.ERROR("Must specify either --dry-run or --apply"))
            return

        if dry_run and apply:
            self.stdout.write(self.style.ERROR("Cannot specify both --dry-run and --apply"))
            return

        # Get storage prefix
        prefix = get_storage_prefix()

        if not prefix:
            self.stdout.write(self.style.WARNING("No storage prefix configured (AWS_LOCATION is empty)"))
            self.stdout.write("Migration not needed.")
            return

        self.stdout.write(f"Storage prefix: '{prefix}'")
        self.stdout.write(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
        if limit:
            self.stdout.write(f"Limit: {limit} records")
        self.stdout.write("")
        self.stdout.write(
            "NOTE: This migration REMOVES the prefix from file_path values in the database.\n"
            "The prefix will be added automatically by default_storage when accessing files."
        )
        self.stdout.write("")

        # Initialize S3 service
        s3_service = S3FileUploadService()

        # Query FileModel records that START with prefix (these need to be updated)
        queryset = FileModel.objects.filter(file_path__startswith=f"{prefix}/")

        if limit:
            queryset = queryset[:limit]

        total_count = queryset.count()
        self.stdout.write(f"Found {total_count} records with prefix that need updating")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("All records already correct. Nothing to do."))
            return

        # Process records
        updated_count = 0
        not_found_count = 0
        error_count = 0

        for file_model in queryset:
            original_path = file_model.file_path
            # Remove prefix from path
            new_path = original_path[len(prefix) + 1 :]  # +1 for the slash

            try:
                # Check if object exists at the S3 location (using original prefixed path)
                if s3_service.check_file_exists(original_path):
                    if dry_run:
                        self.stdout.write(
                            f"Would update: {file_model.id} | {original_path} -> {new_path}",
                        )
                        updated_count += 1
                    else:
                        # Apply the change
                        with transaction.atomic():
                            file_model.file_path = new_path
                            file_model.save(update_fields=["file_path"])
                        self.stdout.write(
                            self.style.SUCCESS(f"Updated: {file_model.id} | {original_path} -> {new_path}")
                        )
                        logger.info(
                            f"Migrated file path (removed prefix): id={file_model.id}, old={original_path}, new={new_path}"
                        )
                        updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Object not found in S3: {file_model.id} | {original_path}",
                        )
                    )
                    logger.warning(f"S3 object not found during migration: id={file_model.id}, path={original_path}")
                    not_found_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing record {file_model.id}: {e}",
                    )
                )
                logger.error(f"Error during migration: id={file_model.id}, path={original_path}, error={e}")
                error_count += 1

        # Summary
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total records processed: {total_count}")
        self.stdout.write(f"Records {'that would be ' if dry_run else ''}updated: {updated_count}")
        self.stdout.write(f"Records with object not found: {not_found_count}")
        self.stdout.write(f"Records with errors: {error_count}")
        self.stdout.write("")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("This was a DRY RUN. No changes were made."),
            )
            self.stdout.write("Run with --apply to make changes.")
        else:
            self.stdout.write(self.style.SUCCESS("Migration completed."))

        if not_found_count > 0:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"{not_found_count} records have file_path values where the S3 object "
                    "was not found. These may need manual review."
                )
            )
