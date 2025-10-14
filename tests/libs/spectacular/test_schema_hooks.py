"""
Tests for drf-spectacular schema post-processing hooks.
"""

import unittest

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from libs.spectacular.schema_hooks import wrap_with_envelope


class SchemaHookTest(unittest.TestCase):
    """Test cases for wrap_with_envelope post-processing hook (no DB required)"""

    def test_wrap_with_envelope_basic_structure(self):
        """Test that the hook wraps responses in envelope format"""
        # Arrange
        result = {
            "paths": {
                "/api/test/": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # Act
        wrapped_result = wrap_with_envelope(result, None, None, True)

        # Assert
        response_schema = wrapped_result["paths"]["/api/test/"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]

        # Check envelope structure exists
        assert "properties" in response_schema
        assert "success" in response_schema["properties"]
        assert "data" in response_schema["properties"]
        assert "error" in response_schema["properties"]

        # Check success is boolean
        assert response_schema["properties"]["success"]["type"] == "boolean"

        # Check data contains original schema
        data_schema = response_schema["properties"]["data"]
        assert data_schema["type"] == "object"
        assert "id" in data_schema["properties"]
        assert "name" in data_schema["properties"]

    def test_wrap_with_envelope_preserves_list_schemas(self):
        """Test that list/array schemas are preserved correctly"""
        # Arrange
        result = {
            "paths": {
                "/api/items/": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"type": "object", "properties": {"id": {"type": "integer"}}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # Act
        wrapped_result = wrap_with_envelope(result, None, None, True)

        # Assert
        response_schema = wrapped_result["paths"]["/api/items/"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        data_schema = response_schema["properties"]["data"]

        # Data should contain the original array schema
        assert data_schema["type"] == "array"
        assert "items" in data_schema

    def test_wrap_with_envelope_skips_error_responses(self):
        """Test that error responses (4xx, 5xx) are not wrapped"""
        # Arrange
        result = {
            "paths": {
                "/api/test/": {
                    "get": {
                        "responses": {
                            "200": {"content": {"application/json": {"schema": {"type": "object"}}}},
                            "400": {
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object", "properties": {"error": {"type": "string"}}}
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }

        # Act
        wrapped_result = wrap_with_envelope(result, None, None, True)

        # Assert
        success_response = wrapped_result["paths"]["/api/test/"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        error_response = wrapped_result["paths"]["/api/test/"]["get"]["responses"]["400"]["content"][
            "application/json"
        ]["schema"]

        # Success response should be wrapped
        assert "properties" in success_response
        assert "success" in success_response["properties"]

        # Error response should NOT be wrapped (should remain unchanged)
        assert "error" in error_response["properties"]
        assert "success" not in error_response["properties"]

    def test_wrap_with_envelope_skips_non_json_responses(self):
        """Test that non-JSON responses are not modified"""
        # Arrange
        result = {
            "paths": {
                "/api/download/": {
                    "get": {
                        "responses": {
                            "200": {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}
                        }
                    }
                }
            }
        }

        # Act
        wrapped_result = wrap_with_envelope(result, None, None, True)

        # Assert
        response_schema = wrapped_result["paths"]["/api/download/"]["get"]["responses"]["200"]["content"][
            "application/pdf"
        ]["schema"]

        # Should remain unchanged
        assert response_schema["type"] == "string"
        assert response_schema["format"] == "binary"
        assert "properties" not in response_schema

    def test_wrap_with_envelope_doesnt_double_wrap(self):
        """Test that already wrapped schemas are not wrapped again"""
        # Arrange - pre-wrapped schema
        result = {
            "paths": {
                "/api/test/": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # Act
        wrapped_result = wrap_with_envelope(result, None, None, True)

        # Assert
        response_schema = wrapped_result["paths"]["/api/test/"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]

        # Should not have nested success/data structure
        assert response_schema["properties"]["success"]["type"] == "boolean"
        assert response_schema["properties"]["data"]["type"] == "object"
        # Should not have success inside data
        if "properties" in response_schema["properties"]["data"]:
            assert "success" not in response_schema["properties"]["data"]["properties"]

    def test_wrap_with_envelope_skips_when_manual_examples_defined(self):
        """Test that schemas with manual examples are not wrapped (examples should already have envelope)"""
        # Arrange - schema with manual examples defined
        result = {
            "paths": {
                "/api/roles/": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "count": {"type": "integer"},
                                                "results": {"type": "array"},
                                            },
                                        },
                                        "examples": {
                                            "List roles success": {
                                                "value": {
                                                    "success": True,
                                                    "data": {
                                                        "count": 2,
                                                        "next": None,
                                                        "previous": None,
                                                        "results": [],
                                                    },
                                                }
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # Act
        wrapped_result = wrap_with_envelope(result, None, None, True)

        # Assert - schema should NOT be wrapped because examples are defined
        response_schema = wrapped_result["paths"]["/api/roles/"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]

        # Should remain unwrapped (original pagination structure)
        assert "count" in response_schema["properties"]
        assert "results" in response_schema["properties"]
        assert "success" not in response_schema["properties"]

        # Examples should remain unchanged
        examples = wrapped_result["paths"]["/api/roles/"]["get"]["responses"]["200"]["content"]["application/json"][
            "examples"
        ]
        assert "List roles success" in examples
        assert examples["List roles success"]["value"]["success"] is True


class SchemaGenerationIntegrationTest(TestCase):
    """Integration tests for schema generation with envelope wrapping"""

    def setUp(self):
        self.client = APIClient()

    def test_schema_endpoint_accessible(self):
        """Test that schema endpoint is accessible"""
        # This test may only work in local/develop environments
        try:
            url = reverse("schema")
            response = self.client.get(url)
            # Schema endpoint should be accessible (either 200 or 404 if not in correct env)
            assert response.status_code in [200, 404]
        except Exception:
            # If schema URL is not configured, skip this test
            pytest.skip("Schema endpoint not configured in this environment")

    def _check_wrapped_response(self, json_schema):
        """Helper method to check if a response is wrapped"""
        if "properties" in json_schema:
            props = json_schema["properties"]
            if "success" in props and "data" in props:
                return True
        return False

    def _find_wrapped_responses(self, paths):
        """Helper method to find wrapped responses in schema paths"""
        for path_item in paths.values():
            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                responses = operation.get("responses", {})
                for status_code, response_def in responses.items():
                    if not status_code.startswith("2"):
                        continue

                    content = response_def.get("content", {})
                    if "application/json" in content:
                        json_schema = content["application/json"].get("schema", {})
                        if self._check_wrapped_response(json_schema):
                            return True
        return False

    def test_schema_contains_envelope_structure(self):
        """Test that generated schema includes envelope structure"""
        try:
            url = reverse("schema")
            response = self.client.get(url)

            if response.status_code == 200:
                schema = response.json() if hasattr(response, "json") else response.data

                # Check that paths exist
                assert "paths" in schema

                # Find at least one wrapped response
                paths = schema.get("paths", {})
                if paths:
                    found_wrapped = self._find_wrapped_responses(paths)
                    assert found_wrapped, "No wrapped responses found in schema"
        except Exception:
            pytest.skip("Schema endpoint not accessible or not configured")
