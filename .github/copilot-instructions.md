# Copilot Instructions for This Repository

## 1. General Principles
- **Language:** All code, comments, variable names, and documentation must be in **English**.
- **User-Facing Strings:** All strings intended for the end-user must be wrapped in Django's translation functions (e.g., `gettext` or `_()`).
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
* **Docstrings & Comments:** Document all public modules, classes, and functions with clear docstrings. Use comments to explain complex or non-obvious logic.
* **API Documentation:** You must use `drf-spectacular` to add decorators and docstrings to API Views and ViewSets. This ensures that our API documentation is automatically generated and up-to-date.
* **Diagrams:** For any new feature or refactor that significantly impacts a workflow, you must generate a diagram (e.g., sequence, flowchart) using Mermaid format and save it in the project's shared documentation folder.
* **Translation Files (PO):** Before committing, update the `.po` translation files.
    * Rerun `makemessages` to update all `msgid` entries and metadata.
    * Add translations for any new strings.
    * Resolve any strings marked as "fuzzy".
    * If a string's meaning is ambiguous, investigate its context. Add a context comment in the code (e.g., `_("...") # CONTEXT: ...`) and the `.po` file to clarify its meaning for translators. If still unclear, ask the project lead.

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

## 9. Performance & Optimization for Agent Tasks
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
