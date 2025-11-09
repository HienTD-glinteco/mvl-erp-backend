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
from datetime import date, datetime, timedelta
from typing import Any, Callable, Protocol

from celery import shared_task
from django.db import transaction
from django.db.models import Min, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Constants
AGGREGATION_MAX_RETRIES = 3
AGGREGATION_RETRY_DELAY = 60  # seconds
MAX_REPORT_LOOKBACK_DAYS = 365
EVENT_QUEUE = "reports_event"
BATCH_QUEUE = "reports_batch"


class AggregationFunction(Protocol):
    """Protocol for aggregation functions."""

    def __call__(self, event_type: str, snapshot: dict[str, Any]) -> None:
        """Process aggregation for a single event.
        
        Args:
            event_type: "create", "update", or "delete"
            snapshot: Dict with "previous" and "current" state
        """
        ...


class BatchAggregationFunction(Protocol):
    """Protocol for batch aggregation functions."""

    def __call__(
        self, 
        process_date: date, 
        org_units: list[tuple[int, int, int]]
    ) -> int:
        """Process batch aggregation for a specific date.
        
        Args:
            process_date: Date to aggregate
            org_units: List of (branch_id, block_id, department_id) tuples
            
        Returns:
            Number of org units processed
        """
        ...


def create_event_task(
    name: str,
    aggregate_func: AggregationFunction,
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

            # Extract date for logging
            data = current if current else previous
            report_date = data.get("date")

            logger.info(
                f"[{name}] Processing {event_type} event for date {report_date}"
            )

            # Execute aggregation in atomic transaction
            try:
                with transaction.atomic():
                    aggregate_func(event_type, snapshot)
            except Exception as agg_error:
                logger.exception(
                    f"[{name}] Aggregation failed for {event_type}: {str(agg_error)}"
                )
                raise

            return {
                "success": True,
                "event_type": event_type,
                "report_date": str(report_date),
            }

        except Exception as e:
            logger.exception(f"[{name}] Task execution failed: {str(e)}")
            try:
                countdown = AGGREGATION_RETRY_DELAY * (2 ** self.request.retries)
                raise self.retry(exc=e, countdown=countdown)
            except self.MaxRetriesExceededError:
                return {"success": False, "error": str(e)}

    return event_task


def create_batch_task(
    name: str,
    batch_aggregate_func: BatchAggregationFunction,
    get_modified_model_query: Callable[[date, date], Any],
    queue: str = BATCH_QUEUE,
) -> Callable:
    """Create a batch report reconciliation task.
    
    This factory creates a Celery task that:
    - Detects modified records from today
    - Finds earliest affected date
    - Processes all dates from earliest to today
    - Handles affected org units efficiently
    - Implements retry logic
    
    Args:
        name: Task name for Celery
        batch_aggregate_func: Function that performs batch aggregation
        get_modified_model_query: Function that returns queryset of modified records
        queue: Celery queue name (default: reports_batch)
    
    Returns:
        Configured Celery shared_task
    """

    @shared_task(
        bind=True,
        name=name,
        queue=queue,
        max_retries=AGGREGATION_MAX_RETRIES,
    )
    def batch_task(self, target_date: str | None = None) -> dict[str, Any]:
        """Batch report aggregation task.
        
        Args:
            self: Celery task instance
            target_date: Specific date to process (ISO format YYYY-MM-DD)
            
        Returns:
            dict: Result with success status and metadata
        """
        try:
            today = timezone.now().date()

            if target_date:
                # Process specific date only
                report_date = datetime.fromisoformat(target_date).date()
                dates_to_process = [report_date]
                affected_org_units = None
            else:
                # Check for modifications today
                cutoff_date = today - timedelta(days=MAX_REPORT_LOOKBACK_DAYS)

                modified_records = get_modified_model_query(today, cutoff_date)

                if not modified_records.exists():
                    # No changes - process today only
                    dates_to_process = [today]
                    affected_org_units = None
                else:
                    # Find earliest date and affected org units
                    earliest_date = modified_records.aggregate(min_date=Min("date"))[
                        "min_date"
                    ]

                    # Get unique org units
                    affected_org_units = set(
                        modified_records.values_list(
                            "branch_id", "block_id", "department_id"
                        ).distinct()
                    )

                    # Generate date range
                    dates_to_process = []
                    current_date = earliest_date
                    while current_date <= today:
                        dates_to_process.append(current_date)
                        current_date += timedelta(days=1)

                    logger.info(
                        f"[{name}] Detected {modified_records.count()} modifications. "
                        f"Processing {len(dates_to_process)} dates for "
                        f"{len(affected_org_units)} org units."
                    )

            if not dates_to_process:
                logger.info(f"[{name}] No dates to process")
                return {"success": True, "dates_processed": 0}

            # Process all dates
            total_org_units = 0
            try:
                for process_date in dates_to_process:
                    org_units_processed = batch_aggregate_func(
                        process_date, affected_org_units
                    )
                    total_org_units += org_units_processed
            except Exception as batch_error:
                logger.exception(
                    f"[{name}] Batch processing failed: {str(batch_error)}"
                )
                raise

            logger.info(
                f"[{name}] Complete. Processed {len(dates_to_process)} dates, "
                f"{total_org_units} org units."
            )

            return {
                "success": True,
                "dates_processed": len(dates_to_process),
                "org_units_processed": total_org_units,
            }

        except Exception as e:
            logger.exception(f"[{name}] Task execution failed: {str(e)}")
            try:
                countdown = AGGREGATION_RETRY_DELAY * (2 ** self.request.retries)
                raise self.retry(exc=e, countdown=countdown)
            except self.MaxRetriesExceededError:
                return {"success": False, "error": str(e)}

    return batch_task


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
