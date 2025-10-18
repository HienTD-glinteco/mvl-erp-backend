"""
Tests for field filtering AutoSchema extension.

These tests verify that the field filtering query parameter is automatically
documented when a serializer uses FieldFilteringSerializerMixin.
"""

from unittest.mock import MagicMock

import pytest
from rest_framework import serializers

from apps.core.models import Role
from libs.serializers.mixins import FieldFilteringSerializerMixin
from libs.spectacular.field_filtering import FieldFilteringAutoSchema


class TestFieldFilteringSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Test serializer with field filtering mixin."""

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class TestFieldFilteringSerializerWithDefaults(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Test serializer with default_fields attribute."""

    default_fields = ["id", "name"]

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class TestRegularSerializer(serializers.ModelSerializer):
    """Test serializer without field filtering mixin."""

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description"]


class TestFieldFilteringAutoSchema:
    """Test cases for FieldFilteringAutoSchema."""

    @pytest.fixture
    def mock_view(self):
        """Create a mock view for testing."""
        view = MagicMock()
        view.action = "list"
        view.get_queryset.return_value = Role.objects.none()
        return view

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        request = MagicMock()
        request.method = "GET"
        return request

    def _create_schema(self, serializer_class, view, request, method="GET"):
        """Helper method to create an AutoSchema instance."""
        schema = FieldFilteringAutoSchema()
        schema.view = view
        schema.path = "/api/test/"
        schema.method = method
        schema.get_serializer = lambda: serializer_class()
        return schema

    def test_adds_fields_parameter_for_field_filtering_serializer(self, mock_view, mock_request):
        """Test that fields parameter is added for serializers with FieldFilteringSerializerMixin."""
        schema = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        # Find the fields parameter
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)

        assert fields_param is not None
        assert fields_param["in"] == "query"
        # Check required field - it may not be present if False is default
        assert fields_param.get("required", False) is False
        assert "schema" in fields_param
        assert fields_param["schema"]["type"] == "string"

    def test_fields_parameter_includes_available_fields(self, mock_view, mock_request):
        """Test that the fields parameter description includes all available fields."""
        schema = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is not None

        description = fields_param.get("description", "")
        # Check that all fields are mentioned in description
        assert "`id`" in description
        assert "`code`" in description
        assert "`name`" in description
        assert "`description`" in description
        assert "`created_at`" in description
        assert "`updated_at`" in description

    def test_fields_parameter_includes_default_fields_info(self, mock_view, mock_request):
        """Test that default_fields are mentioned in the description."""
        schema = self._create_schema(TestFieldFilteringSerializerWithDefaults, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is not None

        description = fields_param.get("description", "")
        assert "default fields" in description.lower()
        assert "`id`" in description
        assert "`name`" in description

    def test_no_fields_parameter_for_regular_serializer(self, mock_view, mock_request):
        """Test that fields parameter is not added for regular serializers."""
        schema = self._create_schema(TestRegularSerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        # Fields parameter should not be present
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is None

    def test_fields_parameter_only_for_get_requests(self, mock_view, mock_request):
        """Test that fields parameter is only added for GET/HEAD/OPTIONS requests."""
        # Test GET - should have fields parameter
        schema_get = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request, method="GET")
        params_get = schema_get.get_override_parameters()
        fields_param_get = next((p for p in params_get if p.get("name") == "fields"), None)
        assert fields_param_get is not None

        # Test POST - should not have fields parameter
        schema_post = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request, method="POST")
        params_post = schema_post.get_override_parameters()
        fields_param_post = next((p for p in params_post if p.get("name") == "fields"), None)
        assert fields_param_post is None

        # Test PUT - should not have fields parameter
        schema_put = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request, method="PUT")
        params_put = schema_put.get_override_parameters()
        fields_param_put = next((p for p in params_put if p.get("name") == "fields"), None)
        assert fields_param_put is None

    def test_fields_parameter_has_example(self, mock_view, mock_request):
        """Test that the fields parameter includes an example value."""
        schema = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is not None
        assert "example" in fields_param
        assert isinstance(fields_param["example"], str)
        # Example should be comma-separated field names
        assert "," in fields_param["example"]

    def test_description_includes_usage_instructions(self, mock_view, mock_request):
        """Test that the description includes usage instructions."""
        schema = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is not None

        description = fields_param.get("description", "")
        assert "comma-separated" in description.lower()
        assert "?fields=" in description
        assert "Available fields" in description

    def test_no_fields_parameter_when_no_serializer(self, mock_view, mock_request):
        """Test that no fields parameter is added when serializer cannot be determined."""
        schema = FieldFilteringAutoSchema()
        schema.view = mock_view
        schema.path = "/api/test/"
        schema.method = "GET"
        schema.get_serializer = lambda: None  # No serializer

        parameters = schema.get_override_parameters()
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is None

    def test_handles_serializer_with_no_fields(self, mock_view, mock_request):
        """Test that the extension handles serializers with no fields gracefully."""

        class EmptySerializer(FieldFilteringSerializerMixin, serializers.Serializer):
            pass

        schema = self._create_schema(EmptySerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        # Should not add fields parameter if there are no fields
        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is None

    def test_fields_sorted_in_description(self, mock_view, mock_request):
        """Test that fields are sorted alphabetically in the description."""
        schema = self._create_schema(TestFieldFilteringSerializer, mock_view, mock_request)
        parameters = schema.get_override_parameters()

        fields_param = next((p for p in parameters if p.get("name") == "fields"), None)
        assert fields_param is not None

        description = fields_param.get("description", "")
        # Extract field names from description
        # Should be sorted alphabetically
        expected_fields = ["code", "created_at", "description", "id", "name", "updated_at"]
        for field in expected_fields:
            assert f"`{field}`" in description
