"""
Global pytest configuration for test database toggling.

Usage:
- Default (from pyproject addopts): reuse test DB across runs for speed.
- Override quickly via CLI:
    pytest --db-mode=recreate   # drop and re-create test DB
    pytest --db-mode=flush      # keep schema, flush data at session start
    pytest --db-mode=reuse      # reuse existing test DB (default)
- Or via env var (takes effect if CLI option omitted):
    PYTEST_DB_MODE=recreate pytest

Modes:
- reuse:     pytest-django --reuse-db (fastest, no deletion)
- recreate:  force re-create test DB (--create-db, disable reuse)
- flush:     reuse schema but flush all data once at session start
"""

import os
from unittest.mock import MagicMock

import pytest
from django.core.management import call_command


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--db-mode",
        action="store",
        default=os.getenv("PYTEST_DB_MODE", "reuse"),
        choices=["reuse", "recreate", "flush"],
        help=(
            "Test DB mode: 'reuse' (default), 'recreate' (drop & re-create), or "
            "'flush' (keep schema, clear data at session start)."
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    mode = config.getoption("--db-mode")

    # Normalize pytest-django options based on requested mode
    if mode == "recreate":
        # Force a fresh database: disable reuse, enable create
        config.option.reuse_db = False
        config.option.create_db = True
    elif mode == "reuse":
        # Ensure reuse is on (fast path)
        config.option.reuse_db = True
        config.option.create_db = False
    elif mode == "flush":
        # Reuse schema for speed; data cleared by fixture below
        config.option.reuse_db = True
        config.option.create_db = False


@pytest.fixture(scope="session", autouse=True)
def _maybe_flush_db(request: pytest.FixtureRequest, django_db_blocker) -> None:  # type: ignore[no-redef]
    """Flush DB once at session start if --db-mode=flush.

    This keeps the test DB schema (fast) but ensures no leftover data.
    """
    mode = request.config.getoption("--db-mode")
    if mode != "flush":
        return

    with django_db_blocker.unblock():
        # Flush without interactive prompts; keep auth tables, etc., intact.
        call_command("flush", verbosity=0, interactive=False)


@pytest.fixture(autouse=True)
def mock_audit_logging(monkeypatch):
    """
    Mock audit logging producer to prevent RabbitMQ connection attempts during tests.

    This fixture is automatically applied to all tests unless a test explicitly
    needs to test audit logging functionality (in which case it should mock at
    the specific view level).
    """

    # Mock the _send_message_async method to avoid RabbitMQ connection
    mock_producer = MagicMock()
    monkeypatch.setattr("apps.audit_logging.producer._audit_producer.log_event", MagicMock())
