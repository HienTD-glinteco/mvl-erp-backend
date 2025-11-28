from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.realestate.api.filtersets import ProjectFilterSet
from apps.realestate.api.serializers import ProjectSerializer
from apps.realestate.models import Project
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all projects",
        description="Retrieve a paginated list of all real estate projects with support for filtering and search",
        tags=["6.10: Project"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "DA001",
                                "name": "Main Office Project",
                                "address": "123 Main Street, District 1, Ho Chi Minh City",
                                "description": "Primary office location",
                                "status": "active",
                                "is_active": True,
                                "created_at": "2025-11-14T03:00:00Z",
                                "updated_at": "2025-11-14T03:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new project",
        description="Create a new real estate project. Code is auto-generated server-side.",
        tags=["6.10: Project"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "New Development Project",
                    "address": "456 Development Road, District 2",
                    "description": "New residential project",
                    "status": "active",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DA001",
                        "name": "New Development Project",
                        "address": "456 Development Road, District 2",
                        "description": "New residential project",
                        "status": "active",
                        "is_active": True,
                        "created_at": "2025-11-14T03:00:00Z",
                        "updated_at": "2025-11-14T03:00:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get project details",
        description="Retrieve detailed information about a specific project",
        tags=["6.10: Project"],
    ),
    update=extend_schema(
        summary="Update project",
        description="Update project information. Code cannot be changed.",
        tags=["6.10: Project"],
    ),
    partial_update=extend_schema(
        summary="Partially update project",
        description="Partially update project information",
        tags=["6.10: Project"],
    ),
    destroy=extend_schema(
        summary="Delete project",
        description="Remove a project from the system",
        tags=["6.10: Project"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            )
        ],
    ),
)
class ProjectViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Project model"""

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filterset_class = ProjectFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name"]

    # Permission registration attributes
    module = "Real Estate"
    submodule = "Project Management"
    permission_prefix = "project"
