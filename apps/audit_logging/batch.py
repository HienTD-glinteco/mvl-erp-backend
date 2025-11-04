"""
Utilities for batch audit logging.

This module provides mechanisms to log batch operations where each object
gets its own individual audit log entry, but all entries are linked together
via batch metadata (batch_id, batch_action).
"""

import logging
import threading
import uuid
from contextlib import contextmanager
from typing import Any, List, Optional

from .constants import LogAction
from .middleware import get_current_request, get_current_user
from .producer import _audit_producer
from .registry import AuditLogRegistry
from .utils import prepare_request_info, prepare_user_info

logger = logging.getLogger(__name__)

# Thread-local storage for batch context
_batch_locals = threading.local()


def get_batch_context():
    """Get the current batch context if active."""
    return getattr(_batch_locals, "batch_context", None)


def is_batch_active():
    """Check if we're currently in a batch logging context."""
    return get_batch_context() is not None


def get_batch_metadata():
    """
    Get the current batch metadata if in a batch context.

    Returns:
        dict: Batch metadata to include in individual logs, or None if not in batch context
    """
    batch_context = get_batch_context()
    if batch_context:
        return batch_context.get_metadata()
    return None


@contextmanager
def batch_audit_context(action: str, model_class, user=None, request=None, **extra_fields):
    """
    Context manager for batch operations that creates individual audit logs
    for each affected object, with all logs linked via batch metadata.

    This allows querying all logs for a specific object (including batch operations)
    while still maintaining the relationship between all objects in a batch.

    Usage:
        from apps.audit_logging import batch_audit_context, LogAction

        with batch_audit_context(
            action=LogAction.IMPORT,
            model_class=Customer,
            user=request.user,
            request=request,
            import_source="customers.xlsx"
        ) as batch:
            for data in customer_data:
                customer = Customer.objects.create(**data)
                # Individual log is automatically created via signals
                # with batch metadata attached

    Args:
        action: The batch action type (e.g., LogAction.IMPORT)
        model_class: The model class being operated on
        user: The user performing the action
        request: The HTTP request object
        **extra_fields: Additional fields to include in each log (e.g., import_source)

    Yields:
        BatchContext: A context object for tracking batch progress
    """
    batch_context = BatchContext(
        action=action,
        model_class=model_class,
        user=user,
        request=request,
        extra_fields=extra_fields,
    )

    # Store in thread-local so signal handlers can access batch metadata
    _batch_locals.batch_context = batch_context

    try:
        yield batch_context
    finally:
        # Log summary if there were any errors
        if batch_context.errors:
            batch_context.log_summary()

        # Clean up thread-local
        if hasattr(_batch_locals, "batch_context"):
            del _batch_locals.batch_context


class BatchContext:
    """
    Context object for batch operations.

    Tracks batch metadata that will be attached to individual audit logs
    for each object in the batch. Also tracks errors for summary logging.
    """

    def __init__(
        self,
        action: str,
        model_class,
        user=None,
        request=None,
        extra_fields: Optional[dict[str, Any]] = None,
    ):
        self.action = action
        self.model_class = model_class
        self.user = user or get_current_user()
        self.request = request or get_current_request()
        self.extra_fields = extra_fields or {}
        self.batch_id = str(uuid.uuid4())  # Unique ID to link all logs in this batch
        self.object_count = 0
        self.errors: List[dict] = []

    def get_metadata(self) -> dict[str, Any]:
        """
        Get batch metadata to be included in individual audit logs.

        Returns:
            dict: Metadata to attach to each individual log entry
        """
        return {
            "batch_id": self.batch_id,
            "batch_action": self.action,
            **self.extra_fields,
        }

    def increment_count(self):
        """Increment the count of objects processed in this batch."""
        self.object_count += 1

    def add_error(self, error_message: str, context: Optional[dict] = None):
        """
        Track an error that occurred during the batch operation.

        Args:
            error_message: Description of the error
            context: Optional context information (e.g., row number, object data)
        """
        error_entry: dict[str, Any] = {
            "message": error_message,
            "timestamp": None,  # Will be set when logged
        }
        if context:
            error_entry["context"] = context
        self.errors.append(error_entry)

    def log_summary(self):
        """
        Log a summary entry for the batch operation if there were errors.

        This creates an additional log entry (separate from individual object logs)
        that summarizes the batch operation and lists any errors that occurred.
        """
        if not self.errors:
            return

        try:
            # Get model info from registry instead of querying ContentType
            model_info = AuditLogRegistry.get_model_info(self.model_class)
            if not model_info:
                logger.warning(
                    f"Model {self.model_class.__name__} not registered for audit logging. Skipping batch summary."
                )
                return

            # Prepare summary log data
            log_data: dict[str, Any] = {
                "action": self.action,
                "object_type": model_info["model_name"],
                "batch_id": self.batch_id,
                "batch_summary": True,
                "total_processed": self.object_count,
                "error_count": len(self.errors),
                "errors": self.errors[:20],  # Limit to first 20 errors
            }

            # Add user information
            if self.user:
                prepare_user_info(log_data, self.user)

            # Add request metadata
            if self.request:
                prepare_request_info(log_data, self.request)

            # Create change message
            action_names = {
                LogAction.ADD: "created",
                LogAction.CHANGE: "updated",
                LogAction.DELETE: "deleted",
                LogAction.IMPORT: "imported",
                LogAction.EXPORT: "exported",
            }
            action_name = action_names.get(self.action, self.action.lower())

            change_message = (
                f"Batch {action_name}: {self.object_count} {model_info['model_name']} object(s) "
                f"processed with {len(self.errors)} error(s)"
            )
            log_data["change_message"] = change_message

            # Add any extra fields
            log_data.update(self.extra_fields)

            # Log the summary (using the internal producer directly)
            _audit_producer.log_event(**log_data)

        except Exception as e:
            logger.error(f"Failed to log batch summary: {e}", exc_info=True)
