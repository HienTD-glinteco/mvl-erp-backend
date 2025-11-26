from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.core.api.filtersets import PermissionFilterSet
from apps.core.api.serializers.role import PermissionSerializer
from apps.core.models import Permission
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List permissions",
        description="Retrieve a list of all permissions available in the system",
        tags=["Permissions"],
    ),
    retrieve=extend_schema(
        summary="Get permission details",
        description="Retrieve detailed information about a specific permission",
        tags=["Permissions"],
    ),
)
class PermissionViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Permission model - Read only"""

    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    filterset_class = PermissionFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "description", "module", "submodule"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "Core"
    submodule = "Permission Management"
    permission_prefix = "permission"

    def list(self, request, *args, **kwargs):
        """List permissions with optional get_all parameter."""
        get_all = request.query_params.get("get_all", "").lower() == "true"

        if get_all:
            # Return all results with pagination structure
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response({"count": queryset.count(), "next": None, "previous": None, "results": serializer.data})

        # Default paginated response
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Get permission structure (modules/submodules)",
        description=(
            "Return permission structure. "
            "Use `type` query param to specify which data to return:\n\n"
            "- `type=module`: return list of modules\n"
            "- `type=submodule`: return list of submodules\n"
            "- omit or `type=both`: return tree structure with modules as keys and their submodules as values"
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
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "modules": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    {
                        "type": "object",
                        "properties": {
                            "submodules": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
                ]
            }
        },
    )
    @action(detail=False, methods=["get"], url_path="structure")
    def structure(self, request):
        """Return permission structure as tree or lists."""
        query_type = request.query_params.get("type", "both").lower()

        if query_type == "module":
            modules = Permission.objects.exclude(module="").order_by().values_list("module", flat=True).distinct()
            response_data = {"modules": list(modules)}
        elif query_type == "submodule":
            submodules = (
                Permission.objects.exclude(submodule="").order_by().values_list("submodule", flat=True).distinct()
            )
            response_data = {"submodules": list(submodules)}
        else:  # both
            permissions = Permission.objects.exclude(module="").values("module", "submodule").distinct()
            tree = {}
            for perm in permissions:
                module = perm["module"]
                submodule = perm["submodule"]
                if module not in tree:
                    tree[module] = []
                if submodule and submodule not in tree[module]:
                    tree[module].append(submodule)
            response_data = tree

        return Response(response_data)
