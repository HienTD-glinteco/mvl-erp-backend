"""Celery tasks for async import processing."""

import importlib
import logging
import traceback
from pathlib import Path
from typing import Callable

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.imports.constants import (
    ERROR_HANDLER_NOT_FOUND,
    ERROR_MISSING_HANDLER,
    FILE_PURPOSE_IMPORT_FAILED,
    FILE_PURPOSE_IMPORT_SUCCESS,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
)
from apps.imports.models import ImportJob
from apps.imports.progress import ImportProgressTracker
from apps.imports.utils import (
    count_total_rows,
    get_streaming_reader,
    get_streaming_writer,
    read_headers,
    upload_result_file,
)

logger = logging.getLogger(__name__)


class ImportCancelled(Exception):
    """Exception raised when import job is cancelled."""

    pass


def resolve_handler(handler_path: str) -> Callable:
    """
    Resolve handler function from dotted path.

    Args:
        handler_path: Dotted path to handler function

    Returns:
        Callable: Handler function

    Raises:
        ImportError: If handler cannot be imported
        AttributeError: If handler does not exist in module
    """
    try:
        module_path, function_name = handler_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        handler = getattr(module, function_name)
        return handler
    except (ValueError, ImportError, AttributeError) as e:
        raise ImportError(ERROR_HANDLER_NOT_FOUND.format(handler_path=handler_path)) from e


@shared_task(bind=True, name="imports.process_import_job")
def import_job_task(self, import_job_id: str) -> dict:  # noqa: C901
    """
    Background task to process import job.

    Args:
        import_job_id: UUID of the ImportJob

    Returns:
        dict: Result with status and metrics
    """
    job = None
    progress_tracker = ImportProgressTracker(import_job_id)

    try:
        # Acquire lock and load job
        with transaction.atomic():
            job = ImportJob.objects.select_for_update().get(id=import_job_id)

            # Check if already running
            if job.status == STATUS_RUNNING:
                logger.warning(f"Import job {import_job_id} is already running")
                return {"status": "already_running"}

            # Update job status
            job.status = STATUS_RUNNING
            job.started_at = timezone.now()
            job.celery_task_id = self.request.id
            job.save(update_fields=["status", "started_at", "celery_task_id"])

        # Get file and validate
        file_obj = job.file
        if not file_obj.is_confirmed:
            raise ValueError("File is not confirmed")

        # Get handler from options
        handler = None
        options = job.options or {}

        # Check if using ViewSet method handler
        if options.get("use_viewset_method"):
            viewset_class_path = options.get("viewset_class_path")
            if not viewset_class_path:
                raise ValueError("ViewSet class path not found for method handler")

            # Resolve ViewSet class and instantiate it
            try:
                module_path, class_name = viewset_class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                viewset_class = getattr(module, class_name)

                # Create a minimal ViewSet instance (without request context)
                viewset_instance = viewset_class()

                # Get the method handler
                if hasattr(viewset_instance, "_process_import_data_row"):
                    handler = viewset_instance._process_import_data_row
                else:
                    raise ValueError(f"ViewSet {viewset_class_path} does not have _process_import_data_row method")
            except (ValueError, ImportError, AttributeError) as e:
                raise ImportError(f"Failed to resolve ViewSet method handler: {viewset_class_path}") from e
        else:
            # Use traditional handler path
            handler_path = options.get("handler_path")
            if not handler_path:
                raise ValueError(ERROR_MISSING_HANDLER)

            # Resolve handler
            handler = resolve_handler(handler_path)

        # Get import options
        batch_size = options.get("batch_size", getattr(settings, "IMPORT_DEFAULT_BATCH_SIZE", 500))
        count_total_first = options.get("count_total_first", True)
        header_rows = options.get("header_rows", 1)
        output_format = options.get("output_format", "csv")
        create_result_files = options.get("create_result_file_records", True)
        db_flush_every_n = getattr(settings, "IMPORT_PROGRESS_DB_FLUSH_EVERY_N_BATCHES", 5)

        # Get file extension
        file_extension = Path(file_obj.file_name).suffix

        # Get the correct file path for storage backend
        # If AWS_LOCATION is set, file_path may already include it, so strip it to avoid duplication
        file_path = file_obj.file_path
        aws_location = getattr(settings, "AWS_LOCATION", None)
        if aws_location and file_path.startswith(f"{aws_location}/"):
            file_path = file_path[len(aws_location) + 1 :]

        # Read headers from the file and add to options
        try:
            headers = read_headers(file_path, file_extension, header_row=0)
            options["headers"] = headers
            logger.info(f"Import job {import_job_id}: Read {len(headers)} headers")
        except Exception as e:
            logger.warning(f"Failed to read headers for import job {import_job_id}: {e}")
            options["headers"] = []

        # Count total rows if requested
        total_rows = None
        if count_total_first:
            logger.info(f"Counting total rows for import job {import_job_id}")
            total_rows = count_total_rows(file_path, file_extension, skip_rows=header_rows)
            job.total_rows = total_rows
            job.save(update_fields=["total_rows"])
            progress_tracker.set_total(total_rows)
            logger.info(f"Import job {import_job_id}: total_rows={total_rows}")

        # Prepare temporary directory for result files
        temp_dir = getattr(settings, "IMPORT_TEMP_DIR", None)

        # Initialize streaming writers
        base_filename = Path(file_obj.file_name).stem
        success_writer = get_streaming_writer(
            f"{base_filename}_success",
            output_format=output_format,
            temp_dir=temp_dir,
        )
        failed_writer = get_streaming_writer(
            f"{base_filename}_failed",
            output_format=output_format,
            temp_dir=temp_dir,
        )

        # Process rows
        reader = get_streaming_reader(file_path, file_extension)
        batch_count = 0

        with reader, success_writer, failed_writer:
            # Write headers
            # For failed file, add import_error column
            headers_written = False

            for row_index, row in enumerate(reader.read_rows(skip_rows=header_rows), start=1):
                # Check for cancellation
                # Reload job from DB to check if it was cancelled
                job.refresh_from_db()
                if job.status == STATUS_CANCELLED:
                    logger.info(f"Import job {import_job_id} was cancelled")
                    raise ImportCancelled()

                # Invoke handler
                try:
                    result = handler(
                        row_index=row_index,
                        row=row,
                        import_job_id=str(import_job_id),
                        options=options,
                    )

                    # Write headers on first row
                    if not headers_written:
                        # Assume row length matches header
                        success_headers = [f"col_{i}" for i in range(len(row))]
                        failed_headers = success_headers + ["import_error"]
                        success_writer.write_header(success_headers)
                        failed_writer.write_header(failed_headers)
                        headers_written = True

                    if result.get("ok"):
                        # Success
                        success_writer.write_row(row)
                        progress_tracker.update(success_increment=1)
                    else:
                        # Failure
                        error_msg = result.get("error", "Unknown error")
                        failed_row = list(row) + [error_msg]
                        failed_writer.write_row(failed_row)
                        progress_tracker.update(failure_increment=1)

                except Exception as e:
                    # Handler exception
                    logger.error(f"Import job {import_job_id} handler error at row {row_index}: {e}")
                    if not headers_written:
                        success_headers = [f"col_{i}" for i in range(len(row))]
                        failed_headers = success_headers + ["import_error"]
                        success_writer.write_header(success_headers)
                        failed_writer.write_header(failed_headers)
                        headers_written = True

                    failed_row = list(row) + [str(e)]
                    failed_writer.write_row(failed_row)
                    progress_tracker.update(failure_increment=1)

                # Flush progress to DB periodically
                batch_count += 1
                if batch_count >= batch_size * db_flush_every_n:
                    job.processed_rows = progress_tracker.processed_rows
                    job.success_count = progress_tracker.success_count
                    job.failure_count = progress_tracker.failure_count
                    job.calculate_percentage()
                    job.save(update_fields=["processed_rows", "success_count", "failure_count", "percentage"])
                    batch_count = 0

        # Upload result files if enabled
        result_success_file = None
        result_failed_file = None

        if create_result_files:
            s3_prefix = getattr(settings, "IMPORT_S3_PREFIX", "uploads/imports/")
            s3_prefix = f"{s3_prefix}{import_job_id}/"

            # Upload success file
            if progress_tracker.success_count > 0:
                try:
                    result_success_file = upload_result_file(
                        local_file_path=success_writer.get_file_path(),
                        s3_prefix=s3_prefix,
                        original_filename=f"{base_filename}_success.{output_format}",
                        purpose=FILE_PURPOSE_IMPORT_SUCCESS,
                        uploaded_by=job.created_by,
                    )
                    logger.info(f"Uploaded success file for import job {import_job_id}: {result_success_file.id}")
                except Exception as e:
                    logger.error(f"Failed to upload success file for import job {import_job_id}: {e}")

            # Upload failed file
            if progress_tracker.failure_count > 0:
                try:
                    result_failed_file = upload_result_file(
                        local_file_path=failed_writer.get_file_path(),
                        s3_prefix=s3_prefix,
                        original_filename=f"{base_filename}_failed.{output_format}",
                        purpose=FILE_PURPOSE_IMPORT_FAILED,
                        uploaded_by=job.created_by,
                    )
                    logger.info(f"Uploaded failed file for import job {import_job_id}: {result_failed_file.id}")
                except Exception as e:
                    logger.error(f"Failed to upload failed file for import job {import_job_id}: {e}")

        # Mark as completed
        job.status = STATUS_SUCCEEDED
        job.finished_at = timezone.now()
        job.processed_rows = progress_tracker.processed_rows
        job.success_count = progress_tracker.success_count
        job.failure_count = progress_tracker.failure_count
        job.calculate_percentage()
        job.result_success_file = result_success_file
        job.result_failed_file = result_failed_file
        if result_success_file:
            job.result_success_s3_path = result_success_file.file_path
        if result_failed_file:
            job.result_failed_s3_path = result_failed_file.file_path
        job.save()

        progress_tracker.set_completed()

        return {
            "status": "success",
            "processed_rows": job.processed_rows,
            "success_count": job.success_count,
            "failure_count": job.failure_count,
        }

    except ImportCancelled:
        # Task was cancelled
        if job:
            job.status = STATUS_CANCELLED
            job.finished_at = timezone.now()
            job.processed_rows = progress_tracker.processed_rows
            job.success_count = progress_tracker.success_count
            job.failure_count = progress_tracker.failure_count
            job.calculate_percentage()
            job.save()
        return {"status": "cancelled"}

    except Exception as e:
        # Task failed
        error_message = f"{str(e)}\n\n{traceback.format_exc()}"
        logger.error(f"Import job {import_job_id} failed: {error_message}")

        if job:
            job.status = STATUS_FAILED
            job.finished_at = timezone.now()
            job.error_message = error_message[:5000]  # Truncate if too long
            job.processed_rows = progress_tracker.processed_rows
            job.success_count = progress_tracker.success_count
            job.failure_count = progress_tracker.failure_count
            job.calculate_percentage()
            job.save()

        progress_tracker.set_failed(str(e))

        return {
            "status": "error",
            "error": str(e),
        }
