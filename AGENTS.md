# Project Instructions for AI Coding Agents

This file provides instructions for AI coding agents working on the MVL ERP Backend project.

## Project Overview

- **Project**: MaiVietLand ERP Backend
- **Framework**: Django 5.2.6 + Django REST Framework
- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Virtual Environment**: `.venv` directory

## Setup Instructions

### 1. Install Dependencies

```bash
poetry install --with dev
```

### 2. Environment Configuration

```bash
cp .env.tpl .env
# Edit .env with appropriate values
```

### 3. Database Migrations

```bash
poetry run python manage.py migrate
```

## Running Tests

```bash
# CRITICAL: Always set ENVIRONMENT=test
ENVIRONMENT=test poetry run pytest

# Run specific test file
ENVIRONMENT=test poetry run pytest apps/hrm/tests/test_models.py -v

# Run specific app tests
ENVIRONMENT=test poetry run pytest apps/hrm/ -v
```

## Code Quality Commands

```bash
# Linting
poetry run ruff check apps/ libs/ settings/
poetry run ruff format --check apps/ libs/ settings/

# Type checking
poetry run mypy apps/

# Pre-commit (run before committing)
pre-commit run --all-files
```

## Critical Rules

### Code Language
- **NO Vietnamese text** in code, comments, or docstrings
- All code, API documentation, and comments must be in **English only**
- Vietnamese translations go in `.po` files only

### API Documentation
- Use `@extend_schema` with English `summary` and `tags`
- Include `OpenApiExample` for request/response examples
- All responses use envelope format: `{"success": true/false, "data": ..., "error": ...}`

### Required Custom Classes
- **Use `SafeTextField`** instead of `models.TextField` (XSS prevention)
- **Use `PhraseSearchFilter`** instead of `SearchFilter` in ViewSets

### Translation (i18n)
- Wrap **user-facing strings only** with `gettext()` or `gettext_lazy()`
- **DO NOT translate**: `verbose_name`, `help_text`, `Meta.verbose_name` (admin-facing)
- Import: `from django.utils.translation import gettext as _`

### Imports
- ALL imports must be at the **top of the file** (avoid `E402` linting errors).
- Never import inside functions or methods.
- Use `ruff` with `--fix` to auto-sort and organize imports.

### Testing
- **Framework**: Use `pytest` exclusively. **DO NOT** use `unittest.TestCase`.
- **Database**: Use `@pytest.mark.django_db` for tests requiring database access.
- **Fixtures**: Use `pytest` fixtures for setup and reusable data. **DO NOT** use `setUp()` or `tearDown()` methods.
- **Assertions**: Use standard `assert` statements instead of `self.assert*`.
- **Imports**: Ensure all imports are at the **top of the file**. `import pytest` and other imports must precede any code to avoid `E402` errors.
- **External Services**: Mock external APIs and network connections.
- **Cleanliness**: Ensure tests are independent and do not leak state.

## Project Structure

```
apps/           # Django applications (core, hrm, crm)
libs/           # Shared libraries and utilities
settings/       # Django settings
tests/          # Global test utilities
docs/           # Documentation
scripts/        # Utility scripts
locale/         # Translation files (.po)
```

## Architecture Guidelines

| File | Purpose |
|------|---------|
| `models.py` | Django models and methods |
| `queryset.py` | Custom QuerySet classes |
| `views.py` | API views (keep thin) |
| `serializers.py` | DRF serializers |
| `filters.py` | Custom FilterSet classes |
| `permissions.py` | Permission classes |
| `constants.py` | Choices, enums, constants |

## Version Control

- **Branch from**: `master`
- **Commit format**: `type(scope): description` (Conventional Commits)
- **Example**: `feat(hrm): add employee performance review model`

## Forbidden Actions

- ❌ Do not add new dependencies without approval
- ❌ Do not create unnecessary documentation files (TASK_PLAN.md, etc.)
- ❌ Do not commit directly to `master`
- ❌ Do not hard-code sensitive information

## Pre-commit Enforcement

> [!IMPORTANT]
> **Before completing any task or handing off work**, agents MUST:

1. Run `pre-commit run --all-files` (or at minimum on changed files).
2. **Fix ALL issues** reported by hooks (linting, formatting, type checking, Vietnamese text, etc.).
3. Ensure all tests pass before considering work complete.

This is non-negotiable. All code must pass pre-commit checks before it can be considered ready for review or merge.
