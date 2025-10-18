"""
Integration test for field filtering documentation in OpenAPI schema.

This test creates a minimal view and verifies that the OpenAPI schema
correctly includes the 'fields' query parameter documentation.
"""

import pytest
from django.urls import path
from rest_framework import serializers, viewsets
from rest_framework.test import APIRequestFactory

from apps.core.models import Role
from libs.serializers.mixins import FieldFilteringSerializerMixin
from libs.spectacular.field_filtering import FieldFilteringAutoSchema


class TestRoleSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Test serializer for integration testing."""

    default_fields = ["id", "name"]

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class TestRoleViewSet(viewsets.ReadOnlyModelViewSet):
    """Test viewset for integration testing."""

    queryset = Role.objects.all()
    serializer_class = TestRoleSerializer


@pytest.mark.django_db
class TestFieldFilteringSchemaIntegration:
    """Integration tests for field filtering schema generation."""

    def test_schema_includes_fields_parameter(self):
        """Test that the generated schema includes the 'fields' query parameter."""
        # Create the view
        view = TestRoleViewSet.as_view({"get": "list"})

        # Create a request
        factory = APIRequestFactory()
        request = factory.get("/api/test/")

        # Set up the view instance
        view_instance = view.cls()
        view_instance.action = "list"
        view_instance.request = request
        view_instance.format_kwarg = None

        # Generate the schema
        schema = FieldFilteringAutoSchema()
        schema.view = view_instance
        schema.path = "/api/test/"
        schema.method = "GET"

        # Get parameters
        parameters = schema.get_override_parameters()

        # Verify fields parameter exists
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is not None, "Fields parameter should be present in schema"
        assert fields_param["in"] == "query"
        assert "schema" in fields_param
        assert fields_param["schema"]["type"] == "string"

    def test_schema_fields_parameter_description(self):
        """Test that the fields parameter has a proper description."""
        view_instance = TestRoleViewSet()
        view_instance.action = "list"
        factory = APIRequestFactory()
        view_instance.request = factory.get("/api/test/")
        view_instance.format_kwarg = None

        schema = FieldFilteringAutoSchema()
        schema.view = view_instance
        schema.path = "/api/test/"
        schema.method = "GET"

        parameters = schema.get_override_parameters()
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)

        assert fields_param is not None
        description = fields_param.get("description", "")

        # Check that description includes all expected information
        assert "Available fields" in description
        assert "`id`" in description
        assert "`code`" in description
        assert "`name`" in description
        assert "`description`" in description
        assert "default fields" in description.lower()

    def test_schema_fields_parameter_has_example(self):
        """Test that the fields parameter includes an example."""
        view_instance = TestRoleViewSet()
        view_instance.action = "list"
        factory = APIRequestFactory()
        view_instance.request = factory.get("/api/test/")
        view_instance.format_kwarg = None

        schema = FieldFilteringAutoSchema()
        schema.view = view_instance
        schema.path = "/api/test/"
        schema.method = "GET"

        parameters = schema.get_override_parameters()
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)

        assert fields_param is not None
        assert "example" in fields_param
        assert isinstance(fields_param["example"], str)
        # Example should contain comma-separated field names
        assert "," in fields_param["example"]


@pytest.mark.django_db
class TestFieldFilteringWithRegularSerializer:
    """Test that regular serializers don't get the fields parameter."""

    def test_regular_serializer_no_fields_parameter(self):
        """Test that serializers without the mixin don't get fields parameter."""

        class RegularSerializer(serializers.ModelSerializer):
            class Meta:
                model = Role
                fields = ["id", "name"]

        class RegularViewSet(viewsets.ReadOnlyModelViewSet):
            queryset = Role.objects.all()
            serializer_class = RegularSerializer

        view_instance = RegularViewSet()
        view_instance.action = "list"
        factory = APIRequestFactory()
        view_instance.request = factory.get("/api/test/")
        view_instance.format_kwarg = None

        schema = FieldFilteringAutoSchema()
        schema.view = view_instance
        schema.path = "/api/test/"
        schema.method = "GET"

        parameters = schema.get_override_parameters()
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)

        # Should not have fields parameter
        assert fields_param is None
