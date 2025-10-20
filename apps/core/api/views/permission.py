from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.history_mixin import HistoryMixin
from apps.core.api.filtersets import PermissionFilterSet
from apps.core.api.serializers.role import PermissionSerializer
from apps.core.models import Permission
from libs import BaseReadOnlyModelViewSet


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
class PermissionViewSet(HistoryMixin, BaseReadOnlyModelViewSet):
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
