from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentChannelFilterSet
from apps.hrm.api.serializers import RecruitmentChannelSerializer
from apps.hrm.models import RecruitmentChannel
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment channels",
        description="Retrieve a list of all recruitment channels with support for filtering and search",
        tags=["Recruitment Channel"],
        examples=[
            OpenApiExample(
                "List recruitment channels success",
                description="Example response when listing recruitment channels",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "code": "RC001",
                                "name": "LinkedIn",
                                "description": "Recruitment through LinkedIn platform",
                                "is_active": True,
                                "created_at": "2025-01-01T00:00:00Z",
                                "updated_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440002",
                                "code": "RC002",
                                "name": "Job Fair",
                                "description": "Recruitment through job fairs and events",
                                "is_active": True,
                                "created_at": "2025-01-02T10:00:00Z",
                                "updated_at": "2025-01-02T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new recruitment channel",
        description="Create a new recruitment channel in the system",
        tags=["Recruitment Channel"],
        examples=[
            OpenApiExample(
                "Create recruitment channel request",
                description="Example request to create a new recruitment channel",
                value={
                    "name": "Company Website",
                    "description": "Recruitment through company career page",
                    "is_active": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Create recruitment channel success",
                description="Success response when creating a recruitment channel",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440003",
                        "code": "RC003",
                        "name": "Company Website",
                        "description": "Recruitment through company career page",
                        "is_active": True,
                        "created_at": "2025-01-15T14:30:00Z",
                        "updated_at": "2025-01-15T14:30:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Create recruitment channel validation error",
                description="Error response when validation fails",
                value={"success": False, "error": {"name": ["Recruitment channel with this name already exists"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get recruitment channel details",
        description="Retrieve detailed information about a specific recruitment channel",
        tags=["Recruitment Channel"],
        examples=[
            OpenApiExample(
                "Get recruitment channel success",
                description="Example response when retrieving a recruitment channel",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "code": "RC001",
                        "name": "LinkedIn",
                        "description": "Recruitment through LinkedIn platform",
                        "is_active": True,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get recruitment channel not found",
                description="Error response when recruitment channel is not found",
                value={"success": False, "error": "Recruitment channel not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update recruitment channel",
        description="Update recruitment channel information",
        tags=["Recruitment Channel"],
        examples=[
            OpenApiExample(
                "Update recruitment channel request",
                description="Example request to update a recruitment channel",
                value={
                    "name": "LinkedIn Premium",
                    "description": "Recruitment through LinkedIn premium account",
                    "is_active": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Update recruitment channel success",
                description="Success response when updating a recruitment channel",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "code": "RC001",
                        "name": "LinkedIn Premium",
                        "description": "Recruitment through LinkedIn premium account",
                        "is_active": True,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-16T09:15:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment channel",
        description="Partially update recruitment channel information",
        tags=["Recruitment Channel"],
        examples=[
            OpenApiExample(
                "Partial update request",
                description="Example request to partially update a recruitment channel",
                value={"is_active": False},
                request_only=True,
            ),
            OpenApiExample(
                "Partial update success",
                description="Success response when partially updating a recruitment channel",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "code": "RC001",
                        "name": "LinkedIn",
                        "description": "Recruitment through LinkedIn platform",
                        "is_active": False,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-16T11:30:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete recruitment channel",
        description="Remove a recruitment channel from the system",
        tags=["Recruitment Channel"],
        examples=[
            OpenApiExample(
                "Delete recruitment channel success",
                description="Success response when deleting a recruitment channel",
                value=None,
                response_only=True,
                status_codes=["204"],
            ),
            OpenApiExample(
                "Delete recruitment channel error",
                description="Error response when recruitment channel cannot be deleted (e.g., in use)",
                value={"success": False, "error": "Cannot delete recruitment channel that is in use"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class RecruitmentChannelViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentChannel model"""

    queryset = RecruitmentChannel.objects.all()
    serializer_class = RecruitmentChannelSerializer
    filterset_class = RecruitmentChannelFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_channel"
