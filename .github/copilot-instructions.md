# Copilot Instructions for This Repository

## ⚠️ PRE-FLIGHT CHECKLIST - READ BEFORE EVERY TASK ⚠️

Before writing ANY code, verify you understand these NON-NEGOTIABLE rules:

- [ ] ✅ **NO Vietnamese text** in code, comments, or docstrings
- [ ] ✅ **ALL API documentation** (`@extend_schema`) must be in English
- [ ] ✅ **ALL API endpoints** must include request and response examples using `OpenApiExample`
- [ ] ✅ **ALL response examples** must use envelope format: `{success: true/false, data: ..., error: ...}`
- [ ] ✅ **ALL user-facing strings** must be wrapped in `gettext()` or `gettext_lazy()`
- [ ] ✅ **Use constants for string values** - Define strings in `constants.py` or module-level constants
- [ ] ✅ **English strings ONLY** - Vietnamese goes in `.po` translation files
- [ ] ✅ **Import translation functions**: `from django.utils.translation import gettext as _`
- [ ] ✅ **Run pre-commit** before committing: `pre-commit run --all-files`
- [ ] ✅ **Update translations**: Run `makemessages` and add Vietnamese translations to `.po` files

**If you violate these rules, your code WILL be rejected.**

## 1. General Principles

### Language Requirements (CRITICAL - MUST FOLLOW)

**⚠️ ABSOLUTELY NO VIETNAMESE TEXT IN CODE ⚠️**

All code, comments, docstrings, and API docs MUST be in **English**. User-facing strings must be:
1. Written in English in code
2. Wrapped in `gettext()` or `gettext_lazy()` (imported as `_`)
3. Translated in `.po` files

**Examples:**
```python
from django.utils.translation import gettext as _

# ✅ CORRECT
error_message = _("Invalid email address")
@extend_schema(summary="List all roles", tags=["Roles"])
class Role(models.Model):
    name = models.CharField(verbose_name=_("Role name"))

# ❌ WRONG - Vietnamese in code
error_message = "Địa chỉ email không hợp lệ"
@extend_schema(summary="Danh sách vai trò")
```

### String Constants and DRY Principle

**Use constants for string values throughout the codebase:**

- **API Documentation**: Define summary, description, and tags as constants
- **Serializer Help Text**: Use constants for help_text values
- **Log Messages**: Define log messages as constants
- **Error Messages**: Use constants for internal error messages (user-facing strings use `gettext()`)

**Examples:**

```python
# ✅ CORRECT - Using constants
# constants.py
API_USER_LIST_SUMMARY = "List all users"
API_USER_LIST_DESCRIPTION = "Retrieve a paginated list of all users in the system"
ERROR_USER_NOT_FOUND = "User not found"
HELP_TEXT_EMAIL = "User's email address"

# views.py
from .constants import API_USER_LIST_SUMMARY, API_USER_LIST_DESCRIPTION

@extend_schema(
    summary=API_USER_LIST_SUMMARY,
    description=API_USER_LIST_DESCRIPTION,
    tags=["Users"],
)
def list_users(request):
    pass

# serializers.py
from .constants import HELP_TEXT_EMAIL

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(help_text=HELP_TEXT_EMAIL)
```

```python
# ❌ WRONG - Hardcoded strings
@extend_schema(
    summary="List all users",  # Should be a constant
    description="Retrieve a paginated list of all users",  # Should be a constant
    tags=["Users"],
)
```

**Exceptions (allowed):**
- Very short strings (≤3 chars): `"id"`, `"pk"`, `"en"`
- Field names and model names: `"email"`, `"username"`
- URLs and paths: `"/api/users"`, `"https://example.com"`
- Format strings: `f"{user.name}"`
- Strings wrapped in `gettext()`: `_("User not found")` (user-facing)

### Other Principles
- **Clarity and Simplicity:** Write clear, maintainable, and self-explanatory code. Follow the DRY (Don't Repeat Yourself) principle.

## 2. Project Architecture & Structure
This project is a Django application with a modular architecture.

* **Django Apps:** The project is divided into distinct Django 'apps' (e.g., `core`, `hrm`, `crm`). Each app has a specific business function. When adding a new feature, identify the correct app to place it in. If the feature is large and distinct enough, propose creating a new app.
* **Module Responsibility:** Adhere strictly to the separation of concerns within each app:
    * `models.py`: Contains only Django model definitions and their methods. For table-related logic, use a custom QuerySet or Manager.
    * `queryset.py`: Contains custom `QuerySet` classes with table-level methods.
    * `views.py`: Contains API view logic for handling requests and responses. Keep views thin.
    * `serializers.py`: Defines DRF serializers for data validation, serialization, and deserialization.
    * `filters.py`: Contains custom FilterSet classes that extend Django Filters FilterSet, used in views and viewsets, unless there are explicit instructions from human.
    * `urls.py`: Manages URL routing for the app.
    * `permissions.py`: Holds custom permission classes for access control.
    * `utils.py`: Contains reusable helper functions specific to the app.
    * `constants.py`: Stores choices, enums, and other constant values to avoid hard-coding.
* **Modularity:** If a module like `models.py` or `views.py` becomes too large, convert it into a package (a directory with an `__init__.py` file that imports only the most important symbols/objects and wraps them in `__all__`) and split the logic into multiple files (e.g., `models/user.py`, `models/profile.py`).
* **Configuration:** All project settings are located in the `settings/` directory. Do not modify settings without a clear and approved reason.

## 3. Coding Style & Linting
- The codebase must strictly adhere to our linting and formatting rules.
- **Tools:** We use `ruff` for both linting and code formatting, and `mypy` for static type checking.
- **Pre-commit:** You MUST run the `pre-commit` hooks to format and lint your code before pushing any changes.
- **Optimization:** For faster iteration, use an incremental validation approach:
  * Start with code reading and analysis (no dependencies needed)
  * Use Python's built-in syntax checking (`python -m py_compile`) for basic validation
  * Run `poetry run ruff check` for targeted files when modifying code
  * Run `mypy` only on files you're modifying, not the entire codebase
  * Defer full pre-commit validation until final changes are ready

### Pre-commit Hooks

The repository includes custom pre-commit hooks to enforce code quality:

**1. Vietnamese Text Check** (`check-no-vietnamese`)
- **Purpose**: Prevents Vietnamese text in code, comments, and docstrings
- **Status**: **BLOCKING** - Commits will fail if Vietnamese text is detected
- **Allows**: Vietnamese in `.po` translation files, migrations (historical data)
- **Script**: `scripts/check_no_vietnamese.py`

**2. String Constants Check** (`check-string-constants`)
- **Purpose**: Encourages using constants instead of hardcoded strings
- **Status**: **WARNING ONLY** - Won't block commits, but will warn developers
- **Flags**: API documentation, help text, log messages without constants
- **Allows**: `gettext()` wrapped strings, field names, URLs, short strings (≤3 chars)
- **Script**: `scripts/check_string_constants.py`

**Running Hooks Manually:**
```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run specific hooks
pre-commit run check-no-vietnamese --all-files
pre-commit run check-string-constants --all-files

# Test the scripts directly
python scripts/check_no_vietnamese.py apps/core/models.py
python scripts/check_string_constants.py apps/core/api/views.py
```

## 4. Testing
- **TDD Approach:** Write tests **before** implementing or modifying code when working on business logic. For documentation-only changes, bug fixes with existing tests, or minor refactors, tests may not be needed.
- **AAA Pattern:** Structure all tests using the Arrange-Act-Assert (AAA) pattern.
    1.  **Arrange:** Set up the test data and initial state using Django ORM objects.
    2.  **Act:** Execute the function or make the API call you are testing.
    3.  **Assert:** Verify the outcome is as expected.
- **Database:** Do **not** mock the database unless there are explicit human instructions. Create real model instances for testing via the Django ORM.
- **Fixtures:** Reuse test data by creating Pytest fixtures. For widely used fixtures, define them in a higher-level `conftest.py` file to broaden their scope.
- **Execution:** Run relevant tests after making code changes to ensure nothing is broken. For performance:
  * Start by understanding the existing test structure without running tests
  * Run only the specific test files related to your changes (e.g., `pytest apps/hrm/tests/test_models.py`)
  * Run full test suite only before final commit if making significant changes
  * For documentation-only changes, skip running tests entirely

## 5. Documentation & Internationalization (i18n)

### Internationalization (i18n) - CRITICAL RULES

**This project uses Django's i18n framework with Vietnamese as the default language.**

#### Step-by-Step Process for ALL User-Facing Strings:

1. **Write in English ONLY**
   ```python
   # ✅ CORRECT
   message = _("User not found")
   ```

2. **Import the translation function**
   ```python
   from django.utils.translation import gettext as _          # For runtime
   from django.utils.translation import gettext_lazy as _     # For models/class-level
   ```

3. **Wrap ALL user-facing strings**
   - Error messages: `raise ValidationError(_("Invalid email"))`
   - Model fields: `verbose_name=_("User name")`
   - API responses: `{"detail": _("Success")}`
   - Help text: `help_text=_("Enter your email")`
   - Choice labels: `choices=[("active", _("Active"))]`

4. **Update translation files**
   ```bash
   poetry run python manage.py makemessages -l vi --no-obsolete
   # Then edit locale/vi/LC_MESSAGES/django.po to add Vietnamese translations
   poetry run python manage.py compilemessages
   ```

#### API Documentation (drf-spectacular)

**ALL API documentation MUST be in English and include examples:**

##### Response Envelope Format (CRITICAL - MANDATORY)

**ALL API response examples MUST use the standard envelope format:**

This project uses `ApiResponseWrapperMiddleware` which wraps all responses. The `wrap_with_envelope` hook automatically updates the OpenAPI schema, but **examples must manually include this envelope structure**.

**Formats:**

Success (single item): `{"success": true, "data": {...}, "error": null}`  
Success (list with pagination): `{"success": true, "data": {"count": N, "next": "...", "previous": null, "results": [...]}, "error": null}`  
Success (list no pagination): `{"success": true, "data": [...], "error": null}`  
Error: `{"success": false, "data": null, "error": "..." or {...}}`

**Example:**
```python
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    summary="List all roles",
    tags=["Roles"],
    examples=[
        OpenApiExample(
            "Success",
            value={"success": True, "data": {"count": 1, "next": None, "previous": None, "results": [{"id": 1, "name": "Admin"}]}},
            response_only=True,
        ),
        OpenApiExample(
            "Error",
            value={"success": False, "error": {"field": ["Error message"]}},
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
```

**Requirements:**
1. Use envelope format: `{success, data, error}`
2. Include success AND error examples
3. List endpoints with pagination: Include `count`, `next`, `previous`, `results` in `data`
4. All text in English only

#### Other Documentation Requirements

* **Docstrings & Comments:** Document all public modules, classes, and functions with clear docstrings in English. Use comments to explain complex or non-obvious logic.
* **Diagrams:** For any new feature or refactor that significantly impacts a workflow, you must generate a diagram (e.g., sequence, flowchart) using Mermaid format and save it in the project's shared documentation folder.
* **Translation Files (PO):** Before committing, update the `.po` translation files.
    * Rerun `makemessages` to update all `msgid` entries and metadata.
    * Add Vietnamese translations for any new strings.
    * Resolve any strings marked as "fuzzy".
    * If a string's meaning is ambiguous, investigate its context. Add a context comment in the code (e.g., `_("...") # CONTEXT: ...`) and the `.po` file to clarify its meaning for translators. If still unclear, ask the project lead.

#### Documentation Files - What NOT to Create

**⚠️ CRITICAL: Do NOT create unnecessary documentation files ⚠️**

**Copilot must ONLY generate documentation that is truly necessary and directly related to business flows and logic.**

**FORBIDDEN Documentation Types** (these are considered WASTE and must NOT be created):
* ❌ **Task planning documents**: `TASK_PLAN.md`, `WORK_PLAN.md`
* ❌ **Work summaries**: `WORK_SUMMARY.md`, `TASK_SUMMARY.md`
* ❌ **Implementation summaries**: `*_IMPLEMENTATION_SUMMARY.md`, `*_SUMMARY.md`
* ❌ **Issue resolution docs**: `ISSUE_RESOLUTION_*.md`, `ISSUE_*.md`
* ❌ **Checklists**: `*_CHECKLIST.md`, `*_MIGRATION_CHECKLIST.md`
* ❌ **Quick reference cards**: `*_QUICK_REFERENCE.md`, `*_REFERENCE.md`
* ❌ **Compliance/instruction documents**: `INSTRUCTION_COMPLIANCE.md`, `COPILOT_VALIDATION.md`
* ❌ **Review documents**: `*_REVIEW.md`, `CODE_*_REVIEW.md`
* ❌ **Optimization summaries**: `*_OPTIMIZATION_SUMMARY.md`, `CI_OPTIMIZATION_*.md`
* ❌ **Comparison documents**: `*_COMPARISON.md`, `*_WORKFLOW_COMPARISON.md`

**Why these are forbidden:**
- PR descriptions already contain task information
- Commit messages already explain what was done and why
- These docs become outdated and misleading
- They waste time and clutter the repository
- They provide no value to end users or future developers

**ONLY create documentation when:**
* ✅ Adding a **new feature** that requires **user-facing documentation**
* ✅ Documenting **API endpoints** (with examples) for integration
* ✅ Updating **existing documentation** (README, API docs)
* ✅ Creating **technical design documents** explicitly requested by the team lead
* ✅ Adding **architecture diagrams** for significant changes (Mermaid format)
* ✅ Documenting **business logic and workflows** that are complex and need explanation

**Before creating ANY documentation file, ask yourself:**
1. Does this document business logic or workflows?
2. Will this help users/developers integrate with the system?
3. Was this explicitly requested by the team lead?

If all answers are "NO", **DO NOT create the file**.

**Remember:** Excessive documentation is WASTE. Focus on clean code, good commit messages, and thorough PR descriptions.

## 6. Version Control (Git)
* **Branching:** All work must be done on a feature or fix branch created from `master`. Never commit directly to `master`.
* **Branch Naming Convention:** Branch names should be descriptive and follow these rules:
    * Use the related issue's title as the basis for the branch name, not random strings.
    * Convert the issue title to lowercase.
    * Strip special characters (keep only alphanumeric characters and hyphens).
    * Remove leading and trailing spaces.
    * Replace spaces with hyphens (`-`).
    * Keep the branch name concise and not too long (ideally under 50 characters).
    * **Example:** Issue title "Update Copilot Instructions" → branch name `update-copilot-instructions`
* **Commit Messages:** Follow the Conventional Commits specification.
    * **Format:** `type(scope): short description` (e.g., `feat(hrm): add employee performance review model`).
    * **Description:** The body of the commit message should explain **why** the change was made, not just **what** was changed.

## 7. Security Best Practices
* **Secrets:** **NEVER** hard-code sensitive information (API keys, passwords, secret keys). Always use environment variables.
* **Input Validation:** Always validate and sanitize all user-provided input, especially from API requests, using DRF serializers.
* **Database Queries:** Use the Django ORM exclusively for database interactions. Avoid raw SQL queries to prevent SQL injection vulnerabilities.

## 8. Dependencies
* Do **not** add any new third-party libraries or packages to the project without prior discussion and approval from the team lead.

## 9. Common Violations - NEVER DO THESE

**❌ Vietnamese text in code** - Use English + `gettext()`: `_("Invalid email")` not `"Email không hợp lệ"`

**❌ Vietnamese in API docs** - `@extend_schema(summary="List roles")` not `summary="Danh sách vai trò"`

**❌ Missing envelope** - Always use `{"success": true/false, "data": ..., "error": ...}` in response examples

**❌ Missing pagination** - List endpoints: `{"success": true, "data": {"count": N, "results": [...]}}` not direct array

**❌ Forgot translations** - After adding `_()` strings, run: `poetry run python manage.py makemessages -l vi --no-obsolete`

**✅ Before committing:** Run `pre-commit run --all-files`

## 10. Performance & Optimization for Agent Tasks
To ensure fast iteration and minimize startup time:

### Initial Assessment (No Dependencies Required)
When starting a task, perform lightweight exploration first:
* Read and understand relevant files using the `view` tool
* Analyze code structure and identify files to modify
* Review existing tests to understand coverage
* Check git history if needed for context

### When to Install Dependencies
Only install Poetry dependencies (`poetry install`) when:
* You need to run tests
* You need to execute Django management commands
* You need to run the actual application code
* You're validating database migrations

### When to Run Validation
* **Documentation changes**: No validation needed, just ensure markdown/text is correct
* **Configuration changes**: Quick syntax check with `ruff check` (no deps needed)
* **Code changes**: Run targeted tests for affected modules only
* **Before final commit**: Run full linting (`pre-commit run --all-files`) and relevant test suite

### Optimization Strategies
1. **Defer Dependency Installation**: Analyze and plan changes first, install only when necessary
2. **Use Targeted Testing**: Run `pytest path/to/specific/test.py` instead of full suite
3. **Use Incremental Validation**: Start with basic syntax checks, then progress to linting and testing
4. **Skip Unnecessary Steps**: Don't run Django checks for documentation changes
5. **Leverage CI/CD**: Trust that the CI/CD pipeline will catch issues; focus on your specific changes
6. **Batch Operations**: When multiple files need checking, do it in a single command rather than one-by-one

### Quick Reference Commands
```bash
# Lightweight syntax validation (analyze without running code)
python -m py_compile apps/core/models.py  # Basic syntax check

# Fast linting with ruff (via Poetry)
poetry run ruff check apps/ libs/ settings/
poetry run ruff format --check apps/ libs/ settings/

# Run specific test file (requires dependencies)
poetry run pytest apps/core/tests/test_models.py -v

# Run tests for a specific app (requires dependencies)
poetry run pytest apps/hrm/ -v

# Type check specific files (requires dependencies)
poetry run mypy apps/hrm/models.py
```
