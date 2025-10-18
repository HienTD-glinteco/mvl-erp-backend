"""
Tests to verify OpenApiExample definitions are correct.

This test verifies that all OpenApiExample definitions follow the
correct envelope format: {success: true/false, data: ..., error: ...}
"""

import ast
import unittest
from pathlib import Path


class OpenApiExampleTest(unittest.TestCase):
    """Test that OpenApiExample values follow the correct envelope format"""

    def _extract_openapi_examples_from_file(self, filepath):  # noqa: C901
        """Extract OpenApiExample value definitions from a Python file"""
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())

        examples = []

        # Walk through AST to find OpenApiExample calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is an OpenApiExample call
                if isinstance(node.func, ast.Name) and node.func.id == "OpenApiExample":
                    # Check if this is a response example (not request_only=True)
                    is_response = True
                    for keyword in node.keywords:
                        if keyword.arg == "request_only":
                            if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                                is_response = False
                                break

                    # Only process response examples
                    if is_response:
                        # Find the 'value' keyword argument
                        for keyword in node.keywords:
                            if keyword.arg == "value":
                                # Extract the value (should be a dict literal)
                                if isinstance(keyword.value, ast.Dict):
                                    # Convert AST dict to Python dict (simplified)
                                    example_value = ast.literal_eval(keyword.value)
                                    examples.append(example_value)
                                elif isinstance(keyword.value, ast.Constant) and keyword.value.value is None:
                                    # Handle None value (e.g., for 204 responses)
                                    examples.append(None)

        return examples

    def _check_envelope_format(self, example_value):
        """Check if a value follows the envelope format"""
        # None is valid (for 204 No Content responses)
        if example_value is None:
            return True, None

        if not isinstance(example_value, dict):
            return False, "Example value must be a dictionary"

        # Check for success field
        if "success" not in example_value:
            return False, "Missing 'success' field in envelope"

        # Check for data or error field
        has_data = "data" in example_value
        has_error = "error" in example_value

        if not (has_data or has_error):
            return False, "Must have either 'data' or 'error' field"

        # If success=True, data should be present
        if example_value.get("success") is True:
            if not has_data:
                return False, "Success response must have 'data' field"

        # If success=False, error should be present
        if example_value.get("success") is False:
            if not has_error:
                return False, "Error response must have 'error' field"

        return True, None

    def test_permission_viewset_examples(self):
        """Test that PermissionViewSet has correct envelope format in examples"""
        filepath = Path(__file__).parent.parent.parent.parent / "apps" / "core" / "api" / "views" / "permission.py"
        examples = self._extract_openapi_examples_from_file(filepath)

        self.assertGreater(len(examples), 0, "PermissionViewSet should have OpenApiExample definitions")

        for i, example in enumerate(examples):
            is_valid, error_msg = self._check_envelope_format(example)
            self.assertTrue(is_valid, f"Example {i} in PermissionViewSet is invalid: {error_msg}")

    def test_recruitment_channel_viewset_examples(self):
        """Test that RecruitmentChannelViewSet has correct envelope format in examples"""
        filepath = (
            Path(__file__).parent.parent.parent.parent / "apps" / "hrm" / "api" / "views" / "recruitment_channel.py"
        )
        examples = self._extract_openapi_examples_from_file(filepath)

        self.assertGreater(len(examples), 0, "RecruitmentChannelViewSet should have OpenApiExample definitions")

        for i, example in enumerate(examples):
            is_valid, error_msg = self._check_envelope_format(example)
            self.assertTrue(is_valid, f"Example {i} in RecruitmentChannelViewSet is invalid: {error_msg}")

    def test_employee_viewset_examples(self):
        """Test that EmployeeViewSet has correct envelope format in examples"""
        filepath = Path(__file__).parent.parent.parent.parent / "apps" / "hrm" / "api" / "views" / "employee.py"
        examples = self._extract_openapi_examples_from_file(filepath)

        self.assertGreater(len(examples), 0, "EmployeeViewSet should have OpenApiExample definitions")

        for i, example in enumerate(examples):
            is_valid, error_msg = self._check_envelope_format(example)
            self.assertTrue(is_valid, f"Example {i} in EmployeeViewSet is invalid: {error_msg}")

    def test_paginated_list_examples_have_correct_format(self):
        """Test that paginated list examples have the correct structure"""
        # Check specific files that have list endpoints with pagination
        files_to_check = [
            Path(__file__).parent.parent.parent.parent / "apps" / "core" / "api" / "views" / "permission.py",
            Path(__file__).parent.parent.parent.parent / "apps" / "hrm" / "api" / "views" / "recruitment_channel.py",
            Path(__file__).parent.parent.parent.parent / "apps" / "hrm" / "api" / "views" / "employee.py",
        ]

        for filepath in files_to_check:
            examples = self._extract_openapi_examples_from_file(filepath)

            for example in examples:
                # Skip None examples (e.g., 204 responses)
                if example is None:
                    continue

                # If this is a success response with data
                if example.get("success") is True and "data" in example:
                    data = example["data"]
                    # Check if this looks like a paginated response
                    if isinstance(data, dict) and "results" in data:
                        # Verify pagination structure
                        self.assertIn("count", data, f"Paginated response in {filepath.name} missing 'count'")
                        self.assertIn("next", data, f"Paginated response in {filepath.name} missing 'next'")
                        self.assertIn("previous", data, f"Paginated response in {filepath.name} missing 'previous'")
                        self.assertIn("results", data, f"Paginated response in {filepath.name} missing 'results'")

                        # Verify results is a list
                        self.assertIsInstance(
                            data["results"],
                            list,
                            f"Paginated response 'results' in {filepath.name} should be a list",
                        )


if __name__ == "__main__":
    unittest.main()
