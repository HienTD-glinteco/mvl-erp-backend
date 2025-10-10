"""
Celery tasks for async XLSX export.
"""

from celery import shared_task
from django.utils.translation import gettext as _

from .generator import XLSXGenerator
from .storage import get_storage_backend


@shared_task(bind=True, name="export_xlsx.generate_file")
def generate_xlsx_task(self, schema, filename=None, storage_backend=None):
    """
    Background task to generate XLSX file.

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
    try:
        # Generate XLSX file
        generator = XLSXGenerator()
        file_content = generator.generate(schema)

        # Save to storage
        storage = get_storage_backend(storage_backend)
        filename = filename or "export.xlsx"
        file_path = storage.save(file_content, filename)
        file_url = storage.get_url(file_path)

        return {
            "status": "success",
            "file_url": file_url,
            "file_path": file_path,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
