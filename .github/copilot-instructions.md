# Copilot Instructions for This Repository

## Human Summary

This file contains comprehensive coding guidelines and instructions for GitHub Copilot when working on this Django ERP backend project.

**Important Notes:**
- **The JSON prompt MUST be embedded within this `.md` file** - do not create separate `.json` files
- **GitHub Copilot only reads guidance from this file** and will not automatically consume external JSON files
- All instructions are provided in both human-readable (this summary) and machine-readable (JSON below) formats
- The JSON section below contains the complete, expanded set of rules and guidelines

**Critical Rules:**
- NO Vietnamese text in code, comments, or docstrings - All code must be in English
- ALL API documentation (@extend_schema) must be in English
- ALL API endpoints must include request and response examples using OpenApiExample
- ALL response examples must use envelope format: {success: true/false, data: ..., error: ...}
- ONLY user-facing strings must be wrapped in gettext() or gettext_lazy()
- DO NOT translate admin/developer-facing strings (verbose_name, help_text, Meta.verbose_name)
- ALWAYS use PhraseSearchFilter for ViewSets instead of SearchFilter
- ALWAYS use SafeTextField instead of model.TextField
- ALWAYS activate Python environment before running any Python command
- ALWAYS set ENVIRONMENT=test when running pytest

## JSON Prompting Section

```json
{
  "meta": {
    "version": "1.1.0",
    "last_updated": "2025-11-21",
    "project_type": "django_rest_api",
    "primary_language": "python",
    "framework": "django",
    "description": "Comprehensive coding guidelines for MVL ERP Backend Django application"
  },
  "json_schema": {
    "version": "draft-07",
    "description": "This JSON follows a structured schema defining all coding guidelines, architecture patterns, and enforcement rules for the project"
  },
  "preflight_checklist": {
    "title": "PRE-FLIGHT CHECKLIST - READ BEFORE EVERY TASK",
    "critical": true,
    "enforcement": "blocking",
    "items": [
      {
        "rule": "NO Vietnamese text in code, comments, or docstrings",
        "severity": "critical",
        "description": "All code must be in English. Use gettext() for user-facing strings."
      },
      {
        "rule": "ALL API documentation (@extend_schema) must be in English",
        "severity": "critical",
        "description": "API docs including summary, description, and tags must be in English"
      },
      {
        "rule": "ALL API endpoints must include request and response examples using OpenApiExample",
        "severity": "critical",
        "description": "Every API endpoint needs concrete examples for requests and responses"
      },
      {
        "rule": "ALL response examples must use envelope format: {success: true/false, data: ..., error: ...}",
        "severity": "critical",
        "description": "Standard response envelope is mandatory for all API responses"
      },
      {
        "rule": "ONLY user-facing strings must be wrapped in gettext() or gettext_lazy()",
        "severity": "critical",
        "description": "Use Django's i18n framework ONLY for end-user-visible text. DO NOT translate admin/developer-facing strings like verbose_name, help_text, or Meta.verbose_name."
      },
      {
        "rule": "Use constants for string values",
        "severity": "high",
        "description": "Define strings in constants.py or module-level constants to avoid hardcoding"
      },
      {
        "rule": "English strings ONLY - Vietnamese goes in .po translation files",
        "severity": "critical",
        "description": "Code contains English only; translations go in locale files"
      },
      {
        "rule": "Import translation functions: from django.utils.translation import gettext as _",
        "severity": "high",
        "description": "Always import translation utilities at the top of files"
      },
      {
        "rule": "Run pre-commit before committing: pre-commit run --all-files",
        "severity": "critical",
        "description": "Pre-commit hooks must pass before any commit"
      },
      {
        "rule": "Update translations: Run makemessages and add Vietnamese translations to .po files",
        "severity": "high",
        "description": "Keep translation files synchronized with code changes"
      },
      {
        "rule": "ALWAYS use PhraseSearchFilter for ViewSets instead of SearchFilter",
        "severity": "critical",
        "description": "Use PhraseSearchFilter from libs.drf.filtersets.search for whole-phrase searching in all ViewSets"
      },
      {
        "rule": "ALWAYS use SafeTextField instead of model.TextField",
        "severity": "critical",
        "description": "Use SafeTextField from libs.django.db.models for all text fields to prevent XSS attacks"
      }
    ],
    "rejection_message": "If you violate these rules, your code WILL be rejected."
  },
  "precommit_hooks": {
    "tools": ["ruff", "mypy", "custom_validators"],
    "custom_hooks": [
      {
        "name": "check-no-vietnamese",
        "purpose": "Prevents Vietnamese text in code, comments, and docstrings",
        "status": "BLOCKING",
        "script": "scripts/check_no_vietnamese.py",
        "allowed_locations": [".po translation files", "migrations (historical data)"]
      },
      {
        "name": "check-string-constants",
        "purpose": "Encourages using constants instead of hardcoded strings",
        "status": "WARNING_ONLY",
        "script": "scripts/check_string_constants.py",
        "flags": ["API documentation", "help text", "log messages without constants"],
        "allows": ["gettext() wrapped strings", "field names", "URLs", "short strings (≤3 chars)"]
      }
    ],
    "manual_commands": {
      "run_all": "pre-commit run --all-files",
      "run_vietnamese_check": "pre-commit run check-no-vietnamese --all-files",
      "run_constants_check": "pre-commit run check-string-constants --all-files",
      "test_scripts_directly": [
        "python scripts/check_no_vietnamese.py apps/core/models.py",
        "python scripts/check_string_constants.py apps/core/api/views.py"
      ]
    }
  },
  "i18n_requirements": {
    "framework": "django.utils.translation",
    "default_language": "vietnamese",
    "critical_rules": [
      {
        "rule": "ABSOLUTELY NO VIETNAMESE TEXT IN CODE",
        "description": "All code, comments, docstrings, and API docs MUST be in English"
      },
      {
        "rule": "ONLY translate user-facing strings - NOT admin/developer-facing strings",
        "description": "Translation is for end-user messages only, not for internal admin interfaces or API schema docs"
      }
    ],
    "strings_requiring_translation": {
      "description": "These strings MUST be wrapped with gettext() or gettext_lazy()",
      "examples": [
        "Validation error messages: raise ValidationError(_(\"Invalid email\"))",
        "API error responses: {\"detail\": _(\"User not found\")}",
        "TextChoices labels: choices=[(\"active\", _(\"Active\")), (\"inactive\", _(\"Inactive\"))]",
        "Business logic messages shown to end users: return {\"message\": _(\"Operation completed successfully\")}"
      ]
    },
    "strings_not_requiring_translation": {
      "description": "These strings should NOT be wrapped with gettext() - they are for admin/developer use only",
      "examples": [
        "Model field verbose_name: models.CharField(max_length=100, verbose_name=\"Username\")",
        "Model field help_text: models.CharField(max_length=100, help_text=\"Enter the user's username\")",
        "Serializer field help_text: serializers.CharField(help_text=\"Username for login\")",
        "Meta.verbose_name: class Meta: verbose_name = \"User\"",
        "Meta.verbose_name_plural: class Meta: verbose_name_plural = \"Users\""
      ],
      "rationale": "Admin interfaces and API schema documentation are for developers and administrators who work in English. Translating these creates unnecessary maintenance burden and confusion."
    },
    "process": [
      {
        "step": 1,
        "action": "Write in English ONLY",
        "example": "message = _(\"User not found\")"
      },
      {
        "step": 2,
        "action": "Import the translation function ONLY when needed for user-facing strings",
        "imports": [
          "from django.utils.translation import gettext as _  # For runtime user-facing messages",
          "from django.utils.translation import gettext_lazy as _  # For model TextChoices labels"
        ],
        "note": "Do NOT import translation functions if only defining models/serializers with verbose_name/help_text"
      },
      {
        "step": 3,
        "action": "Wrap ONLY user-facing strings",
        "examples": [
          "Error messages: raise ValidationError(_(\"Invalid email\"))",
          "API responses: {\"detail\": _(\"Success\")}",
          "Choice labels: choices=[(\"active\", _(\"Active\"))]"
        ],
        "anti_examples": [
          "DO NOT: verbose_name=_(\"User name\")  # Admin-facing, no translation needed",
          "DO NOT: help_text=_(\"Enter your email\")  # Schema docs, no translation needed"
        ]
      },
      {
        "step": 4,
        "action": "Update translation files",
        "commands": [
          "poetry run python manage.py makemessages -l vi --no-obsolete",
          "# Then edit locale/vi/LC_MESSAGES/django.po to add Vietnamese translations",
          "poetry run python manage.py compilemessages"
        ]
      }
    ]
  },
  "api_doc_requirements": {
    "library": "drf-spectacular",
    "language": "english",
    "mandatory_elements": ["summary", "tags", "examples"],
    "response_envelope": {
      "critical": true,
      "middleware": "ApiResponseWrapperMiddleware",
      "formats": {
        "success_single": "{\"success\": true, \"data\": {...}, \"error\": null}",
        "success_list_paginated": "{\"success\": true, \"data\": {\"count\": N, \"next\": \"...\", \"previous\": null, \"results\": [...]}, \"error\": null}",
        "success_list_no_pagination": "{\"success\": true, \"data\": [...], \"error\": null}",
        "error": "{\"success\": false, \"data\": null, \"error\": \"...\" or {...}}"
      },
      "requirements": [
        "Use envelope format: {success, data, error}",
        "Include success AND error examples",
        "List endpoints with pagination: Include count, next, previous, results in data",
        "All text in English only"
      ],
      "example": {
        "import": "from drf_spectacular.utils import extend_schema, OpenApiExample",
        "decorator": "@extend_schema(\n    summary=\"List all roles\",\n    tags=[\"Roles\"],\n    examples=[\n        OpenApiExample(\n            \"Success\",\n            value={\"success\": True, \"data\": {\"count\": 1, \"next\": None, \"previous\": None, \"results\": [{\"id\": 1, \"name\": \"Admin\"}]}},\n            response_only=True,\n        ),\n        OpenApiExample(\n            \"Error\",\n            value={\"success\": False, \"error\": {\"field\": [\"Error message\"]}},\n            response_only=True,\n            status_codes=[\"400\"],\n        ),\n    ],\n)"
      }
    }
  },
  "architecture_guidelines": {
    "project_type": "django_modular_apps",
    "apps": ["core", "hrm", "crm"],
    "app_selection": "Identify the correct app for new features. Propose new apps for large, distinct features.",
    "module_responsibility": {
      "models.py": "Django model definitions and their methods. Use custom QuerySet or Manager for table-related logic.",
      "queryset.py": "Custom QuerySet classes with table-level methods",
      "views.py": "API view logic for handling requests and responses. Keep views thin.",
      "serializers.py": "DRF serializers for data validation, serialization, and deserialization",
      "filters.py": "Custom FilterSet classes extending Django Filters FilterSet",
      "urls.py": "URL routing for the app",
      "permissions.py": "Custom permission classes for access control",
      "utils.py": "Reusable helper functions specific to the app",
      "constants.py": "Choices, enums, and other constant values to avoid hard-coding"
    },
    "modularity": {
      "rule": "If a module becomes too large, convert it into a package",
      "structure": "Directory with __init__.py importing important symbols, wrapped in __all__",
      "example": "models/user.py, models/profile.py"
    },
    "configuration": {
      "location": "settings/ directory",
      "modification_policy": "Do not modify without clear and approved reason"
    }
  },
  "coding_style_and_tools": {
    "linters": ["ruff"],
    "formatters": ["ruff"],
    "type_checkers": ["mypy"],
    "enforcement": "strict",
    "pre_commit_required": true,
    "optimization_approach": {
      "description": "Use incremental validation for faster iteration",
      "steps": [
        "Start with code reading and analysis (no dependencies needed)",
        "Use Python's built-in syntax checking (python -m py_compile)",
        "Run poetry run ruff check for targeted files when modifying code",
        "Run mypy only on files you're modifying",
        "Defer full pre-commit validation until final changes are ready"
      ]
    },
    "string_constants": {
      "rule": "Use constants for string values throughout the codebase, but avoid creating constants for simple API documentation strings",
      "apply_to": [
        "Serializer Help Text: Use constants for help_text values",
        "Log Messages: Define log messages as constants",
        "Error Messages: Use constants for internal error messages (user-facing strings use gettext())"
      ],
      "do_not_create_constants_for": [
        "API Documentation: @extend_schema summary and description should use inline strings, not constants",
        "OpenAPI examples: Use inline strings in OpenApiExample definitions"
      ],
      "exceptions": [
        "Very short strings (≤3 chars): \"id\", \"pk\", \"en\"",
        "Field names and model names: \"email\", \"username\"",
        "URLs and paths: \"/api/users\", \"https://example.com\"",
        "Format strings: f\"{user.name}\"",
        "Strings wrapped in gettext(): _(\"User not found\") (user-facing)"
      ]
    },
    "import_rules": {
      "critical": true,
      "rule": "ALL imports MUST be placed at the top of the file",
      "description": "Never import modules inside functions or methods. All imports must be at module level (top of file).",
      "enforcement": "blocking",
      "examples": {
        "correct": "# At top of file\nfrom apps.devices.zk import ZKDeviceService\n\nclass MyModel:\n    def my_method(self):\n        service = ZKDeviceService()",
        "wrong": "# NEVER do this\nclass MyModel:\n    def my_method(self):\n        from apps.devices.zk import ZKDeviceService  # WRONG!\n        service = ZKDeviceService()"
      },
      "rationale": [
        "Improves code readability and maintainability",
        "Makes dependencies explicit and visible",
        "Prevents import-related performance issues",
        "Follows PEP 8 style guidelines"
      ]
    },
    "general_principles": {
      "clarity": "Write clear, maintainable, and self-explanatory code",
      "dry": "Follow the DRY (Don't Repeat Yourself) principle"
    }
  },
  "testing_requirements": {
    "approach": "TDD (Test-Driven Development)",
    "pattern": "AAA (Arrange-Act-Assert)",
    "test_structure": {
      "arrange": "Set up test data and initial state using Django ORM objects",
      "act": "Execute the function or make the API call you are testing",
      "assert": "Verify the outcome is as expected"
    },
    "database_policy": "Do NOT mock the database unless explicit human instructions. Create real model instances via Django ORM.",
    "mocking_policy": {
      "critical": true,
      "rule": "ALWAYS mock external services, third-party APIs, and network connections in unit tests",
      "description": "Mock any usage or requests to external services unless explicitly told not to",
      "must_mock": [
        "Third-party API calls (payment gateways, email services, etc.)",
        "Network connections to external devices or services",
        "File system operations (reading/writing files)",
        "External database connections",
        "Time-dependent operations (use freezegun or similar)",
        "Random number generation when deterministic results are needed"
      ],
      "how_to_mock": {
        "unittest_mock": "Use unittest.mock.patch decorator to mock at the import location",
        "correct_patch_path": "Mock where the object is imported and used, not where it's defined. Example: @patch('apps.hrm.models.attendance_device.ZKDeviceService') when ZKDeviceService is imported at top of attendance_device.py",
        "context_managers": "For objects used as context managers, mock both __enter__ and __exit__ methods",
        "return_values": "Set appropriate return values: mock_instance.method.return_value = expected_value"
      },
      "examples": {
        "correct": "@patch('apps.hrm.models.attendance_device.ZKDeviceService')\ndef test_connection(self, mock_service):\n    mock_instance = MagicMock()\n    mock_instance.test_connection.return_value = (True, 'Connected')\n    mock_service.return_value = mock_instance",
        "wrong": "@patch('apps.devices.zk.ZKDeviceService')  # Wrong - should patch where imported, not where defined"
      }
    },
    "fixtures": {
      "usage": "Reuse test data by creating Pytest fixtures",
      "scope": "For widely used fixtures, define them in higher-level conftest.py"
    },
    "execution_strategy": {
      "performance_optimization": [
        "Start by understanding the existing test structure without running tests",
        "Run only specific test files related to changes (e.g., pytest apps/hrm/tests/test_models.py)",
        "Run full test suite only before final commit if making significant changes",
        "For documentation-only changes, skip running tests entirely"
      ]
    },
    "when_to_write_tests": "Write tests BEFORE implementing or modifying business logic. Tests may not be needed for documentation-only changes, bug fixes with existing tests, or minor refactors."
  },
  "forbidden_documents": {
    "critical": true,
    "description": "Do NOT create unnecessary documentation files",
    "forbidden_types": [
      "Task planning documents: TASK_PLAN.md, WORK_PLAN.md",
      "Work summaries: WORK_SUMMARY.md, TASK_SUMMARY.md",
      "Implementation summaries: *_IMPLEMENTATION_SUMMARY.md, *_SUMMARY.md",
      "Issue resolution docs: ISSUE_RESOLUTION_*.md, ISSUE_*.md",
      "Checklists: *_CHECKLIST.md, *_MIGRATION_CHECKLIST.md",
      "Quick reference cards: *_QUICK_REFERENCE.md, *_REFERENCE.md",
      "Compliance/instruction documents: INSTRUCTION_COMPLIANCE.md, COPILOT_VALIDATION.md",
      "Review documents: *_REVIEW.md, CODE_*_REVIEW.md",
      "Optimization summaries: *_OPTIMIZATION_SUMMARY.md, CI_OPTIMIZATION_*.md",
      "Comparison documents: *_COMPARISON.md, *_WORKFLOW_COMPARISON.md"
    ],
    "rationale": [
      "PR descriptions already contain task information",
      "Commit messages already explain what was done and why",
      "These docs become outdated and misleading",
      "They waste time and clutter the repository",
      "They provide no value to end users or future developers"
    ],
    "allowed_documentation": [
      "Adding a new feature that requires user-facing documentation",
      "Documenting API endpoints (with examples) for integration",
      "Updating existing documentation (README, API docs)",
      "Creating technical design documents explicitly requested by the team lead",
      "Adding architecture diagrams for significant changes (Mermaid format)",
      "Documenting business logic and workflows that are complex and need explanation"
    ],
    "validation_questions": [
      "Does this document business logic or workflows?",
      "Will this help users/developers integrate with the system?",
      "Was this explicitly requested by the team lead?"
    ],
    "message": "If all answers are NO, DO NOT create the file. Excessive documentation is WASTE."
  },
  "version_control": {
    "branching": {
      "policy": "All work on feature or fix branch from master. Never commit directly to master.",
      "naming_convention": {
        "rules": [
          "Use related issue's title as basis for branch name",
          "Convert to lowercase",
          "Strip special characters (keep alphanumeric and hyphens)",
          "Remove leading/trailing spaces",
          "Replace spaces with hyphens",
          "Keep concise (ideally under 50 characters)"
        ],
        "example": "Issue: 'Update Copilot Instructions' → Branch: 'update-copilot-instructions'"
      }
    },
    "commit_messages": {
      "specification": "Conventional Commits",
      "format": "type(scope): short description",
      "example": "feat(hrm): add employee performance review model",
      "body_requirement": "Explain WHY the change was made, not just WHAT was changed"
    }
  },
  "security_and_secrets": {
    "secrets_policy": "NEVER hard-code sensitive information (API keys, passwords, secret keys). Always use environment variables.",
    "input_validation": "Always validate and sanitize all user-provided input, especially from API requests, using DRF serializers.",
    "database_queries": "Use Django ORM exclusively. Avoid raw SQL queries to prevent SQL injection vulnerabilities."
  },
  "dependencies_policy": {
    "rule": "Do NOT add any new third-party libraries or packages without prior discussion and approval from team lead"
  },
  "performance_and_ci_guidelines": {
    "optimization_goal": "Fast iteration and minimize startup time",
    "initial_assessment": {
      "description": "Perform lightweight exploration first - no dependencies required",
      "actions": [
        "Read and understand relevant files using the view tool",
        "Analyze code structure and identify files to modify",
        "Review existing tests to understand coverage",
        "Check git history if needed for context"
      ]
    },
    "when_to_install_dependencies": [
      "You need to run tests",
      "You need to execute Django management commands",
      "You need to run the actual application code",
      "You're validating database migrations"
    ],
    "when_to_run_validation": {
      "documentation_changes": "No validation needed, just ensure markdown/text is correct",
      "configuration_changes": "Quick syntax check with ruff check (no deps needed)",
      "code_changes": "Run targeted tests for affected modules only",
      "before_final_commit": "Run full linting (pre-commit run --all-files) and relevant test suite"
    },
    "optimization_strategies": [
      "Defer Dependency Installation: Analyze and plan changes first, install only when necessary",
      "Use Targeted Testing: Run pytest path/to/specific/test.py instead of full suite",
      "Use Incremental Validation: Start with basic syntax checks, then progress to linting and testing",
      "Skip Unnecessary Steps: Don't run Django checks for documentation changes",
      "Leverage CI/CD: Trust that the CI/CD pipeline will catch issues; focus on your specific changes",
      "Batch Operations: When multiple files need checking, do it in a single command rather than one-by-one"
    ],
    "quick_reference_commands": {
      "lightweight_syntax_validation": "python -m py_compile apps/core/models.py  # Basic syntax check",
      "fast_linting": [
        "poetry run ruff check apps/ libs/ settings/",
        "poetry run ruff format --check apps/ libs/ settings/"
      ],
      "run_specific_test": "poetry run pytest apps/core/tests/test_models.py -v",
      "run_app_tests": "poetry run pytest apps/hrm/ -v",
      "type_check": "poetry run mypy apps/hrm/models.py"
    }
  },
  "vscode_environment_setup": {
    "python_environment_activation": {
      "critical": true,
      "rule": "ALWAYS activate Python environment before running any Python command",
      "description": "Never run Python commands without activating the virtual environment first",
      "default_directories": ["venv", ".venv"],
      "fallback_action": "If default directories not found, check VS Code Python interpreter configuration or ask user",
      "examples": {
        "activate_venv": "source venv/bin/activate  # Linux/Mac",
        "activate_conda": "conda activate myenv  # If using conda",
        "check_interpreter": "Check VS Code settings for python.pythonPath or python.defaultInterpreterPath"
      }
    },
    "pytest_environment_variable": {
      "critical": true,
      "rule": "ALWAYS set ENVIRONMENT=test when running pytest",
      "description": "Set the ENVIRONMENT environment variable to 'test' for all pytest executions",
      "examples": {
        "correct": "ENVIRONMENT=test pytest apps/core/tests/",
        "with_activation": "source venv/bin/activate && ENVIRONMENT=test pytest apps/core/tests/"
      }
    }
  },
  "enforcement": {
    "level": "strict",
    "violations_consequence": "Code will be rejected",
    "common_violations": [
      {
        "violation": "Vietnamese text in code",
        "correct": "Use English + gettext(): _(\"Invalid email\")",
        "wrong": "\"Email không hợp lệ\""
      },
      {
        "violation": "Vietnamese in API docs",
        "correct": "@extend_schema(summary=\"List roles\")",
        "wrong": "summary=\"Danh sách vai trò\""
      },
      {
        "violation": "Missing envelope",
        "correct": "Always use {\"success\": true/false, \"data\": ..., \"error\": ...} in response examples"
      },
      {
        "violation": "Missing pagination",
        "correct": "List endpoints: {\"success\": true, \"data\": {\"count\": N, \"results\": [...]}}",
        "wrong": "Direct array"
      },
      {
        "violation": "Forgot translations",
        "reminder": "After adding _() strings, run: poetry run python manage.py makemessages -l vi --no-obsolete"
      }
    ],
    "before_committing": "Run pre-commit run --all-files"
  },
  "generation_params": {
    "temperature": 0.1,
    "reasoning": "Low temperature for consistent, rule-following code generation"
  },
  "safety": {
    "content_filtering": true,
    "pii_detection": true,
    "code_injection_prevention": true
  },
  "examples": {
    "i18n_correct": {
      "python": "from django.utils.translation import gettext as _\n\n# Correct: Translate user-facing error messages\nerror_message = _(\"Invalid email address\")\n\n# Correct: API docs in English (no translation needed)\n@extend_schema(summary=\"List all roles\", tags=[\"Roles\"])\n\n# Correct: Admin-facing verbose_name without translation\nclass Role(models.Model):\n    name = models.CharField(max_length=100, verbose_name=\"Role name\")\n    \n    class Meta:\n        verbose_name = \"Role\"\n        verbose_name_plural = \"Roles\"\n\n# Correct: Translate TextChoices labels (user-facing)\nclass Status(models.TextChoices):\n    ACTIVE = \"active\", _(\"Active\")\n    INACTIVE = \"inactive\", _(\"Inactive\")"
    },
    "i18n_wrong": {
      "python": "# Wrong: Vietnamese text in code\nerror_message = \"Địa chỉ email không hợp lệ\"\n\n# Wrong: Vietnamese in API docs\n@extend_schema(summary=\"Danh sách vai trò\")\n\n# Wrong: Translating admin-facing verbose_name (unnecessary)\nclass Role(models.Model):\n    name = models.CharField(max_length=100, verbose_name=_(\"Role name\"))  # Don't do this!\n    \n    class Meta:\n        verbose_name = _(\"Role\")  # Don't do this!\n        verbose_name_plural = _(\"Roles\")  # Don't do this!"
    },
    "constants_correct": {
      "constants_py": "ERROR_USER_NOT_FOUND = \"User not found\"\nHELP_TEXT_EMAIL = \"User's email address\"",
      "views_py": "@extend_schema(\n    summary=\"List all users\",\n    description=\"Retrieve a paginated list of all users in the system\",\n    tags=[\"Users\"],\n)\ndef list_users(request):\n    pass",
      "serializers_py": "from .constants import HELP_TEXT_EMAIL\n\nclass UserSerializer(serializers.ModelSerializer):\n    email = serializers.EmailField(help_text=HELP_TEXT_EMAIL)"
    },
    "constants_wrong": {
      "python": "# Don't create constants for API documentation\nAPI_USER_LIST_SUMMARY = \"List all users\"  # WRONG - unnecessary constant\nAPI_USER_LIST_DESCRIPTION = \"Retrieve a list...\"  # WRONG - unnecessary constant"
    },
    "import_correct": {
      "python": "# All imports at top of file\nfrom apps.devices.zk import ZKDeviceService\nfrom apps.hrm.models import AttendanceDevice\n\nclass MyClass:\n    def my_method(self):\n        service = ZKDeviceService()"
    },
    "import_wrong": {
      "python": "# NEVER import inside methods\nclass MyClass:\n    def my_method(self):\n        from apps.devices.zk import ZKDeviceService  # WRONG!\n        service = ZKDeviceService()"
    },
    "api_response_envelope": {
      "python": "from drf_spectacular.utils import extend_schema, OpenApiExample\n\n@extend_schema(\n    summary=\"List all roles\",\n    tags=[\"Roles\"],\n    examples=[\n        OpenApiExample(\n            \"Success\",\n            value={\"success\": True, \"data\": {\"count\": 1, \"next\": None, \"previous\": None, \"results\": [{\"id\": 1, \"name\": \"Admin\"}]}},\n            response_only=True,\n        ),\n        OpenApiExample(\n            \"Error\",\n            value={\"success\": False, \"error\": {\"field\": [\"Error message\"]}},\n            response_only=True,\n            status_codes=[\"400\"],\n        ),\n    ],\n)"
    }
  }
}
```
