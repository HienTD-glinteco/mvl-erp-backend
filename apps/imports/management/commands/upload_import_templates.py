"""Management command to upload import template files."""

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import User
from apps.files.models import FileModel
from apps.files.utils.s3_utils import S3FileUploadService
from apps.imports.constants import FILE_PURPOSE_IMPORT_TEMPLATE


class Command(BaseCommand):
    """
    Upload import template files from a directory structure to S3 and create FileModel records.

    Directory structure:
        templates/
            hrm_employees_template.csv
            hrm_departments_template.xlsx
            crm_customers_template.csv
            ...

    File naming convention:
        {app_name}_{resource}_template.{ext}

    Examples:
        hrm_employees_template.csv
        crm_customers_template.xlsx
        core_users_template.csv
    """

    help = "Upload import template files from a directory to S3"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "directory",
            type=str,
            help="Path to the directory containing template files",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="ID of the user to associate with uploaded files (optional)",
        )
        parser.add_argument(
            "--s3-prefix",
            type=str,
            default="templates/imports/",
            help="S3 prefix for template files (default: templates/imports/)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform a dry run without actually uploading files",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace existing templates for the same app (archives old ones)",
        )

    def handle(self, *args, **options):  # noqa: C901
        """Handle the command execution."""
        directory = options["directory"]
        user_id = options.get("user_id")
        s3_prefix = options["s3_prefix"]
        dry_run = options["dry_run"]
        replace = options["replace"]

        # Validate directory
        if not os.path.exists(directory):
            raise CommandError(f"Directory does not exist: {directory}")

        if not os.path.isdir(directory):
            raise CommandError(f"Path is not a directory: {directory}")

        # Get user if specified
        uploaded_by = None
        if user_id:
            try:
                uploaded_by = User.objects.get(id=user_id)
                self.stdout.write(f"Using user: {uploaded_by.username} (ID: {user_id})")
            except User.DoesNotExist:
                raise CommandError(f"User with ID {user_id} does not exist")

        # Find template files
        template_files = self._find_template_files(directory)
        if not template_files:
            self.stdout.write(self.style.WARNING("No template files found in directory"))
            return

        self.stdout.write(f"Found {len(template_files)} template file(s):")
        for template_path, app_name in template_files:
            self.stdout.write(f"  - {template_path.name} (app: {app_name})")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run mode - no files will be uploaded"))
            return

        # Upload templates
        uploaded_count = 0
        replaced_count = 0
        s3_service = S3FileUploadService()

        for template_path, app_name in template_files:
            try:
                with transaction.atomic():
                    # Handle replacement
                    if replace:
                        existing = FileModel.objects.filter(
                            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
                            file_name__istartswith=app_name,
                            is_confirmed=True,
                        )
                        if existing.exists():
                            replaced_count += existing.count()
                            # Mark existing templates as not confirmed (soft archive)
                            existing.update(is_confirmed=False)
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Archived {existing.count()} existing template(s) for app: {app_name}"
                                )
                            )

                    # Read file content
                    with open(template_path, "rb") as f:
                        file_content = f.read()

                    # Generate S3 path
                    file_name = template_path.name
                    s3_path = f"{s3_prefix}{file_name}"

                    # Upload to S3
                    s3_service.upload_file(
                        file_content=file_content,
                        s3_path=s3_path,
                        content_type=self._get_content_type(file_name),
                    )

                    # Create FileModel record
                    file_obj = FileModel.objects.create(
                        purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
                        file_name=file_name,
                        file_path=s3_path,
                        size=len(file_content),
                        is_confirmed=True,
                        uploaded_by=uploaded_by,
                    )

                    uploaded_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Uploaded: {file_name} (FileModel ID: {file_obj.id})"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to upload {template_path.name}: {e}"))
                continue

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Successfully uploaded {uploaded_count} template file(s)"))
        if replaced_count > 0:
            self.stdout.write(self.style.WARNING(f"Replaced {replaced_count} existing template(s)"))
        self.stdout.write("=" * 60)

    def _find_template_files(self, directory):
        """
        Find all template files in the directory.

        Returns:
            List of tuples: (Path, app_name)
        """
        template_files = []
        dir_path = Path(directory)

        for file_path in dir_path.glob("*_template.*"):
            if file_path.is_file():
                # Extract app name from filename
                # Format: {app_name}_{resource}_template.{ext}
                file_name = file_path.stem  # Remove extension
                parts = file_name.split("_")

                if len(parts) >= 2:
                    # First part is the app name
                    app_name = parts[0]
                    template_files.append((file_path, app_name))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Skipping file with invalid naming convention: {file_path.name}")
                    )

        return template_files

    def _get_content_type(self, file_name):
        """
        Get content type based on file extension.

        Args:
            file_name: Name of the file

        Returns:
            str: Content type
        """
        ext = Path(file_name).suffix.lower()
        content_types = {
            ".csv": "text/csv",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
        }
        return content_types.get(ext, "application/octet-stream")
