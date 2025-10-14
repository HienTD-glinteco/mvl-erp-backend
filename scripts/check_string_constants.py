#!/usr/bin/env python3
"""Pre-commit hook to check for hardcoded strings in Python code.

This script encourages the use of constants for string values, particularly:
- Log messages
- Error messages (non-user-facing, reusable)
- Configuration values

Allowed string patterns (not flagged):
- gettext() wrapped strings (user-facing, already handled by i18n)
- API documentation strings (extend_schema summary, description, tags) - mostly one-time use
- Serializer help_text (mostly one-time use)
- Field names, model names (Django internals)
- URLs, file paths
- Test strings
- Single-word or very short strings (< 4 chars)
- Format strings used with variables
"""

import ast
import re
import sys

# Patterns to ALLOW (won't be flagged as violations)
ALLOWED_PATTERNS = [
    # Translation functions
    r"_\(",  # gettext
    r"gettext\(",
    r"gettext_lazy\(",
    r"ngettext\(",
    r"npgettext\(",
    r"pgettext\(",
    # Django model/field internals
    r"verbose_name=_\(",
    r"help_text=_\(",
    # Very short strings (likely constants, field names, etc.)
    # We'll check length in the AST analysis
]

# Files/directories to skip
SKIP_PATTERNS = [
    "migrations/",  # Migration files
    "test_",  # Test files (more lenient)
    "tests/",  # Test directories
    "conftest.py",  # Test configuration
    "settings/",  # Settings files
    "manage.py",  # Django management
]


def should_check_file(filepath: str) -> bool:
    """Determine if a file should be checked."""
    for pattern in SKIP_PATTERNS:
        if pattern in filepath:
            return False
    return filepath.endswith(".py")


def is_allowed_string(value: str, context: str = "") -> bool:
    """Check if a string literal is allowed (should not be flagged).

    Args:
        value: The string literal value
        context: Additional context about where the string is used

    Returns:
        True if the string is allowed, False if it should be a constant
    """
    # Allow very short strings (likely field names, keys, etc.)
    if len(value) <= 3:
        return True

    # Allow empty strings
    if not value.strip():
        return True

    # Allow single words (likely field names or keys)
    if " " not in value and len(value) < 20:
        return True

    # Allow strings that look like field names (snake_case, lowercase)
    if re.match(r"^[a-z_][a-z0-9_]*$", value):
        return True

    # Allow URLs
    if value.startswith(("http://", "https://", "/")):
        return True

    # Allow file extensions and paths
    if value.startswith(".") or "/" in value:
        return True

    # Allow format string placeholders
    if re.search(r"\{[^}]*\}", value) or "%" in value:
        return True

    # Allow strings with only special characters or numbers
    if re.match(r"^[^a-zA-Z]*$", value):
        return True

    return False


class StringLiteralVisitor(ast.NodeVisitor):
    """AST visitor to find string literals that should be constants."""

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: list[tuple[int, str, str]] = []
        self.in_gettext = False
        self.in_api_doc = False

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to detect gettext usage and API doc calls."""
        # Check if this is a gettext or API doc call
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # Track if we're in a gettext call
        was_in_gettext = self.in_gettext
        if func_name in ("_", "gettext", "gettext_lazy", "ngettext", "pgettext"):
            self.in_gettext = True

        # Track if we're in an API documentation call (extend_schema, OpenApiParameter, etc.)
        was_in_api_doc = self.in_api_doc
        if func_name in ("extend_schema", "extend_schema_view", "OpenApiParameter", "OpenApiResponse", "OpenApiExample"):
            self.in_api_doc = True

        self.generic_visit(node)
        self.in_gettext = was_in_gettext
        self.in_api_doc = was_in_api_doc

    def visit_Constant(self, node: ast.Constant) -> None:
        """Visit constant nodes (string literals)."""
        # Get the value from the node
        value = getattr(node, "value", None)
        if not isinstance(value, str):
            self.generic_visit(node)
            return

        # Skip if we're inside a gettext call
        if self.in_gettext:
            self.generic_visit(node)
            return

        # Skip if we're inside an API documentation call
        if self.in_api_doc:
            self.generic_visit(node)
            return

        # Skip allowed strings
        if is_allowed_string(value):
            self.generic_visit(node)
            return

        # This is a potential violation
        lineno = getattr(node, "lineno", 0)
        self.violations.append((lineno, value, self.filename))

        self.generic_visit(node)

    # For Python < 3.8 compatibility
    def visit_Str(self, node) -> None:
        """Visit string nodes (for older Python AST)."""
        if hasattr(node, "lineno") and hasattr(node, "s"):
            # Create a Constant node and visit it
            const_node = ast.Constant(value=node.s)
            const_node.lineno = node.lineno
            self.visit_Constant(const_node)


def check_file_for_hardcoded_strings(filepath: str) -> tuple[bool, list[tuple[int, str]]]:
    """Check a single file for hardcoded strings.

    Returns:
        tuple: (has_violations, list of (line_number, string_value))
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=filepath)
        visitor = StringLiteralVisitor(filepath)
        visitor.visit(tree)

        violations = [(line, string) for line, string, _ in visitor.violations]
        return len(violations) > 0, violations

    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        return False, []
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}", file=sys.stderr)
        return False, []


def main() -> int:
    """Main function to check all files passed as arguments."""
    if len(sys.argv) < 2:
        print("Usage: check_string_constants.py <file1> <file2> ...")
        return 0

    files_to_check = [f for f in sys.argv[1:] if should_check_file(f)]

    if not files_to_check:
        return 0

    has_violations = False
    total_violations = 0

    for filepath in files_to_check:
        has_viol, violations = check_file_for_hardcoded_strings(filepath)

        if has_viol:
            has_violations = True
            total_violations += len(violations)
            print(f"\n⚠️  Hardcoded strings found in: {filepath}")
            for line_num, string_value in violations[:5]:  # Show first 5
                preview = string_value[:60] + "..." if len(string_value) > 60 else string_value
                print(f'   Line {line_num}: "{preview}"')
            if len(violations) > 5:
                print(f"   ... and {len(violations) - 5} more")

    if has_violations:
        print("\n" + "=" * 70)
        print(f"⚠️  WARNING: {total_violations} hardcoded string(s) detected!")
        print("=" * 70)
        print("\n📋 Best Practice:")
        print("   - Define string constants in constants.py or at module level")
        print("   - For user-facing strings, use gettext() for i18n")
        print("   - For API docs, create constant dictionaries")
        print("\n💡 Example:")
        print("   # constants.py")
        print('   ERROR_MESSAGE = "An error occurred"')
        print('   API_SUMMARY = "List all users"')
        print("\n   # your_file.py")
        print("   from .constants import ERROR_MESSAGE, API_SUMMARY")
        print()
        print("ℹ️  Note: This is a WARNING, not a hard failure.")
        print("   Consider refactoring to use constants for maintainability.")
        print()
        # Return 0 (success) to not block commits, but inform developers
        return 0

    print("✅ No hardcoded strings found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
