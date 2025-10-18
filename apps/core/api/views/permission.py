from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.core.api.filtersets import PermissionFilterSet
from apps.core.api.serializers.role import PermissionSerializer
from apps.core.models import Permission
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List permissions",
        description="Retrieve a list of all permissions available in the system",
        tags=["Permissions"],
        examples=[
            OpenApiExample(
                "List permissions success",
                description="Example response when listing permissions",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "name": "Create User",
                                "description": "Permission to create users",
                                "module": "Core",
                                "submodule": "User Management",
                                "created_at": "2025-01-01T00:00:00Z",
                                "updated_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "user.update",
                                "name": "Update User",
                                "description": "Permission to update users",
                                "module": "Core",
                                "submodule": "User Management",
                                "created_at": "2025-01-01T00:00:00Z",
                                "updated_at": "2025-01-01T00:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get permission details",
        description="Retrieve detailed information about a specific permission",
        tags=["Permissions"],
        examples=[
            OpenApiExample(
                "Get permission success",
                description="Example response when retrieving a permission",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "user.create",
                        "name": "Create User",
                        "description": "Permission to create users",
                        "module": "Core",
                        "submodule": "User Management",
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get permission not found",
                description="Error response when permission is not found",
                value={"success": False, "error": "Permission not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
)
class PermissionViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Permission model - Read only"""

    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    filterset_class = PermissionFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "description", "module", "submodule"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "Core"
    submodule = "Permission Management"
    permission_prefix = "permission"

    @extend_schema(
        summary="Get permission structure (modules/submodules)",
        description=(
            "Return distinct module and/or submodule names from permissions. "
            "Use `type` query param to specify which data to return:\n\n"
            "- `type=module`: return modules only\n"
            "- `type=submodule`: return submodules only\n"
            "- omit or `type=both`: return both"
        ),
        tags=["Permissions"],
        parameters=[
            OpenApiParameter(
                name="type",
                description="Specify whether to return 'module', 'submodule', or 'both' (default).",
                required=False,
                type=str,
                enum=["module", "submodule", "both"],
            ),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "modules": {"type": "array", "items": {"type": "string"}},
                    "submodules": {"type": "array", "items": {"type": "string"}},
                },
            }
        },
        examples=[
            OpenApiExample(
                "Get permission structure (both)",
                description="Example response when requesting both modules and submodules",
                value={
                    "success": True,
                    "data": {
                        "modules": ["Core", "HRM", "CRM"],
                        "submodules": [
                            "User Management",
                            "Role Management",
                            "Employee Management",
                            "Customer Management",
                        ],
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get permission structure (module only)",
                description="Example response when requesting modules only (type=module)",
                value={"success": True, "data": {"modules": ["Core", "HRM", "CRM"]}},
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="structure")
    def structure(self, request):
        """Return distinct module and/or submodule values."""
        query_type = request.query_params.get("type", "both").lower()

        response_data = {}

        if query_type in ["module", "both"]:
            modules = Permission.objects.exclude(module="").order_by().values_list("module", flat=True).distinct()
            response_data["modules"] = list(modules)

        if query_type in ["submodule", "both"]:
            submodules = (
                Permission.objects.exclude(submodule="").order_by().values_list("submodule", flat=True).distinct()
            )
            response_data["submodules"] = list(submodules)

        return Response(response_data)
