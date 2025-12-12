from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import KPICriterionFilterSet
from apps.payroll.api.serializers import KPICriterionSerializer
from apps.payroll.models import KPICriterion
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all KPI criteria",
        description="Retrieve a paginated list of all KPI evaluation criteria with support for filtering and search. Target field accepts: 'sales' or 'backoffice'.",
        tags=["10.2: KPI Criteria"],
        examples=[
            OpenApiExample(
                "Success - List of criteria",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "target": "SALES",
                                "evaluation_type": "job_performance",
                                "name": "Revenue Achievement",
                                "description": "Monthly revenue target achievement",
                                "component_total_score": "70.00",
                                "ordering": 1,
                                "active": True,
                                "created_by": 1,
                                "updated_by": 1,
                                "created_at": "2025-12-11T07:00:00Z",
                                "updated_at": "2025-12-11T07:00:00Z",
                            },
                            {
                                "id": 2,
                                "target": "SALES",
                                "evaluation_type": "discipline",
                                "name": "Attendance",
                                "description": "Monthly attendance record",
                                "component_total_score": "30.00",
                                "ordering": 2,
                                "active": True,
                                "created_by": 1,
                                "updated_by": None,
                                "created_at": "2025-12-11T08:00:00Z",
                                "updated_at": "2025-12-11T08:00:00Z",
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get KPI criterion details",
        description="Retrieve detailed information about a specific KPI criterion",
        tags=["10.2: KPI Criteria"],
        examples=[
            OpenApiExample(
                "Success - Single criterion",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "target": "sales",
                        "evaluation_type": "job_performance",
                        "name": "Revenue Achievement",
                        "description": "Monthly revenue target achievement",
                        "component_total_score": "70.00",
                        "ordering": 1,
                        "active": True,
                        "created_by": 1,
                        "updated_by": 1,
                        "created_at": "2025-12-11T07:00:00Z",
                        "updated_at": "2025-12-11T07:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Not found",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Not found."},
                },
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
    create=extend_schema(
        summary="Create a new KPI criterion",
        description="Create a new KPI evaluation criterion. The created_by field is set automatically. Target must be either 'sales' or 'backoffice'.",
        tags=["10.2: KPI Criteria"],
        examples=[
            OpenApiExample(
                "Request - Create criterion",
                value={
                    "target": "sales",
                    "evaluation_type": "job_performance",
                    "name": "Revenue Achievement",
                    "description": "Monthly revenue target achievement",
                    "component_total_score": "70.00",
                    "ordering": 1,
                    "active": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Created",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "target": "sales",
                        "evaluation_type": "job_performance",
                        "name": "Revenue Achievement",
                        "description": "Monthly revenue target achievement",
                        "component_total_score": "70.00",
                        "ordering": 1,
                        "active": True,
                        "created_by": 1,
                        "updated_by": None,
                        "created_at": "2025-12-11T07:00:00Z",
                        "updated_at": "2025-12-11T07:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Error - Validation failed",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "component_total_score": ["Component total score must be between 0 and 100"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Duplicate criterion",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "non_field_errors": ["A criterion with this target, evaluation type, and name already exists"]
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update KPI criterion",
        description="Update all fields of a KPI criterion. The updated_by field is set automatically.",
        tags=["10.2: KPI Criteria"],
        examples=[
            OpenApiExample(
                "Request - Update criterion",
                value={
                    "target": "sales",
                    "evaluation_type": "job_performance",
                    "name": "Revenue Achievement",
                    "description": "Updated monthly revenue target achievement",
                    "component_total_score": "75.00",
                    "ordering": 1,
                    "active": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "target": "sales",
                        "evaluation_type": "job_performance",
                        "name": "Revenue Achievement",
                        "description": "Updated monthly revenue target achievement",
                        "component_total_score": "75.00",
                        "ordering": 1,
                        "active": True,
                        "created_by": 1,
                        "updated_by": 2,
                        "created_at": "2025-12-11T07:00:00Z",
                        "updated_at": "2025-12-11T09:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update KPI criterion",
        description="Update specific fields of a KPI criterion. The updated_by field is set automatically.",
        tags=["10.2: KPI Criteria"],
        examples=[
            OpenApiExample(
                "Request - Deactivate criterion",
                value={"active": False},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Partially updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "target": "sales",
                        "evaluation_type": "job_performance",
                        "name": "Revenue Achievement",
                        "description": "Monthly revenue target achievement",
                        "component_total_score": "70.00",
                        "ordering": 1,
                        "active": False,
                        "created_by": 1,
                        "updated_by": 2,
                        "created_at": "2025-12-11T07:00:00Z",
                        "updated_at": "2025-12-11T09:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete KPI criterion",
        description="Soft-delete a KPI criterion by setting active=False. Physical deletion is not recommended to preserve audit history.",
        tags=["10.2: KPI Criteria"],
        examples=[
            OpenApiExample(
                "Success - Deleted",
                value={"success": True, "data": None, "error": None},
                response_only=True,
                status_codes=["204"],
            ),
            OpenApiExample(
                "Error - Not found",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Not found."},
                },
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
)
class KPICriterionViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for KPICriterion model.

    Provides full CRUD operations for KPI evaluation criteria.
    Supports filtering by target, evaluation_type, and active status.
    Supports searching by name and description.
    """

    queryset = KPICriterion.objects.all()
    serializer_class = KPICriterionSerializer
    filterset_class = KPICriterionFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["target", "evaluation_type", "name", "ordering", "created_at", "updated_at"]
    ordering = ["target", "evaluation_type", "ordering"]

    # Permission registration attributes
    module = "Payroll"
    submodule = "KPI Management"
    permission_prefix = "kpi_criterion"

    def perform_create(self, serializer):
        """Set created_by when creating a new criterion."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by when updating a criterion."""
        serializer.save(updated_by=self.request.user)
