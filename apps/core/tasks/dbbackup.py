"""Celery task to run database backups using the `dbbackup` management command.

This task wraps Django's `call_command('dbbackup', ...)` into a Celery task so
it can be scheduled or invoked asynchronously from management or other code.

The task returns a simple dict indicating success and includes any error
message when it fails.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.core.management import call_command
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)


@shared_task
def run_dbbackup() -> dict[str, Any]:
    """Run the `dbbackup` management command.

    This task invokes `manage.py dbbackup --compress` non-interactively.

    Returns:
        dict with keys: `success` (bool) and optionally `error` (str) when
        `success` is False.
    """
    try:
        # Pass compress=True to enable the --compress flag
        call_command("dbbackup", noinput=True, compress=True)
        logger.info("run_dbbackup: dbbackup completed successfully")
        return {"success": True}
    except CommandError as e:
        logger.exception("run_dbbackup: dbbackup command failed: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:  # pragma: no cover - defensive logging
        logger.exception("run_dbbackup: unexpected error: %s", e)
        return {"success": False, "error": str(e)}
