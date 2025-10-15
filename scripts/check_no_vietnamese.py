#!/usr/bin/env python3
"""Pre-commit hook to check for Vietnamese characters in Python code.

This script ensures that no Vietnamese text is present in:
- Python source code (.py files)
- Comments
- Docstrings
- String literals (except in translation .po files)

Vietnamese is only allowed in:
- Translation files (*.po)
- Test fixtures/data
- Migration files (historical data)
- OpenApiExample value data (for realistic API documentation)
"""

import ast
import re
import sys

# Vietnamese character ranges (Unicode)
VIETNAMESE_PATTERN = re.compile(
    r"["
    r"\u00C0-\u00C3\u00C8-\u00CA\u00CC\u00CD\u00D2-\u00D5\u00D9\u00DA\u00DD"
    r"\u00E0-\u00E3\u00E8-\u00EA\u00EC\u00ED\u00F2-\u00F5\u00F9\u00FA\u00FD"
    r"\u0102\u0103\u0110\u0111\u0128\u0129\u0168\u0169\u01A0\u01A1\u01AF\u01B0"
    r"\u1EA0-\u1EF9"
    r"]"
)

# Files/directories to skip
SKIP_PATTERNS = [
    "locale/",  # Translation files
    "migrations/",  # Historical data in migrations
    ".po",  # Translation files
    ".mo",  # Compiled translation files
    "test_fixtures",  # Test data
    "tests/",  # test files
]


def should_check_file(filepath: str) -> bool:
    """Determine if a file should be checked for Vietnamese text."""
    for pattern in SKIP_PATTERNS:
        if pattern in filepath:
            return False
    return filepath.endswith(".py")


class VietnameseTextVisitor(ast.NodeVisitor):
    """AST visitor to find Vietnamese text in code, comments, and docstrings.
    
    This visitor skips Vietnamese text inside OpenApiExample value parameters,
    as those are realistic API documentation examples.
    """

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.violations: list[tuple[int, str]] = []
        self.in_openapi_example = False
        self.openapi_example_depth = 0

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to detect OpenApiExample usage."""
        # Check if this is an OpenApiExample call
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # Track if we're entering an OpenApiExample call
        was_in_example = self.in_openapi_example
        if func_name == "OpenApiExample":
            self.in_openapi_example = True
            self.openapi_example_depth += 1

        self.generic_visit(node)

        # Restore state when leaving OpenApiExample
        if func_name == "OpenApiExample":
            self.openapi_example_depth -= 1
            if self.openapi_example_depth == 0:
                self.in_openapi_example = False

    def visit_Constant(self, node: ast.Constant) -> None:
        """Visit constant nodes (string literals)."""
        value = getattr(node, "value", None)
        if not isinstance(value, str):
            self.generic_visit(node)
            return

        # Skip if we're inside an OpenApiExample call
        if self.in_openapi_example:
            self.generic_visit(node)
            return

        # Check if this string contains Vietnamese
        if VIETNAMESE_PATTERN.search(value):
            lineno = getattr(node, "lineno", 0)
            if 0 < lineno <= len(self.source_lines):
                line_content = self.source_lines[lineno - 1].strip()
                self.violations.append((lineno, line_content))

        self.generic_visit(node)

    # For Python < 3.8 compatibility
    def visit_Str(self, node) -> None:
        """Visit string nodes (for older Python AST)."""
        if hasattr(node, "lineno") and hasattr(node, "s"):
            # Create a Constant node and visit it
            const_node = ast.Constant(value=node.s)
            const_node.lineno = node.lineno
            self.visit_Constant(const_node)


def check_file_for_vietnamese(filepath: str) -> tuple[bool, list[tuple[int, str]]]:
    """Check a single file for Vietnamese characters.

    Returns:
        tuple: (has_vietnamese, list of (line_number, line_content))
    """
    violations = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
            source_lines = source.splitlines()

        # Parse the file and check for Vietnamese in strings
        try:
            tree = ast.parse(source, filename=filepath)
            visitor = VietnameseTextVisitor(source_lines)
            visitor.visit(tree)
            violations.extend(visitor.violations)
        except SyntaxError:
            # If AST parsing fails, fall back to line-by-line checking
            # (but this shouldn't happen for valid Python files)
            for line_num, line in enumerate(source_lines, start=1):
                if VIETNAMESE_PATTERN.search(line):
                    violations.append((line_num, line.strip()))

        # Also check comments (which AST doesn't capture)
        for line_num, line in enumerate(source_lines, start=1):
            # Check if line has a comment
            if "#" in line:
                comment_part = line[line.index("#"):]
                if VIETNAMESE_PATTERN.search(comment_part):
                    # Check if this violation is already recorded
                    if not any(v[0] == line_num for v in violations):
                        violations.append((line_num, line.strip()))

    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return False, []

    return len(violations) > 0, violations


def main() -> int:
    """Main function to check all files passed as arguments."""
    if len(sys.argv) < 2:
        print("Usage: check_no_vietnamese.py <file1> <file2> ...")
        return 0

    files_to_check = [f for f in sys.argv[1:] if should_check_file(f)]

    if not files_to_check:
        return 0

    has_violations = False

    for filepath in files_to_check:
        has_viet, violations = check_file_for_vietnamese(filepath)

        if has_viet:
            has_violations = True
            print(f"\n❌ Vietnamese text found in: {filepath}")
            for line_num, line_content in violations:
                print(f"   Line {line_num}: {line_content}")

    if has_violations:
        print("\n" + "=" * 70)
        print("❌ FAILED: Vietnamese text detected in code!")
        print("=" * 70)
        print("\n📋 Copilot Instructions violation:")
        print("   - NO Vietnamese text in code, comments, or docstrings")
        print("   - Use English ONLY for all code")
        print("   - User-facing strings: use gettext() with English, translate in .po files")
        print("\n💡 To fix:")
        print("   1. Replace Vietnamese text with English")
        print("   2. For user-facing strings, wrap in gettext():")
        print("      from django.utils.translation import gettext as _")
        print('      message = _("Your English message here")')
        print("   3. Update translations: python manage.py makemessages -l vi")
        print("   4. Add Vietnamese translation in locale/vi/LC_MESSAGES/django.po")
        print()
        return 1

    print("✅ No Vietnamese text found in code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
