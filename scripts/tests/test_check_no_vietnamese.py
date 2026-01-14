#!/usr/bin/env python3
"""Tests for check_no_vietnamese.py script.

This test file documents the expected behavior of the Vietnamese text checker.
It ensures that Vietnamese text in OpenApiExample value data is allowed
(for realistic API documentation), while Vietnamese text elsewhere is caught.
"""

import subprocess
import tempfile
from pathlib import Path


def run_check_script(file_content: str) -> tuple[int, str]:
    """Helper to run check_no_vietnamese.py on a temporary file.

    Returns:
        tuple: (exit_code, output)
    """
    # From scripts/tests/, go up 2 levels to backend/, then to scripts/
    script_path = Path(__file__).parent.parent.parent / "scripts" / "check_no_vietnamese.py"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(file_content)
        temp_file = f.name

    try:
        result = subprocess.run(
            ["python3", str(script_path), temp_file],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout + result.stderr
    finally:
        Path(temp_file).unlink()


def test_vietnamese_in_openapi_example_is_allowed():
    """Vietnamese text inside OpenApiExample value should be allowed."""
    code = """
from drf_spectacular.utils import OpenApiExample, extend_schema

@extend_schema(
    summary="Test endpoint",
    examples=[
        OpenApiExample(
            "Example",
            value={
                "name": "Quận Ba Đình",
                "province": "Thành phố Hà Nội",
            },
            response_only=True,
        )
    ],
)
def test_view():
    pass
"""
    exit_code, output = run_check_script(code)
    assert exit_code == 0, f"Expected success but got: {output}"
    assert "No Vietnamese text found" in output


def test_vietnamese_in_variable_is_caught():
    """Vietnamese text in regular variables should be caught."""
    code = """
message = "Đây là thông báo tiếng Việt"
"""
    exit_code, output = run_check_script(code)
    assert exit_code == 1, f"Expected failure but got: {output}"
    assert "Vietnamese text found" in output


def test_vietnamese_in_comment_is_caught():
    """Vietnamese text in comments should be caught."""
    code = """
# Đây là comment tiếng Việt
def test_function():
    pass
"""
    exit_code, output = run_check_script(code)
    assert exit_code == 1, f"Expected failure but got: {output}"
    assert "Vietnamese text found" in output


def test_nested_openapi_example_with_vietnamese():
    """Nested Vietnamese data in OpenApiExample should be allowed."""
    code = """
from drf_spectacular.utils import OpenApiExample, extend_schema_view

@extend_schema_view(
    list=extend_schema(
        examples=[
            OpenApiExample(
                "Example",
                value={
                    "data": [
                        {
                            "name": "Quận Ba Đình",
                            "details": {
                                "province": "Thành phố Hà Nội",
                                "description": "Trung tâm lịch sử",
                            }
                        }
                    ]
                },
            )
        ],
    ),
)
class TestView:
    pass
"""
    exit_code, output = run_check_script(code)
    assert exit_code == 0, f"Expected success but got: {output}"


def test_vietnamese_outside_openapi_example_is_caught():
    """Vietnamese outside OpenApiExample should still be caught."""
    code = """
from drf_spectacular.utils import OpenApiExample, extend_schema

# This Vietnamese is in OpenApiExample - should be allowed
@extend_schema(
    examples=[
        OpenApiExample(
            "Example",
            value={"name": "Quận Ba Đình"},
        )
    ],
)
def test_view():
    pass

# This Vietnamese is NOT in OpenApiExample - should be caught
error_message = "Lỗi xảy ra"
"""
    exit_code, output = run_check_script(code)
    assert exit_code == 1, f"Expected failure but got: {output}"
    assert "Vietnamese text found" in output
    assert "error_message" in output.lower() or "Lỗi" in output


if __name__ == "__main__":
    # Run tests
    test_functions = [
        test_vietnamese_in_openapi_example_is_allowed,
        test_vietnamese_in_variable_is_caught,
        test_vietnamese_in_comment_is_caught,
        test_nested_openapi_example_with_vietnamese,
        test_vietnamese_outside_openapi_example_is_caught,
    ]

    print("Running tests for check_no_vietnamese.py...")
    for test_func in test_functions:
        try:
            test_func()
            print(f"✅ {test_func.__name__}")
        except AssertionError as e:
            print(f"❌ {test_func.__name__}: {e}")

    print("\nAll tests completed!")
