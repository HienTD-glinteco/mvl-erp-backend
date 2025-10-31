from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import RelationshipFilterSet
from apps.hrm.api.serializers import RelationshipSerializer
from apps.hrm.constants import (
    API_RELATION_CREATE_DESCRIPTION,
    API_RELATION_CREATE_SUMMARY,
    API_RELATION_DELETE_DESCRIPTION,
    API_RELATION_DELETE_SUMMARY,
    API_RELATION_LIST_DESCRIPTION,
    API_RELATION_LIST_SUMMARY,
    API_RELATION_RETRIEVE_DESCRIPTION,
    API_RELATION_RETRIEVE_SUMMARY,
    API_RELATION_UPDATE_DESCRIPTION,
    API_RELATION_UPDATE_SUMMARY,
)
from apps.hrm.models import Relationship
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary=API_RELATION_LIST_SUMMARY,
        description=API_RELATION_LIST_DESCRIPTION,
        tags=["Relationship"],
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
                                "employee": 1,
                                "employee_code": "MV0001",
                                "employee_name": "John Doe",
                                "relative_name": "Jane Doe",
                                "relation_type": "SPOUSE",
                                "date_of_birth": "1990-05-15",
                                "national_id": "123456789",
                                "address": "123 Main Street",
                                "phone": "0901234567",
                                "attachment": None,
                                "note": "Emergency contact",
                                "is_active": True,
                                "created_by": 1,
                                "created_at": "2025-10-31T05:00:00Z",
                                "updated_at": "2025-10-31T05:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary=API_RELATION_CREATE_SUMMARY,
        description=API_RELATION_CREATE_DESCRIPTION,
        tags=["Relationship"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_code": "MV0001",
                        "employee_name": "John Doe",
                        "relative_name": "Jane Doe",
                        "relation_type": "SPOUSE",
                        "date_of_birth": "1990-05-15",
                        "national_id": "123456789",
                        "address": "123 Main Street",
                        "phone": "0901234567",
                        "attachment": None,
                        "note": "Emergency contact",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Success with attachment",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_code": "MV0001",
                        "employee_name": "John Doe",
                        "relative_name": "Jane Doe",
                        "relation_type": "SPOUSE",
                        "date_of_birth": "1990-05-15",
                        "national_id": "123456789",
                        "address": "123 Main Street",
                        "phone": "0901234567",
                        "attachment": {
                            "id": 1,
                            "purpose": "relationship",
                            "file_name": "marriage_certificate.pdf",
                            "file_path": "uploads/relationship/1/marriage_certificate.pdf",
                            "size": 123456,
                            "is_confirmed": True,
                            "view_url": "https://example.com/view/...",
                            "download_url": "https://example.com/download/...",
                        },
                        "note": "Emergency contact",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"employee": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary=API_RELATION_RETRIEVE_SUMMARY,
        description=API_RELATION_RETRIEVE_DESCRIPTION,
        tags=["Relationship"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_code": "MV0001",
                        "employee_name": "John Doe",
                        "relative_name": "Jane Doe",
                        "relation_type": "SPOUSE",
                        "date_of_birth": "1990-05-15",
                        "national_id": "123456789",
                        "address": "123 Main Street",
                        "phone": "0901234567",
                        "attachment": None,
                        "note": "Emergency contact",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary=API_RELATION_UPDATE_SUMMARY,
        description=API_RELATION_UPDATE_DESCRIPTION,
        tags=["Relationship"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_code": "MV0001",
                        "employee_name": "John Doe",
                        "relative_name": "Jane Doe",
                        "relation_type": "SPOUSE",
                        "date_of_birth": "1990-05-15",
                        "national_id": "123456789012",
                        "address": "456 New Street",
                        "phone": "0909876543",
                        "attachment": None,
                        "note": "Updated emergency contact",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T06:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        summary=API_RELATION_UPDATE_SUMMARY,
        description=API_RELATION_UPDATE_DESCRIPTION,
        tags=["Relationship"],
    ),
    destroy=extend_schema(
        summary=API_RELATION_DELETE_SUMMARY,
        description=API_RELATION_DELETE_DESCRIPTION,
        tags=["Relationship"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
            )
        ],
    ),
)
class RelationshipViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for managing employee relationships/next-of-kin"""

    queryset = Relationship.objects.select_related("employee", "attachment", "created_by").all()
    serializer_class = RelationshipSerializer
    filterset_class = RelationshipFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ["created_at", "updated_at", "relative_name"]
    ordering = ["-created_at"]
    search_fields = ["employee_code", "employee_name", "relative_name", "relation_type"]

    def get_queryset(self):
        """Filter to show only active relationships by default"""
        queryset = super().get_queryset()
        # Show only active relationships by default unless is_active filter is explicitly provided
        # Check if filterset will handle is_active (presence in query params)
        # If not present, apply default filter
        request = self.request
        if request and "is_active" not in request.query_params:
            queryset = queryset.filter(is_active=True)
        return queryset

    @transaction.atomic
    def perform_destroy(self, instance):
        """Soft delete by setting is_active to False"""
        instance.is_active = False
        instance.save()
