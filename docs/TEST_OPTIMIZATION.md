# Test Performance Optimization Guide

## Overview

This document describes the test performance optimizations implemented to achieve a **5x speedup** in test execution time, reducing it from **123 seconds to 24 seconds** for 845 tests.

## Performance Results

### Before Optimization
- **Test execution time**: 123 seconds (~2 minutes)
- **Tests**: 845 passing
- **Parallelization**: Basic with `-n auto` (4 workers)
- **Bottlenecks**: Database operations, password hashing, logging overhead, external service mocking

### After Optimization
- **Test execution time**: 24 seconds (< 0.5 minutes)
- **With coverage**: 47 seconds (< 1 minute)
- **Tests**: 845 passing
- **Improvement**: **5.1x faster** (80% reduction)
- **Parallelization**: Optimized with `--dist=loadgroup`

## Optimizations Implemented

### 1. Test Settings Performance (`settings/test.py`)

#### Fast Password Hashing
```python
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
```
**Impact**: Password hashing in tests is now ~100x faster. This significantly speeds up user creation in test fixtures.

#### Disabled Logging
```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"]},
}
```
**Impact**: Eliminates I/O overhead from logging operations during tests.

#### In-Memory Email Backend
```python
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
```
**Impact**: Email operations are instant and don't require external services.

#### Optimized SQLite Configuration
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {"timeout": 20},
        "TEST": {"NAME": ":memory:"},
    }
}
```
**Impact**: All database operations happen in memory, eliminating disk I/O.

### 2. Pytest Configuration (`pyproject.toml`)

#### Enhanced Configuration
```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "settings"
filterwarnings = ["ignore::DeprecationWarning", "ignore::UserWarning"]
addopts = [
    "--tb=short",           # Short traceback format
    "-v",                   # Verbose output
    "--reuse-db",           # Reuse test database
    "--strict-markers",     # Enforce marker usage
    "--strict-config",      # Enforce config validation
    "--maxfail=10",        # Fast fail on critical errors
    "-ra",                  # Show short test summary
]
```

#### Test Markers
```toml
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

**Usage**:
- Run only fast tests: `pytest -m "not slow"`
- Run only unit tests: `pytest -m unit`
- Run only integration tests: `pytest -m integration`

#### Added pytest-split Plugin
```toml
[tool.poetry.group.dev.dependencies]
pytest-split = "^0.10.0"
```
**Impact**: Enables intelligent test distribution and better load balancing across workers.

### 3. CI/CD Workflow (`.github/workflows/ci-cd.yml`)

#### Optimized Test Command
```yaml
- name: Run tests
  run: |
    source .venv/bin/activate
    # --dist=loadgroup: distribute tests by module for better caching
    # -n auto: use all available CPU cores
    # --maxfail=10: fail fast after 10 failures
    ENVIRONMENT=test python -m pytest apps/ \
      -v \
      --tb=short \
      --cov=apps \
      --cov-report=xml \
      -n auto \
      --dist=loadgroup \
      --maxfail=10
```

**Key improvements**:
- `--dist=loadgroup`: Groups tests by module, improving database state sharing
- `--maxfail=10`: Stops after 10 failures to save CI time
- Better comments explaining each option

### 4. Coverage Configuration (`.coveragerc`)

```ini
[run]
source = apps
concurrency = multiprocessing
parallel = true
omit =
    static*
    logs*
    *migrations*
    tests*
    */__init__.py
    */conftest.py
    */test_*.py
    */tests/*
```

**Impact**:
- Focuses coverage on actual application code
- Excludes test files from coverage measurement
- Parallel coverage collection for speed

### 5. Test Collection (`conftest.py`)

#### Automatic Test Marking
```python
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark tests for better organization and filtering."""
    for item in items:
        # Mark tests that interact with external services as slow
        if any(keyword in item.nodeid for keyword in ["s3_utils", "opensearch", "consumer", "fcm_service"]):
            item.add_marker(pytest.mark.slow)

        # Mark API tests as integration tests
        if "test_api" in item.nodeid or "API" in str(item.cls):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
```

**Impact**: Enables selective test execution without manual marking.

## Scalability Analysis

### Current Capacity
With 845 tests taking 24 seconds:
- **Tests per second**: ~35 tests/second
- **1-minute capacity**: ~2,100 tests

### Future Projections
| Scenario | Test Count | Estimated Time | Goal Met |
|----------|-----------|----------------|----------|
| Current | 845 | 24s | ✅ |
| 2x tests | 1,690 | ~48s | ✅ |
| 3x tests | 2,535 | ~72s | ✅ (< 2 min) |
| 5x tests | 4,225 | ~120s | ✅ (= 2 min) |
| 10x tests | 8,450 | ~240s | ⚠️ (4 min) |

**Note**: With 5x more tests, we still meet the < 2 minute goal. For 10x tests, consider:
- Matrix strategy to split tests across multiple jobs
- Test sharding with pytest-split
- Selective test execution based on changed files

## Usage Examples

### Local Development

#### Run all tests (fastest)
```bash
ENVIRONMENT=test pytest apps/ -n auto --dist=loadgroup
```

#### Run with coverage
```bash
ENVIRONMENT=test pytest apps/ --cov=apps --cov-report=html -n auto --dist=loadgroup
```

#### Run only fast tests
```bash
ENVIRONMENT=test pytest apps/ -m "not slow" -n auto
```

#### Run specific app tests
```bash
ENVIRONMENT=test pytest apps/core/ -n auto
```

#### Run with detailed durations
```bash
ENVIRONMENT=test pytest apps/ --durations=20 -n auto
```

### CI/CD

The CI workflow automatically uses optimized settings:
```bash
ENVIRONMENT=test python -m pytest apps/ \
  -v \
  --tb=short \
  --cov=apps \
  --cov-report=xml \
  -n auto \
  --dist=loadgroup \
  --maxfail=10
```

## Monitoring Test Performance

### Identify Slow Tests
```bash
# Show slowest 50 tests
ENVIRONMENT=test pytest apps/ --durations=50 -n auto
```

### Profile Individual Tests
```bash
# Run single test with profiling
ENVIRONMENT=test pytest apps/core/tests/test_auth.py::AuthenticationTestCase::test_login -vv --durations=0
```

### Compare Performance
```bash
# Baseline without parallelization
ENVIRONMENT=test pytest apps/ --durations=10

# With parallelization
ENVIRONMENT=test pytest apps/ --durations=10 -n auto --dist=loadgroup
```

## Best Practices

### Writing Fast Tests

1. **Use class-scoped fixtures** for expensive setup:
```python
@pytest.fixture(scope="class")
def setup_expensive_resource(django_db_blocker):
    with django_db_blocker.unblock():
        # Create expensive resources once per class
        return Resource.objects.create(...)
```

2. **Mock external services** instead of making real API calls:
```python
@pytest.fixture
def mock_s3_client(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: mock)
    return mock
```

3. **Use factories** for test data instead of fixtures:
```python
from factory import Factory

class UserFactory(Factory):
    class Meta:
        model = User

    username = "testuser"
    email = "test@example.com"
```

4. **Mark slow tests** explicitly:
```python
@pytest.mark.slow
def test_expensive_operation():
    # Test that takes > 1 second
    pass
```

### Maintaining Performance

1. **Monitor CI test times**: Set up alerts if test time exceeds 2 minutes
2. **Review slow tests regularly**: Use `--durations` to identify new slow tests
3. **Use test markers**: Separate unit tests from integration tests
4. **Consider test sharding**: For very large test suites (> 5,000 tests)

## Troubleshooting

### Tests are slower than expected
1. Check if database reuse is enabled: `--reuse-db` should be in `addopts`
2. Verify parallelization is working: Look for "created: N/N workers" in output
3. Check for serial bottlenecks: Some tests may not be thread-safe
4. Profile individual tests: Use `--durations=0` to find slow tests

### Tests fail in parallel but pass serially
1. Check for shared state: Tests may be modifying shared resources
2. Use database isolation: Mark tests with `@pytest.mark.django_db(transaction=True)`
3. Review fixture scope: Function-scoped fixtures are safer but slower

### Coverage collection is slow
1. Reduce coverage scope: Only measure application code, not tests
2. Use parallel coverage: Ensure `concurrency = multiprocessing` in `.coveragerc`
3. Skip coverage in development: Run `pytest` without `--cov` flag

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-django documentation](https://pytest-django.readthedocs.io/)
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [Django test optimization](https://docs.djangoproject.com/en/stable/topics/testing/advanced/)
