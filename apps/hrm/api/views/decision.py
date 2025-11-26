from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import DecisionFilterSet
from apps.hrm.api.serializers import DecisionExportSerializer, DecisionSerializer
from apps.hrm.models import Decision
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all decisions",
        description="Retrieve a paginated list of all decisions with support for filtering by decision number, "
        "name, signing date range, effective date range, signer, and signing status",
        tags=["Decision"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "decision_number": "QD-2025-001",
                                "name": "Decision on salary adjustment",
                                "signing_date": "2025-01-15",
                                "signer": {
                                    "id": 1,
                                    "code": "MV000001",
                                    "fullname": "John Doe",
                                    "email": "john.doe@example.com",
                                },
                                "effective_date": "2025-02-01",
                                "reason": "Annual salary review",
                                "content": "Salary adjustment for Q1 2025...",
                                "note": "Approved by HR",
                                "signing_status": "issued",
                                "signing_status_color": "GREEN",
                                "attachments": [],
                                "created_at": "2025-01-15T10:00:00Z",
                                "updated_at": "2025-01-15T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get decision details",
        description="Retrieve detailed information about a specific decision",
        tags=["Decision"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "decision_number": "QD-2025-001",
                        "name": "Decision on salary adjustment",
                        "signing_date": "2025-01-15",
                        "signer": {
                            "id": 1,
                            "code": "MV000001",
                            "fullname": "John Doe",
                            "email": "john.doe@example.com",
                        },
                        "effective_date": "2025-02-01",
                        "reason": "Annual salary review",
                        "content": "Salary adjustment for Q1 2025...",
                        "note": "Approved by HR",
                        "signing_status": "issued",
                        "signing_status_color": "GREEN",
                        "attachments": [],
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create a new decision",
        description="Create a new decision record",
        tags=["Decision"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "decision_number": "QD-2025-002",
                    "name": "Decision on employee promotion",
                    "signing_date": "2025-01-20",
                    "signer_id": 1,
                    "effective_date": "2025-02-01",
                    "reason": "Performance evaluation results",
                    "content": "Promotion decision content...",
                    "note": "HR approved",
                    "signing_status": "draft",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 2,
                        "decision_number": "QD-2025-002",
                        "name": "Decision on employee promotion",
                        "signing_date": "2025-01-20",
                        "signer": {
                            "id": 1,
                            "code": "MV000001",
                            "fullname": "John Doe",
                            "email": "john.doe@example.com",
                        },
                        "effective_date": "2025-02-01",
                        "reason": "Performance evaluation results",
                        "content": "Promotion decision content...",
                        "note": "HR approved",
                        "signing_status": "draft",
                        "signing_status_color": "GREY",
                        "attachments": [],
                        "created_at": "2025-01-20T10:00:00Z",
                        "updated_at": "2025-01-20T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Validation",
                value={
                    "success": False,
                    "data": None,
                    "error": {"decision_number": ["This field must be unique."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update decision",
        description="Update all fields of a decision",
        tags=["Decision"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "decision_number": "QD-2025-002",
                    "name": "Decision on employee promotion (updated)",
                    "signing_date": "2025-01-20",
                    "signer_id": 1,
                    "effective_date": "2025-02-01",
                    "reason": "Performance evaluation results",
                    "content": "Updated promotion decision content...",
                    "note": "HR approved - final",
                    "signing_status": "issued",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 2,
                        "decision_number": "QD-2025-002",
                        "name": "Decision on employee promotion (updated)",
                        "signing_date": "2025-01-20",
                        "signer": {
                            "id": 1,
                            "code": "MV000001",
                            "fullname": "John Doe",
                            "email": "john.doe@example.com",
                        },
                        "effective_date": "2025-02-01",
                        "reason": "Performance evaluation results",
                        "content": "Updated promotion decision content...",
                        "note": "HR approved - final",
                        "signing_status": "issued",
                        "signing_status_color": "GREEN",
                        "attachments": [],
                        "created_at": "2025-01-20T10:00:00Z",
                        "updated_at": "2025-01-20T12:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update decision",
        description="Update specific fields of a decision",
        tags=["Decision"],
    ),
    destroy=extend_schema(
        summary="Delete decision",
        description="Soft delete a decision from the system",
        tags=["Decision"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
            ),
        ],
    ),
)
class DecisionViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Decision model.

    Provides CRUD operations and XLSX export for decisions.
    Supports filtering, searching, and ordering.
    """

    queryset = Decision.objects.select_related("signer").prefetch_related("attachments")
    serializer_class = DecisionSerializer
    filterset_class = DecisionFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["decision_number", "name"]
    ordering_fields = ["decision_number", "signing_date", "signer__fullname", "effective_date", "created_at"]
    ordering = ["-signing_date", "-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Decision Management"
    permission_prefix = "decision"

    # Export configuration
    export_serializer_class = DecisionExportSerializer
    export_filename = "decisions"
