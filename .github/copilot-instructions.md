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

This is a **NON-NEGOTIABLE** requirement. All code must be in English.

- **ALL Code:** Variable names, function names, class names, comments, docstrings must be in **English**.
- **API Documentation:** ALL drf-spectacular decorators (`summary`, `description`, `tags`) must be in **English**.
- **User-Facing Strings:** ALL strings shown to end-users must be:
  1. Written in **English** in the code
  2. Wrapped in Django's translation functions: `gettext()` or `gettext_lazy()` (imported as `_`)
  3. Translated in `.po` files

**Examples of CORRECT usage:**
```python
from django.utils.translation import gettext as _

# ✅ CORRECT - English string wrapped in gettext
error_message = _("Invalid email address")

# ✅ CORRECT - API documentation in English
@extend_schema(
    summary="List all roles",
    description="Retrieve a list of all roles in the system",
    tags=["Roles"],
)

# ✅ CORRECT - Model verbose names in English
class Role(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Role name"))
```

**Examples of INCORRECT usage (NEVER DO THIS):**
```python
# ❌ WRONG - Vietnamese directly in code
error_message = "Địa chỉ email không hợp lệ"

# ❌ WRONG - API documentation in Vietnamese
@extend_schema(
    summary="Danh sách vai trò",
    description="Lấy danh sách tất cả vai trò trong hệ thống",
    tags=["Vai trò"],
)

# ❌ WRONG - Model verbose names in Vietnamese
class Role(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên vai trò")
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

This project uses `ApiResponseWrapperMiddleware` which wraps all responses in a consistent envelope. The `wrap_with_envelope` hook in `libs/spectacular/schema_hooks.py` automatically updates the OpenAPI schema, but **examples must manually include this envelope structure**.

**Success Response Format:**
```json
{
  "success": true,
  "data": <actual response data>,
  "error": null
}
```

**Error Response Format:**
```json
{
  "success": false,
  "data": null,
  "error": <error details>
}
```

**Error details can be:**
- A string: `"error": "User not found"`
- An object with field errors: `"error": {"email": ["Invalid email format"], "password": ["Too short"]}`
- An object with a message: `"error": {"detail": "Permission denied"}`

**Pagination Response Format (for list endpoints):**

List endpoints that use pagination MUST include pagination metadata within the `data` field:
```json
{
  "success": true,
  "data": {
    "count": 123,
    "next": "http://api.example.org/endpoint/?page=2",
    "previous": null,
    "results": [
      <array of items>
    ]
  }
}
```

**Important:** List endpoints WITHOUT pagination (with `pagination_class = None`) should use direct array in `data`:
```json
{
  "success": true,
  "data": [
    <array of items>
  ]
}
```

##### Complete Example with Envelope Format

```python
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample

# ✅ CORRECT - English with envelope format
@extend_schema_view(
    list=extend_schema(
        summary="List all roles",
        description="Retrieve a list of all roles in the system",
        tags=["Roles"],
        examples=[
            OpenApiExample(
                "List roles example",
                description="Example response when listing roles",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "VT001",
                                "name": "System Admin",
                                "description": "Full system access",
                                "is_system_role": True,
                                "created_by": "System",
                                "permissions_detail": [
                                    {"id": 1, "code": "user.create", "name": "Create User"}
                                ],
                                "created_at": "2025-01-01T00:00:00Z",
                                "updated_at": "2025-01-01T00:00:00Z"
                            }
                        ]
                    }
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new role",
        description="Create a new role in the system",
        tags=["Roles"],
        examples=[
            OpenApiExample(
                "Create role request",
                description="Example request to create a new role",
                value={
                    "name": "Manager",
                    "description": "Manager role",
                    "permission_ids": [1, 2, 3]
                },
                request_only=True,
            ),
            OpenApiExample(
                "Create role success response",
                description="Success response when creating a role",
                value={
                    "success": True,
                    "data": {
                        "id": 5,
                        "code": "VT005",
                        "name": "Manager",
                        "description": "Manager role",
                        "is_system_role": False,
                        "created_by": "admin@example.com",
                        "permissions_detail": [
                            {"id": 1, "code": "user.view", "name": "View User"}
                        ],
                        "created_at": "2025-01-15T10:30:00Z",
                        "updated_at": "2025-01-15T10:30:00Z"
                    }
                },
                response_only=True,
            ),
            OpenApiExample(
                "Create role validation error",
                description="Error response when validation fails",
                value={
                    "success": False,
                    "error": {
                        "name": ["Role name already exists"],
                        "permission_ids": ["At least one permission must be selected"]
                    }
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get role details",
        description="Retrieve detailed information about a specific role",
        tags=["Roles"],
        examples=[
            OpenApiExample(
                "Get role success",
                description="Success response when retrieving a role",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "VT001",
                        "name": "System Admin",
                        "description": "Full system access",
                        "is_system_role": True,
                        "created_by": "System",
                        "permissions_detail": [
                            {"id": 1, "code": "user.create", "name": "Create User"}
                        ],
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z"
                    }
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get role not found",
                description="Error response when role is not found",
                value={
                    "success": False,
                    "error": "Role not found"
                },
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
)
```

**Mandatory Requirements for ALL API Endpoints:**

1. **Use Envelope Format**: ALL response examples MUST wrap data in `{success: true/false, data: ..., error: ...}` structure
2. **Include Examples**: Every API endpoint MUST have at least one example for both request (if applicable) and response
3. **Cover Success Cases**: Always include a success response example with `success: true` and `data` field
4. **Cover Error Cases**: Include error response examples with `success: false` and `error` field for validation errors, not found, etc.
5. **Use OpenApiExample**: Use `OpenApiExample` from `drf_spectacular.utils`
6. **Realistic Data**: Examples should use realistic, meaningful data that helps developers understand the API
7. **English Only**: All example data and descriptions must be in English

**❌ NEVER use Vietnamese in API documentation decorators or examples!**

**❌ NEVER omit the envelope structure (`success`, `data`, `error` fields) from response examples!**

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

This section lists common mistakes that violate our standards. Review this before every change.

### ❌ Vietnamese Text in Code

**NEVER write Vietnamese directly in code:**

```python
# ❌ WRONG
error_message = "Địa chỉ email không hợp lệ"
raise PermissionDenied("Bạn không có quyền thực hiện hành động này")

# ✅ CORRECT
from django.utils.translation import gettext as _
error_message = _("Invalid email address")
raise PermissionDenied(_("You do not have permission to perform this action"))
```

### ❌ Vietnamese API Documentation

**NEVER use Vietnamese in drf-spectacular decorators:**

```python
# ❌ WRONG
@extend_schema(
    summary="Danh sách vai trò",
    description="Lấy danh sách tất cả vai trò trong hệ thống",
    tags=["Vai trò"],
)

# ✅ CORRECT
@extend_schema(
    summary="List all roles",
    description="Retrieve a list of all roles in the system",
    tags=["Roles"],
)
```

### ❌ Vietnamese Model Verbose Names

**NEVER use Vietnamese in model field definitions:**

```python
# ❌ WRONG
class Role(models.Model):
    code = models.CharField(max_length=50, verbose_name="Mã vai trò")
    name = models.CharField(max_length=100, verbose_name="Tên vai trò")

# ✅ CORRECT
from django.utils.translation import gettext_lazy as _

class Role(models.Model):
    code = models.CharField(max_length=50, verbose_name=_("Role code"))
    name = models.CharField(max_length=100, verbose_name=_("Role name"))
```

### ❌ Missing Response Envelope Format

**NEVER create response examples without the envelope structure:**

```python
# ❌ WRONG - Missing envelope
OpenApiExample(
    "List users",
    value=[
        {"id": 1, "name": "John"},
        {"id": 2, "name": "Jane"}
    ],
    response_only=True,
)

# ❌ WRONG - Missing data field
OpenApiExample(
    "Create user success",
    value={
        "success": True,
        "id": 5,
        "name": "John Doe"
    },
    response_only=True,
)

# ✅ CORRECT - Success with envelope
OpenApiExample(
    "List users success",
    value={
        "success": True,
        "data": [
            {"id": 1, "name": "John"},
            {"id": 2, "name": "Jane"}
        ]
    },
    response_only=True,
)

# ✅ CORRECT - Error with envelope
OpenApiExample(
    "Create user validation error",
    value={
        "success": False,
        "error": {
            "name": ["This field is required"],
            "email": ["Invalid email format"]
        }
    },
    response_only=True,
    status_codes=["400"],
)
```

### ❌ Forgetting to Update Translation Files

**ALWAYS update .po files when adding new translatable strings:**

```bash
# After adding new gettext strings, ALWAYS run:
poetry run python manage.py makemessages -l vi --no-obsolete

# Then edit locale/vi/LC_MESSAGES/django.po and add Vietnamese translations:
msgid "Invalid email address"
msgstr "Địa chỉ email không hợp lệ"

# Finally compile:
poetry run python manage.py compilemessages
```

### ✅ Self-Check Before Committing

Before using `report_progress`, run pre-commit to validate all changes:

```bash
pre-commit run --all-files
```

This will automatically check for Vietnamese text, linting issues, and other code quality problems.

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
