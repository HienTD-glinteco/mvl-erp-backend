"""Management command to upload import template files."""

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.files.models import FileModel
from apps.imports.constants import FILE_PURPOSE_IMPORT_TEMPLATE

User = get_user_model()


class Command(BaseCommand):
    """
    Upload import template files from apps/*/import_templates/ directories to S3.

    The command automatically scans all apps for import_templates/ subdirectories
    and uploads template files found there, automatically prefixing each file
    with the app name.

    Directory structure:
        apps/
            hrm/
                import_templates/
                    employees_template.csv      -> uploaded as hrm_employees_template.csv
                    departments_template.xlsx   -> uploaded as hrm_departments_template.xlsx
            crm/
                import_templates/
                    customers_template.csv      -> uploaded as crm_customers_template.csv
            ...

    File naming convention in import_templates/:
        {resource}_template.{ext}

    Examples:
        employees_template.csv
        customers_template.xlsx
        users_template.csv
    """

    help = "Upload import template files from apps/*/import_templates/ directories to S3"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--app",
            type=str,
            default=None,
            help="Process only specific app (e.g., 'hrm', 'crm'). If not provided, scans all apps.",
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
            help="Replace existing templates (archives old ones)",
        )

    def handle(self, *args, **options):  # noqa: C901
        """Handle the command execution."""
        app_filter = options.get("app")
        user_id = options.get("user_id")
        s3_prefix = options["s3_prefix"]
        dry_run = options["dry_run"]
        replace = options["replace"]

        # Get user if specified
        uploaded_by = None
        if user_id:
            try:
                uploaded_by = User.objects.get(id=user_id)
                self.stdout.write(f"Using user: {uploaded_by.username} (ID: {user_id})")
            except User.DoesNotExist:
                raise CommandError(f"User with ID {user_id} does not exist")

        # Find template files from apps/*/import_templates/ directories
        template_files = self._find_template_files_in_apps(app_filter)
        if not template_files:
            if app_filter:
                self.stdout.write(
                    self.style.WARNING(f"No template files found in apps/{app_filter}/import_templates/")
                )
            else:
                self.stdout.write(
                    self.style.WARNING("No template files found in any apps/*/import_templates/ directories")
                )
            return

        self.stdout.write(f"Found {len(template_files)} template file(s):")
        for template_path, app_name, final_name in template_files:
            self.stdout.write(f"  - {template_path.name} -> {final_name} (app: {app_name})")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run mode - no files will be uploaded"))
            return

        # Upload templates
        uploaded_count = 0
        replaced_count = 0

        for template_path, app_name, final_name in template_files:
            try:
                with transaction.atomic():
                    # Handle replacement - look for templates with the same final name prefix
                    if replace:
                        # Extract the template name without extension for matching
                        template_name_base = final_name.rsplit("_template.", 1)[0]
                        existing = FileModel.objects.filter(
                            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
                            file_name__istartswith=template_name_base,
                            is_confirmed=True,
                        )
                        if existing.exists():
                            replaced_count += existing.count()
                            # Mark existing templates as not confirmed (soft archive)
                            existing.update(is_confirmed=False)
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Archived {existing.count()} existing template(s): {template_name_base}"
                                )
                            )

                    # Read file content
                    with open(template_path, "rb") as f:
                        file_content = f.read()

                    # Generate S3 path with final name
                    s3_path = f"{s3_prefix}{final_name}"

                    # Upload to S3 using default_storage
                    saved_path = default_storage.save(s3_path, ContentFile(file_content))

                    # Create FileModel record
                    file_obj = FileModel.objects.create(
                        purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
                        file_name=final_name,
                        file_path=saved_path,
                        size=len(file_content),
                        is_confirmed=True,
                        uploaded_by=uploaded_by,
                    )

                    uploaded_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Uploaded: {final_name} (FileModel ID: {file_obj.id})"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to upload {template_path.name}: {e}"))
                continue

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Successfully uploaded {uploaded_count} template file(s)"))
        if replaced_count > 0:
            self.stdout.write(self.style.WARNING(f"Replaced {replaced_count} existing template(s)"))
        self.stdout.write("=" * 60)

    def _find_template_files_in_apps(self, app_filter=None):
        """
        Find all template files in apps/*/import_templates/ directories.

        Args:
            app_filter: If provided, only scan this specific app

        Returns:
            List of tuples: (Path, app_name, final_name)
            Where final_name is the filename with app prefix (e.g., hrm_employees_template.csv)
        """
        template_files = []

        # Get the base directory (assumes command is run from project root)
        base_dir = Path(os.getcwd())
        apps_dir = base_dir / "apps"

        if not apps_dir.exists():
            self.stdout.write(self.style.WARNING(f"Apps directory not found: {apps_dir}"))
            return template_files

        # Determine which apps to scan
        if app_filter:
            app_dirs = [apps_dir / app_filter]
        else:
            # Scan all subdirectories in apps/
            app_dirs = [d for d in apps_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]

        for app_dir in app_dirs:
            app_name = app_dir.name
            import_templates_dir = app_dir / "import_templates"

            if not import_templates_dir.exists():
                continue

            # Find all template files in this app's import_templates directory
            for file_path in import_templates_dir.glob("*_template.*"):
                if file_path.is_file():
                    # Generate final name with app prefix
                    # e.g., employees_template.csv -> hrm_employees_template.csv
                    file_name = file_path.name
                    final_name = f"{app_name}_{file_name}"

                    template_files.append((file_path, app_name, final_name))

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
