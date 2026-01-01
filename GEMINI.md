# Gemini CLI Instructions

> **Primary Reference**: See [AGENTS.md](./AGENTS.md) for complete project guidelines.

## Quick Setup

```bash
# Install dependencies
poetry install --with dev
```

## Running Tests

```bash
# CRITICAL: Always set ENVIRONMENT=test
ENVIRONMENT=test poetry run pytest

# Specific tests
ENVIRONMENT=test poetry run pytest apps/hrm/tests/test_models.py -v
```

## Code Quality

```bash
poetry run ruff check apps/ libs/ settings/
poetry run mypy apps/
pre-commit run --all-files
```

## Critical Rules Summary

1. **No Vietnamese** in code/comments - English only
2. **Use SafeTextField** instead of `models.TextField`
3. **Use PhraseSearchFilter** instead of `SearchFilter`
4. **Use `poetry run`** to run Python commands
5. **Set ENVIRONMENT=test** when running pytest
6. **All imports at top** of files - never inside functions

## Project Info

- Django 5.2.6 + DRF
- Python 3.12+
- Poetry for dependencies
- PostgreSQL database
