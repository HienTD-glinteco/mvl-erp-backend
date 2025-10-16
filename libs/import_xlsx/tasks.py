"""
Celery tasks for async XLSX import.
"""

import logging

from celery import shared_task
from django.apps import apps
from django.utils.translation import gettext as _
from openpyxl import load_workbook

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="import_xlsx.import_file")
def import_xlsx_task(self, app_label, model_name, file_path, schema, user_id=None):
    """
    Background task to import XLSX file.

    Args:
        app_label: Django app label (e.g., 'core')
        model_name: Model name (e.g., 'Role')
        file_path: Path to uploaded XLSX file
        schema: Import schema definition
        user_id: Optional user ID for audit logging

    Returns:
        dict: Result with keys:
            - status: 'success' or 'error'
            - success_count: Number of successfully imported rows
            - error_count: Number of errors
            - errors: List of error details
            - error_file_url: URL to download error report (if errors exist)
    """
    from django.core.files.storage import default_storage

    from .error_report import ErrorReportGenerator
    from .storage import get_storage_backend
    from .utils import bulk_import_data, extract_headers, map_headers_to_fields, process_row

    try:
        # Get model class
        model = apps.get_model(app_label, model_name)

        # Load the file from storage
        if not default_storage.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Open and parse XLSX file
        with default_storage.open(file_path, "rb") as f:
            workbook = load_workbook(f, read_only=True)
            sheet = workbook.active

            # Extract headers
            headers = extract_headers(sheet)

            # Map headers to fields
            field_mapping = map_headers_to_fields(headers, schema["fields"])

            # Parse and validate data
            parsed_data = []
            errors = []
            original_data = []

            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                # Skip empty rows
                if not any(row):
                    continue

                # Store original row data
                original_data.append(list(row))

                # Process row
                row_data, row_errors = process_row(row, headers, field_mapping, schema, model)

                if row_errors:
                    errors.append({"row": row_idx, "errors": row_errors})
                elif row_data:
                    parsed_data.append(row_data)

            workbook.close()

        # Import data
        success_count = 0
        if parsed_data:
            success_count = bulk_import_data(model, parsed_data, errors, user_id)

        # Generate error report if errors exist
        error_file_url = None
        if errors:
            try:
                storage = get_storage_backend()
                generator = ErrorReportGenerator()
                report_content = generator.generate(errors, original_data, headers)
                report_path = storage.save_error_report(report_content)
                error_file_url = storage.get_url(report_path)
            except Exception as e:
                logger.warning(f"Failed to generate error report: {e}")

        # Clean up temporary file
        try:
            default_storage.delete(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")

        return {
            "status": "success",
            "success_count": success_count,
            "error_count": len(errors),
            "errors": errors[:100],  # Limit errors in response
            "error_file_url": error_file_url,
        }

    except Exception as e:
        logger.exception(f"Import task failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "success_count": 0,
            "error_count": 0,
            "errors": [],
        }
