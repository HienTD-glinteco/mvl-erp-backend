"""
Tests for export action filterset parameters in EnhancedAutoSchema.

These tests verify that filter parameters from a ViewSet's filterset_class
are automatically added to the export action documentation.
"""

from unittest.mock import MagicMock

import django_filters
import pytest
from rest_framework import serializers

from apps.core.models import Role
from libs.drf.spectacular.field_filtering import EnhancedAutoSchema


class TestFilterSet(django_filters.FilterSet):
    """Test filterset with various filter types."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="exact")
    is_active = django_filters.BooleanFilter()
    created_at_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_at_to = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Role
        fields = ["name", "code", "is_active", "created_at_from", "created_at_to"]


class TestFilterSetWithChoices(django_filters.FilterSet):
    """Test filterset with choice field."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("pending", "Pending"),
    ]

    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES)

    class Meta:
        model = Role
        fields = ["status"]


class TestSerializer(serializers.ModelSerializer):
    """Test serializer."""

    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class TestExportFiltersetParameters:
    """Test cases for export action filterset parameters."""

    @pytest.fixture
    def mock_view_with_export_action(self):
        """Create a mock view for export action testing."""
        view = MagicMock()
        view.action = "export"
        view.filterset_class = TestFilterSet
        return view

    @pytest.fixture
    def mock_view_with_choices_filterset(self):
        """Create a mock view with a filterset that has choices."""
        view = MagicMock()
        view.action = "export"
        view.filterset_class = TestFilterSetWithChoices
        return view

    @pytest.fixture
    def mock_view_without_filterset(self):
        """Create a mock view without filterset_class."""
        view = MagicMock()
        view.action = "export"
        view.filterset_class = None
        return view

    @pytest.fixture
    def mock_view_non_export_action(self):
        """Create a mock view for non-export action."""
        view = MagicMock()
        view.action = "list"
        view.filterset_class = TestFilterSet
        return view

    @pytest.fixture
    def auto_schema(self, mock_view_with_export_action):
        """Create an EnhancedAutoSchema instance."""
        schema = EnhancedAutoSchema()
        schema.method = "GET"
        schema.view = mock_view_with_export_action
        return schema

    def test_adds_filterset_parameters_for_export_action(self, auto_schema):
        """Test that filterset parameters are added for export action."""
        # Mock the base class method
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # Check that filter parameters were added
        param_names = [p.name for p in parameters]
        assert "name" in param_names
        assert "code" in param_names
        assert "is_active" in param_names
        assert "created_at_from" in param_names
        assert "created_at_to" in param_names

    def test_filter_descriptions_include_lookup_expr(self, auto_schema):
        """Test that filter descriptions include lookup expression info."""
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # Find the name parameter
        name_param = next((p for p in parameters if p.name == "name"), None)
        assert name_param is not None
        assert "case-insensitive partial match" in name_param.description

        # Find the code parameter
        code_param = next((p for p in parameters if p.name == "code"), None)
        assert code_param is not None
        assert "Filter by code" in code_param.description

    def test_filter_with_different_field_name(self, auto_schema):
        """Test that filters with different field_name are documented correctly."""
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # created_at_from has field_name="created_at"
        param = next((p for p in parameters if p.name == "created_at_from"), None)
        assert param is not None
        assert "created_at" in param.description
        assert "greater than or equal" in param.description

    def test_boolean_filter_type(self, auto_schema):
        """Test that BooleanFilter parameters have bool type."""
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # Find the is_active parameter
        is_active_param = next((p for p in parameters if p.name == "is_active"), None)
        assert is_active_param is not None
        assert is_active_param.type is bool

    def test_date_filter_type(self, auto_schema):
        """Test that DateFilter parameters have str type."""
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # Find date filter parameters
        created_at_from = next((p for p in parameters if p.name == "created_at_from"), None)
        assert created_at_from is not None
        assert created_at_from.type is str

    def test_choice_filter_has_enum(self):
        """Test that ChoiceFilter parameters have enum values."""
        schema = EnhancedAutoSchema()
        schema.method = "GET"
        view = MagicMock()
        view.action = "export"
        view.filterset_class = TestFilterSetWithChoices
        schema.view = view
        schema._get_serializer = lambda: TestSerializer()

        parameters = schema.get_override_parameters()

        # Find the status parameter
        status_param = next((p for p in parameters if p.name == "status"), None)
        assert status_param is not None
        assert status_param.enum is not None
        assert set(status_param.enum) == {"active", "inactive", "pending"}

    def test_no_parameters_for_non_export_action(self, mock_view_non_export_action):
        """Test that filterset parameters are NOT added for non-export actions."""
        schema = EnhancedAutoSchema()
        schema.method = "GET"
        schema.view = mock_view_non_export_action
        schema._get_serializer = lambda: TestSerializer()

        parameters = schema.get_override_parameters()

        # Filter parameters should not be added for list action
        param_names = [p.name for p in parameters]
        assert "name" not in param_names
        assert "code" not in param_names

    def test_no_parameters_when_no_filterset(self, mock_view_without_filterset):
        """Test that no filterset parameters are added when view has no filterset_class."""
        schema = EnhancedAutoSchema()
        schema.method = "GET"
        schema.view = mock_view_without_filterset
        schema._get_serializer = lambda: TestSerializer()

        parameters = schema.get_override_parameters()

        # Should not have filter parameters
        param_names = [p.name for p in parameters]
        # Only check that filter-specific params are not there
        assert "name" not in param_names
        assert "code" not in param_names

    def test_no_parameters_for_non_get_method(self, mock_view_with_export_action):
        """Test that filterset parameters are NOT added for non-GET methods."""
        schema = EnhancedAutoSchema()
        schema.method = "POST"
        schema.view = mock_view_with_export_action
        schema._get_serializer = lambda: TestSerializer()

        parameters = schema.get_override_parameters()

        # Filter parameters should not be added for POST
        param_names = [p.name for p in parameters]
        assert "name" not in param_names
        assert "code" not in param_names

    def test_all_parameters_are_optional(self, auto_schema):
        """Test that all filterset parameters are marked as optional."""
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # All filter parameters should be optional
        filter_params = [p for p in parameters if p.name in ["name", "code", "is_active"]]
        for param in filter_params:
            assert param.required is False

    def test_parameters_are_query_params(self, auto_schema):
        """Test that all filterset parameters are query parameters."""
        auto_schema._get_serializer = lambda: TestSerializer()

        parameters = auto_schema.get_override_parameters()

        # All filter parameters should be in query location
        filter_params = [p for p in parameters if p.name in ["name", "code", "is_active"]]
        for param in filter_params:
            assert param.location == "query"
