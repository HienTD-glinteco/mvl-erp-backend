"""
Examples of using FieldFilteringSerializerMixin.

This file demonstrates various use cases for the field filtering mixin
that allows frontend to control which fields are returned in API responses.
"""

from rest_framework import serializers, viewsets

from apps.core.models import Role
from libs import FieldFilteringSerializerMixin


# Example 1: Basic Usage
# =====================
class RoleSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """
    Simple serializer with field filtering.

    API Usage:
        GET /api/roles/              # Returns all fields
        GET /api/roles/?fields=id,name            # Returns only id and name
        GET /api/roles/?fields=id,name,description  # Returns id, name, description
    """

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


# Example 2: With Default Fields
# ===============================
class RoleSerializerWithDefaults(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """
    Serializer with default fields when no filtering is specified.

    When 'fields' parameter is not provided, only default_fields are returned.
    This is useful for reducing payload size by default while still allowing
    clients to request more fields when needed.

    API Usage:
        GET /api/roles/              # Returns only id and name (default_fields)
        GET /api/roles/?fields=id,code,description  # Returns specified fields
    """

    default_fields = ["id", "name"]

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


# Example 3: With Nested Serializers
# ===================================
class PermissionSerializer(FieldFilteringSerializerMixin, serializers.Serializer):
    """Nested serializer that also supports field filtering."""

    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()


class RoleWithPermissionsSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """
    Serializer with nested relationships supporting field filtering.

    Both the main serializer and nested serializer can be filtered independently.

    API Usage:
        GET /api/roles/?fields=id,name,permissions_detail
        # Returns role with only id, name, and full permissions_detail

        Note: To filter nested serializer fields, the nested serializer must
        also use FieldFilteringSerializerMixin and receive the request context.
    """

    permissions_detail = PermissionSerializer(source="permissions", many=True, read_only=True)

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "permissions_detail", "created_at"]


# Example 4: ViewSet Integration
# ===============================
class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet using serializer with field filtering.

    The mixin automatically gets the request from the serializer context,
    which is passed by DRF ViewSets by default.

    API Usage:
        GET /api/roles/              # List with default/all fields
        GET /api/roles/?fields=id,name            # List with filtered fields
        GET /api/roles/1/            # Retrieve with default/all fields
        GET /api/roles/1/?fields=name,description # Retrieve with filtered fields
    """

    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    # No additional code needed! The mixin handles everything automatically.


# Example 5: Combining with Pagination
# =====================================
class OptimizedRoleSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """
    Optimized serializer for list views with field filtering.

    Use default_fields to minimize payload size for list views,
    where full details are often not needed.

    API Usage:
        GET /api/roles/?page=1&page_size=20
        # Returns paginated list with only id, name (fast, small payload)

        GET /api/roles/?page=1&page_size=20&fields=id,code,name,description
        # Returns paginated list with specified fields

        GET /api/roles/1/
        # For detail view, you might use a different serializer or override get_serializer_class
    """

    default_fields = ["id", "name"]

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class OptimizedRoleViewSet(viewsets.ModelViewSet):
    """ViewSet using optimized serializer."""

    queryset = Role.objects.all()
    serializer_class = OptimizedRoleSerializer


# Example 6: Different Serializers for List and Detail
# =====================================================
class RoleListSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    default_fields = ["id", "name", "code"]

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description"]


class RoleDetailSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Full serializer for detail views."""

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class SmartRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet using different serializers for list and detail views.

    API Usage:
        GET /api/roles/              # Uses RoleListSerializer (lightweight)
        GET /api/roles/1/            # Uses RoleDetailSerializer (full details)
        GET /api/roles/?fields=id,name,description  # Custom fields in list view
    """

    queryset = Role.objects.all()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return RoleListSerializer
        return RoleDetailSerializer


# Performance Tips
# ================
"""
1. Use default_fields for list views to reduce payload size automatically
2. Request only needed fields in frontend: ?fields=id,name
3. For mobile apps with limited bandwidth, be aggressive with field filtering
4. Consider select_related() and prefetch_related() for nested data
5. Profile your API responses - field filtering reduces serialization time too

Common Patterns:
- List views: ?fields=id,name,thumbnail
- Detail views: ?fields=id,name,description,created_at,updated_at,nested_data
- Autocomplete: ?fields=id,name&search=keyword
- Mobile apps: ?fields=id,name (minimal fields)
- Admin panels: No fields param (all fields)
"""
