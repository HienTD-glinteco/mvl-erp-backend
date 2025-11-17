from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import HolidayFilterSet
from apps.hrm.api.serializers import CompensatoryWorkdaySerializer, HolidayDetailSerializer, HolidaySerializer
from apps.hrm.models import CompensatoryWorkday, Holiday
from libs import BaseModelViewSet
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all holidays",
        description="Retrieve a paginated list of all holidays with support for filtering by name, date range, and status",
        tags=["Holiday"],
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
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "New Year 2026",
                                "start_date": "2026-01-01",
                                "end_date": "2026-01-01",
                                "notes": "Public holiday",
                                "status": "active",
                                "compensatory_days_count": 1,
                                "created_at": "2025-11-14T08:00:00Z",
                                "updated_at": "2025-11-14T08:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create a new holiday",
        description="Create a new holiday. Optionally include compensatory_dates array to create compensatory workdays atomically.",
        tags=["Holiday"],
        examples=[
            OpenApiExample(
                "Request with compensatory dates",
                value={
                    "name": "Lunar New Year 2026",
                    "start_date": "2026-02-05",
                    "end_date": "2026-02-06",
                    "notes": "Vietnamese New Year holiday",
                    "status": "active",
                    "compensatory_dates": ["2026-02-07", "2026-02-08"],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Lunar New Year 2026",
                        "start_date": "2026-02-05",
                        "end_date": "2026-02-06",
                        "notes": "Vietnamese New Year holiday",
                        "status": "active",
                        "compensatory_days_count": 2,
                        "created_at": "2025-11-14T08:00:00Z",
                        "updated_at": "2025-11-14T08:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get holiday details",
        description="Retrieve detailed information about a specific holiday",
        tags=["Holiday"],
    ),
    update=extend_schema(
        summary="Update holiday",
        description="Update holiday information",
        tags=["Holiday"],
    ),
    partial_update=extend_schema(
        summary="Partially update holiday",
        description="Partially update holiday information",
        tags=["Holiday"],
    ),
    destroy=extend_schema(
        summary="Delete holiday",
        description="Soft delete a holiday from the system",
        tags=["Holiday"],
    ),
)
class HolidayViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Holiday model."""

    queryset = Holiday.objects.filter(deleted=False).all()
    serializer_class = HolidaySerializer
    filterset_class = HolidayFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "start_date", "end_date", "created_at"]
    ordering = ["-start_date"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Holiday Management"
    permission_prefix = "holiday"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "retrieve":
            return HolidayDetailSerializer
        return HolidaySerializer

    def perform_create(self, serializer):
        """Set created_by and updated_by when creating a holiday."""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by when updating a holiday."""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete the holiday."""
        instance.delete()
