# Copilot Instructions for This Repository

## Human Summary

This file contains comprehensive coding guidelines and instructions for GitHub Copilot when working on this Django ERP backend project.

**Important Notes:**
- **The JSON prompt MUST be embedded within this `.md` file** - do not create separate `.json` files
- **GitHub Copilot only reads guidance from this file** and will not automatically consume external JSON files
- All instructions are provided in both human-readable (this summary) and machine-readable (JSON below) formats
- The JSON section below contains the complete, expanded set of rules and guidelines

## JSON Prompting Section

```json
{
  "meta": {
    "version": "1.0.0",
    "last_updated": "2025-11-01",
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
        "rule": "ALL user-facing strings must be wrapped in gettext() or gettext_lazy()",
        "severity": "critical",
        "description": "Use Django's i18n framework for all user-visible text"
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
      }
    ],
    "process": [
      {
        "step": 1,
        "action": "Write in English ONLY",
        "example": "message = _(\"User not found\")"
      },
      {
        "step": 2,
        "action": "Import the translation function",
        "imports": [
          "from django.utils.translation import gettext as _  # For runtime",
          "from django.utils.translation import gettext_lazy as _  # For models/class-level"
        ]
      },
      {
        "step": 3,
        "action": "Wrap ALL user-facing strings",
        "examples": [
          "Error messages: raise ValidationError(_(\"Invalid email\"))",
          "Model fields: verbose_name=_(\"User name\")",
          "API responses: {\"detail\": _(\"Success\")}",
          "Help text: help_text=_(\"Enter your email\")",
          "Choice labels: choices=[(\"active\", _(\"Active\"))]"
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
      "rule": "Use constants for string values throughout the codebase",
      "apply_to": [
        "API Documentation: Define summary, description, and tags as constants",
        "Serializer Help Text: Use constants for help_text values",
        "Log Messages: Define log messages as constants",
        "Error Messages: Use constants for internal error messages (user-facing strings use gettext())"
      ],
      "exceptions": [
        "Very short strings (≤3 chars): \"id\", \"pk\", \"en\"",
        "Field names and model names: \"email\", \"username\"",
        "URLs and paths: \"/api/users\", \"https://example.com\"",
        "Format strings: f\"{user.name}\"",
        "Strings wrapped in gettext(): _(\"User not found\") (user-facing)"
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
      "python": "from django.utils.translation import gettext as _\n\nerror_message = _(\"Invalid email address\")\n@extend_schema(summary=\"List all roles\", tags=[\"Roles\"])\nclass Role(models.Model):\n    name = models.CharField(verbose_name=_(\"Role name\"))"
    },
    "i18n_wrong": {
      "python": "error_message = \"Địa chỉ email không hợp lệ\"\n@extend_schema(summary=\"Danh sách vai trò\")"
    },
    "constants_correct": {
      "constants_py": "API_USER_LIST_SUMMARY = \"List all users\"\nAPI_USER_LIST_DESCRIPTION = \"Retrieve a paginated list of all users in the system\"\nERROR_USER_NOT_FOUND = \"User not found\"\nHELP_TEXT_EMAIL = \"User's email address\"",
      "views_py": "from .constants import API_USER_LIST_SUMMARY, API_USER_LIST_DESCRIPTION\n\n@extend_schema(\n    summary=API_USER_LIST_SUMMARY,\n    description=API_USER_LIST_DESCRIPTION,\n    tags=[\"Users\"],\n)\ndef list_users(request):\n    pass",
      "serializers_py": "from .constants import HELP_TEXT_EMAIL\n\nclass UserSerializer(serializers.ModelSerializer):\n    email = serializers.EmailField(help_text=HELP_TEXT_EMAIL)"
    },
    "constants_wrong": {
      "python": "@extend_schema(\n    summary=\"List all users\",  # Should be a constant\n    description=\"Retrieve a paginated list of all users\",  # Should be a constant\n    tags=[\"Users\"],\n)"
    },
    "api_response_envelope": {
      "python": "from drf_spectacular.utils import extend_schema, OpenApiExample\n\n@extend_schema(\n    summary=\"List all roles\",\n    tags=[\"Roles\"],\n    examples=[\n        OpenApiExample(\n            \"Success\",\n            value={\"success\": True, \"data\": {\"count\": 1, \"next\": None, \"previous\": None, \"results\": [{\"id\": 1, \"name\": \"Admin\"}]}},\n            response_only=True,\n        ),\n        OpenApiExample(\n            \"Error\",\n            value={\"success\": False, \"error\": {\"field\": [\"Error message\"]}},\n            response_only=True,\n            status_codes=[\"400\"],\n        ),\n    ],\n)"
    }
  }
}
```


