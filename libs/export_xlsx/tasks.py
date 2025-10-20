"""
Celery tasks for async XLSX export.
"""

from celery import shared_task
from django.conf import settings

from .constants import DEFAULT_PROGRESS_CHUNK_SIZE
from .generator import XLSXGenerator
from .progress import ExportProgressTracker
from .storage import get_storage_backend


@shared_task(bind=True, name="export_xlsx.generate_file")
def generate_xlsx_task(self, schema, filename=None, storage_backend=None):
    """
    Background task to generate XLSX file with progress tracking.

    Args:
        schema: Export schema definition
        filename: Optional filename (default: export.xlsx)
        storage_backend: Storage backend type ('local' or 's3')

    Returns:
        dict: Result with keys:
            - status: 'success' or 'error'
            - file_url: URL to download file (if success)
            - error: Error message (if error)
    """
    # Initialize progress tracker
    progress_tracker = ExportProgressTracker(task_id=self.request.id, celery_task=self)

    try:
        # Calculate total rows from schema
        total_rows = sum(len(sheet.get("data", [])) for sheet in schema.get("sheets", []))
        progress_tracker.set_total(total_rows)

        # Get chunk size from settings
        chunk_size = getattr(settings, "EXPORTER_PROGRESS_CHUNK_SIZE", DEFAULT_PROGRESS_CHUNK_SIZE)

        # Generate XLSX file with progress callback
        def progress_callback(rows_processed: int):
            progress_tracker.update(rows_processed)

        generator = XLSXGenerator(progress_callback=progress_callback, chunk_size=chunk_size)
        file_content = generator.generate(schema)

        # Save to storage
        storage = get_storage_backend(storage_backend)
        filename = filename or "export.xlsx"
        file_path = storage.save(file_content, filename)
        file_url = storage.get_url(file_path)

        # Mark as completed
        progress_tracker.set_completed(file_url=file_url, file_path=file_path)

        return {
            "status": "success",
            "file_url": file_url,
            "file_path": file_path,
        }

    except Exception as e:
        # Mark as failed
        error_message = str(e)
        progress_tracker.set_failed(error_message)

        return {
            "status": "error",
            "error": error_message,
        }
