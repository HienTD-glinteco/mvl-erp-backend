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
import secrets
from unittest.mock import MagicMock

import pytest
from django.core.management import call_command


@pytest.fixture(autouse=True)
def mock_s3_service(monkeypatch):
    """
    Fixture to mock S3FileUploadService used by `apps.files.models.FileModel`.

    Replaces the real `S3FileUploadService` with a lightweight mock that returns
    deterministic URLs for `generate_view_url` and `generate_download_url`.

    Usage in tests:
        def test_something(mock_s3_service):
            # when FileModel.view_url or download_url is accessed,
            # the returned URL will be predictable
            ...
    """

    class _MockS3Service:
        def generate_view_url(self, file_path: str) -> str:
            return f"https://test-s3.local/view/{file_path}"

        def generate_download_url(self, file_path: str, file_name: str) -> str:
            return f"https://test-s3.local/download/{file_path}?name={file_name}"

    # Patch the class used in apps.files.models so instantiating it returns our mock
    monkeypatch.setattr("apps.files.models.S3FileUploadService", _MockS3Service)

    return _MockS3Service()


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


@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch, settings):
    """
    Mock Celery task execution to prevent broker connection attempts during tests.

    This fixture is automatically applied to all tests to avoid RabbitMQ/Redis
    connection errors. Tasks will execute synchronously as regular functions.

    Tests that need to verify task calls should use @patch at the test level.
    """

    def mock_delay(self, *args, **kwargs):
        """Mock .delay() to either execute synchronously or noop depending on settings.

        - If settings.CELERY_TASK_ALWAYS_EAGER is truthy: execute synchronously via
          Task.apply() (existing behavior).
        - If False: make .delay() a no-op (do not execute task) and return a MagicMock
          to mimic an AsyncResult-like object. This lets tests opt-out of running
          task business logic by setting CELERY_TASK_ALWAYS_EAGER = False.
        """
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            return self.apply(args=args, kwargs=kwargs)

        return MagicMock()

    def mock_apply_async(self, *args, **kwargs):
        """Mock .apply_async() similarly to mock_delay()."""
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            task_args = kwargs.get("args", args)
            task_kwargs = kwargs.get("kwargs", {})
            return self.apply(args=task_args, kwargs=task_kwargs)

        return MagicMock()

    # Patch celery Task methods globally
    monkeypatch.setattr("celery.app.task.Task.delay", mock_delay)
    monkeypatch.setattr("celery.app.task.Task.apply_async", mock_apply_async)


@pytest.fixture(autouse=True)
def disable_throttling(settings):
    """
    Disable DRF throttling in all tests to avoid cache/Redis dependency.

    Even though test.py disables throttling, this ensures it's disabled
    for all test cases regardless of settings overrides.
    """
    # Force local memory cache to avoid Redis dependency
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-cache-fixture",
        },
    }

    # Disable throttling
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}


@pytest.fixture
def superuser(db):
    """
    Fixture that creates a superuser for testing.

    This superuser is used for auto-authentication in tests that don't
    explicitly test RoleBasedPermission behavior.
    """
    from apps.core.models import User

    password = secrets.token_urlsafe(16)

    return User.objects.create_superuser(
        username="test_superuser",
        email="superuser@test.com",
        password=password,
    )


@pytest.fixture
def api_client(request, superuser):
    """
    Fixture that provides a DRF APIClient with auto-authentication.

    By default, the client is authenticated as a superuser to bypass
    RoleBasedPermission checks. Tests that need to verify permission
    behavior should be marked with @pytest.mark.rbp to receive an
    unauthenticated client instead.

    Usage:
        - Regular tests: use api_client as normal, it's auto-authenticated
        - Permission tests: mark with @pytest.mark.rbp to get unauthenticated client
        - Custom user tests: create and authenticate your own user in the test
    """
    from rest_framework.test import APIClient

    client = APIClient()

    # Check if the test is marked with 'rbp' (Role-Based Permission)
    # If marked, do not auto-authenticate to allow permission testing
    marker_names = {marker.name for marker in request.node.iter_markers()}
    if "rbp" not in marker_names:
        # Auto-authenticate as superuser for non-permission tests
        client.force_authenticate(user=superuser)

    return client


@pytest.fixture
def work_schedules(db):
    """Create work schedules for all weekdays.

    This fixture creates standard work schedules for Monday through Friday:
    - Morning: 08:00-12:00
    - Noon: 12:00-13:00
    - Afternoon: 13:00-17:00

    Returns:
        list: A list of WorkSchedule instances for weekdays.
    """
    from apps.hrm.models import WorkSchedule

    schedules = []
    weekdays = [
        WorkSchedule.Weekday.MONDAY,
        WorkSchedule.Weekday.TUESDAY,
        WorkSchedule.Weekday.WEDNESDAY,
        WorkSchedule.Weekday.THURSDAY,
        WorkSchedule.Weekday.FRIDAY,
    ]

    for weekday in weekdays:
        schedule = WorkSchedule.objects.create(
            weekday=weekday,
            morning_start_time="08:00",
            morning_end_time="12:00",
            noon_start_time="12:00",
            noon_end_time="13:00",
            afternoon_start_time="13:00",
            afternoon_end_time="17:00",
        )
        schedules.append(schedule)

    return schedules


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """
    Modify test items to optimize test execution.

    - Add markers to slow tests for better filtering
    - Ensure tests are properly distributed across workers
    - Auto-categorize tests as unit or integration based on patterns

    Note: Tests can override these auto-markers by explicitly using decorators:
    @pytest.mark.integration, @pytest.mark.unit, @pytest.mark.slow
    """
    for item in items:
        # Skip if test already has explicit markers
        marker_names = {marker.name for marker in item.iter_markers()}

        # Mark tests that interact with external services as slow
        if "slow" not in marker_names:
            if any(keyword in item.nodeid for keyword in ["s3_utils", "opensearch", "consumer", "fcm_service"]):
                item.add_marker(pytest.mark.slow)

        # Auto-categorize as integration or unit tests if not explicitly marked
        has_test_type = "integration" in marker_names or "unit" in marker_names
        if not has_test_type:
            # Integration test patterns:
            # - API/ViewSet tests (test request/response cycle)
            # - Tests with "API" in class name
            # - Tests in api/ directories
            is_integration = (
                "test_api" in item.nodeid
                or "/api/" in item.nodeid
                or "API" in str(item.cls)
                or "ViewSet" in str(item.cls)
            )

            if is_integration:
                item.add_marker(pytest.mark.integration)
            else:
                # Default to unit test for isolated component tests
                item.add_marker(pytest.mark.unit)
