# GitHub Copilot Instructions

> **Primary Reference**: See [AGENTS.md](../AGENTS.md) for complete project guidelines.

## Critical Rules

These rules are **BLOCKING** - violations will be rejected:

1. **NO Vietnamese text** in code, comments, or docstrings - English only
2. **Use SafeTextField** instead of `models.TextField` (XSS prevention)
3. **Use PhraseSearchFilter** instead of `SearchFilter` in ViewSets
4. **Use `poetry run`** to run Python commands
5. **Set ENVIRONMENT=test** when running pytest
6. **All imports at top** of files - never inside functions
7. **ALL API endpoints** must include `@extend_schema` with `OpenApiExample`
8. **Response envelope format**: `{"success": true/false, "data": ..., "error": ...}`

## Quick Commands

```bash
# Setup
poetry install --with dev

# Tests (CRITICAL: always set ENVIRONMENT=test)
ENVIRONMENT=test poetry run pytest

# Code quality
poetry run ruff check apps/ libs/ settings/
poetry run mypy apps/
pre-commit run --all-files
```

## Project Info

- **Framework**: Django 5.2.6 + Django REST Framework
- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Database**: PostgreSQL

## API Documentation Requirements

All API endpoints must use `@extend_schema` with:
- English `summary` and `tags`
- `OpenApiExample` for request/response examples
- Response envelope format: `{"success": true/false, "data": ..., "error": ...}`

```python
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    summary="List all items",
    tags=["Items"],
    examples=[
        OpenApiExample(
            "Success",
            value={"success": True, "data": {"count": 1, "results": [...]}},
            response_only=True,
        ),
    ],
)
```

## i18n Rules

- Wrap **user-facing strings only** with `gettext()` or `gettext_lazy()`
- **DO NOT translate**: `verbose_name`, `help_text`, `Meta.verbose_name`
- Import: `from django.utils.translation import gettext as _`

## Testing Rules

- Follow **AAA pattern**: Arrange, Act, Assert
- **Mock external services** (APIs, network connections)
- **DO NOT mock database** - use real Django ORM objects
- Correct mock path: `@patch('apps.module.file.ImportedClass')` (where imported, not defined)

## Forbidden Actions

- ❌ Do not add new dependencies without approval
- ❌ Do not create unnecessary docs (TASK_PLAN.md, WORK_SUMMARY.md, etc.)
- ❌ Do not commit directly to `master`
- ❌ Do not hard-code sensitive information
