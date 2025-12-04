"""
Celery tasks for async XLSX export.
"""

from celery import shared_task
from django.apps import apps
from django.conf import settings

from .constants import DEFAULT_PROGRESS_CHUNK_SIZE
from .generator import XLSXGenerator
from .progress import ExportProgressTracker
from .schema_builder import SchemaBuilder
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


@shared_task(bind=True, name="export_xlsx.generate_file_from_queryset")
def generate_xlsx_from_queryset_task(
    self, app_label, model_name, queryset_filters=None, filename=None, storage_backend=None
):
    """
    Background task to generate XLSX file from Django model queryset with progress tracking.

    This task builds the export schema inside the task, avoiding the need to pass
    the full schema (which can be large) through the message broker.

    Args:
        app_label: Django app label (e.g., 'hrm')
        model_name: Model name (e.g., 'Employee')
        queryset_filters: Dict of filter kwargs to apply to queryset (optional)
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
        # Get the model class
        model_class = apps.get_model(app_label, model_name)

        # Build queryset with filters
        queryset = model_class.objects.all()
        if queryset_filters:
            queryset = queryset.filter(**queryset_filters)

        # Build schema from model and queryset
        builder = SchemaBuilder()
        schema = builder.build_from_model(model_class, queryset)

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
        filename = filename or f"{model_class._meta.verbose_name_plural}_export.xlsx"
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


@shared_task(bind=True, name="export_xlsx.generate_file_from_viewset")
def generate_xlsx_from_viewset_task(self, viewset_class_path, request_data, filename=None, storage_backend=None):
    """
    Background task to generate XLSX file by calling ViewSet's get_export_data method.

    This task supports custom export logic by reconstructing the ViewSet and request context
    in the worker, allowing even complex custom exports to be processed asynchronously.

    Args:
        viewset_class_path: Full import path to ViewSet class (e.g., 'apps.myapp.views.MyViewSet')
        request_data: Dict with request context (query_params, user_id, etc.)
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
        from django.contrib.auth import get_user_model
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        # Import the ViewSet class dynamically
        module_path, class_name = viewset_class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        viewset_class = getattr(module, class_name)

        # Create a mock request with the necessary context
        factory = APIRequestFactory()
        django_request = factory.get("/", data=request_data.get("query_params", {}))

        # Add user to request if provided
        if request_data.get("user_id"):
            User = get_user_model()
            try:
                user = User.objects.get(pk=request_data["user_id"])
                django_request.user = user
            except User.DoesNotExist:
                pass

        # Create DRF Request
        drf_request = Request(django_request)

        # Instantiate ViewSet and set up context
        viewset = viewset_class()
        viewset.request = drf_request
        viewset.format_kwarg = None

        # Call get_export_data to build schema
        schema = viewset.get_export_data(drf_request)

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
