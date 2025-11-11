"""Common framework for report aggregation tasks.

This module provides reusable components for implementing report aggregation tasks:
- Event-driven incremental updates
- Batch reconciliation processing
- Retry logic with exponential backoff
- Snapshot-based state handling

Usage:
    from apps.hrm.tasks.report_framework import (
        EventDrivenReportTask,
        BatchReportTask,
        create_report_task,
    )

    # Define your aggregation logic
    def my_aggregate_function(event_type, snapshot):
        # Your logic here
        pass

    # Create task with framework
    my_task = create_report_task(
        name="my_report_task",
        aggregate_func=my_aggregate_function,
        queue="reports_event"
    )
"""

import logging
from typing import Any, Callable, Protocol, cast

from celery import shared_task
from django.db import transaction

# Min is no longer needed as the batch factory no longer inspects modified records
# batch factory no longer determines dates or org units; delegate to implementation

logger = logging.getLogger(__name__)

# Constants
AGGREGATION_MAX_RETRIES = 3
AGGREGATION_RETRY_DELAY = 60  # seconds
MAX_REPORT_LOOKBACK_DAYS = 365
EVENT_QUEUE = "reports_event"
BATCH_QUEUE = "reports_batch"

# Action type constants (renamed from "event_type" to avoid confusion with system events)
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"


class EventAggregationFunction(Protocol):
    """Protocol for event-driven aggregation functions.

    Renamed from AggregationFunction to clarify this is for event-driven tasks,
    not to be confused with other system events.
    """

    def __call__(self, action: str, snapshot: dict[str, Any]) -> None:
        """Process aggregation for a single action/event.

        Args:
            action: One of ACTION_CREATE, ACTION_UPDATE, or ACTION_DELETE
            snapshot: Dict with "previous" and "current" state
        """
        ...


class BatchAggregationFunction(Protocol):
    """Protocol for batch aggregation functions.

    Implementations must determine which dates and org units to process.
    The factory will pass the raw `target_date` parameter (ISO date string)
    or None — the implementation is responsible for interpreting it.
    """

    def __call__(self, target_date: str | None) -> int:
        """Run batch aggregation.

        Args:
            target_date: ISO date string (YYYY-MM-DD) or None to indicate
                the implementation should decide which dates to process.

        Returns:
            Number of org units processed
        """
        ...


def create_event_task(
    name: str,
    aggregate_func: EventAggregationFunction,
    queue: str = EVENT_QUEUE,
) -> Callable:
    """Create an event-driven report aggregation task.

    This factory creates a Celery task that:
    - Uses snapshot data to avoid race conditions
    - Implements retry logic with exponential backoff
    - Wraps aggregation in atomic transaction
    - Provides consistent logging and error handling

    Args:
        name: Task name for Celery
        aggregate_func: Function that performs the actual aggregation
        queue: Celery queue name (default: reports_event)

    Returns:
        Configured Celery shared_task

    Example:
        def my_aggregation(event_type, snapshot):
            # Aggregation logic here
            pass

        my_task = create_event_task(
            name="my.task.name",
            aggregate_func=my_aggregation
        )
    """

    @shared_task(
        bind=True,
        name=name,
        queue=queue,
        max_retries=AGGREGATION_MAX_RETRIES,
    )
    def event_task(self, event_type: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Event-driven report aggregation task.

        Args:
            self: Celery task instance
            event_type: "create", "update", or "delete"
            snapshot: Dict containing previous and current state

        Returns:
            dict: Result with success status and metadata
        """
        try:
            # Validate snapshot
            previous = snapshot.get("previous")
            current = snapshot.get("current")

            if not previous and not current:
                logger.warning(f"[{name}] Invalid snapshot for event {event_type}")
                return {"success": False, "error": "Invalid snapshot"}

            # Extract date for logging, validate that snapshot entries are dicts
            data = current if current is not None else previous
            if not isinstance(data, dict):
                logger.warning(f"[{name}] Invalid snapshot data for event {event_type}")
                return {"success": False, "error": "Invalid snapshot"}

            data_dict = cast(dict[str, Any], data)
            # mypy: data_dict is now a mapping so .get is safe
            report_date = data_dict.get("date")

            logger.info(f"[{name}] Processing {event_type} event for date {report_date}")

            # Execute aggregation in atomic transaction
            try:
                with transaction.atomic():
                    aggregate_func(event_type, snapshot)
            except Exception as agg_error:
                logger.exception(f"[{name}] Aggregation failed for {event_type}: {str(agg_error)}")
                raise

            return {
                "success": True,
                "event_type": event_type,
                "report_date": str(report_date),
            }

        except Exception as e:
            logger.exception(f"[{name}] Task execution failed: {str(e)}")
            try:
                countdown = AGGREGATION_RETRY_DELAY * (2**self.request.retries)
                raise self.retry(exc=e, countdown=countdown)
            except self.MaxRetriesExceededError:
                return {"success": False, "error": str(e)}

    return event_task


def process_snapshot_event(
    event_type: str,
    snapshot: dict[str, Any],
    on_create: Callable[[dict], None] | None = None,
    on_update: Callable[[dict, dict], None] | None = None,
    on_delete: Callable[[dict], None] | None = None,
) -> None:
    """Process a snapshot event with provided callbacks.

    This helper provides a clean pattern for handling different event types:

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with "previous" and "current" state
        on_create: Callback for create events, receives current data
        on_update: Callback for update events, receives (previous, current) data
        on_delete: Callback for delete events, receives previous data

    Example:
        def handle_create(data):
            # Process creation
            pass

        def handle_update(old_data, new_data):
            # Process update
            pass

        def handle_delete(data):
            # Process deletion
            pass

        process_snapshot_event(
            event_type,
            snapshot,
            on_create=handle_create,
            on_update=handle_update,
            on_delete=handle_delete,
        )
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    if event_type == "create" and on_create and current:
        on_create(current)
    elif event_type == "update" and on_update:
        if previous and current:
            on_update(previous, current)
    elif event_type == "delete" and on_delete and previous:
        on_delete(previous)
