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
    """ViewSet for Holiday model with nested compensatory workdays management."""

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

    @extend_schema(
        summary="List compensatory workdays for a holiday",
        description="Retrieve all compensatory workdays associated with a specific holiday",
        tags=["Holiday - Compensatory Workdays"],
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
                                "id": "223e4567-e89b-12d3-a456-426614174000",
                                "holiday": "123e4567-e89b-12d3-a456-426614174000",
                                "date": "2026-02-07",
                                "notes": "Make up day for holiday",
                                "status": "active",
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
    )
    @action(detail=True, methods=["get", "post"], url_path="compensatory-days")
    def compensatory_days(self, request, pk=None):
        """List or create compensatory workdays for a holiday."""
        holiday = self.get_object()

        if request.method == "GET":
            # List compensatory days for this holiday
            queryset = CompensatoryWorkday.objects.filter(holiday=holiday, deleted=False).order_by("date")

            # Apply filters if provided
            date_filter = request.query_params.get("date")
            if date_filter:
                queryset = queryset.filter(date=date_filter)

            status_filter = request.query_params.get("status")
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            # Paginate results
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = CompensatoryWorkdaySerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = CompensatoryWorkdaySerializer(queryset, many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            # Create compensatory day(s)
            # Support both single object and array for bulk create
            is_bulk = isinstance(request.data, list)
            data_list = request.data if is_bulk else [request.data]

            # Validate all items first
            serializers = []
            for data in data_list:
                # Set the holiday for each item
                item_data = data.copy() if isinstance(data, dict) else data
                item_data["holiday"] = holiday.id

                serializer = CompensatoryWorkdaySerializer(data=item_data, context={"request": request})
                serializer.is_valid(raise_exception=True)
                serializers.append(serializer)

            # Create all items atomically
            with transaction.atomic():
                created_items = []
                for ser in serializers:
                    created_items.append(
                        ser.save(
                            holiday=holiday,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    )

            # Return response
            result_serializer = CompensatoryWorkdaySerializer(created_items, many=True)
            if is_bulk:
                return Response(result_serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(result_serializer.data[0], status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Manage a specific compensatory workday",
        description="Get, update, or delete a specific compensatory workday",
        tags=["Holiday - Compensatory Workdays"],
    )
    @action(detail=True, methods=["get", "put", "patch", "delete"], url_path="compensatory-days/(?P<comp_id>[^/.]+)")
    def compensatory_day_detail(self, request, pk=None, comp_id=None):
        """Retrieve, update, or delete a specific compensatory workday."""
        holiday = self.get_object()
        try:
            comp_day = CompensatoryWorkday.objects.get(id=comp_id, holiday=holiday, deleted=False)
        except CompensatoryWorkday.DoesNotExist:
            return Response(
                {"error": _("Compensatory workday not found")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "GET":
            serializer = CompensatoryWorkdaySerializer(comp_day)
            return Response(serializer.data)

        elif request.method in ["PUT", "PATCH"]:
            partial = request.method == "PATCH"
            serializer = CompensatoryWorkdaySerializer(
                comp_day, data=request.data, partial=partial, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)
            return Response(serializer.data)

        elif request.method == "DELETE":
            comp_day.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Export compensatory workdays to XLSX",
        description="Export all compensatory workdays for this holiday to XLSX format",
        tags=["Holiday - Compensatory Workdays"],
    )
    @action(detail=True, methods=["get"], url_path="compensatory-days/export")
    def export_compensatory_days(self, request, pk=None):
        """Export compensatory workdays for this holiday to XLSX."""
        holiday = self.get_object()

        # Get filtered compensatory days
        queryset = CompensatoryWorkday.objects.filter(holiday=holiday, deleted=False).order_by("date")

        # Apply filters if provided
        date_filter = request.query_params.get("date")
        if date_filter:
            queryset = queryset.filter(date=date_filter)

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Build export schema
        schema = {
            "sheets": [
                {
                    "name": f"Compensatory Days - {holiday.name}",
                    "headers": ["Date", "Notes", "Status", "Created At", "Updated At"],
                    "data": [
                        {
                            "Date": comp_day.date.strftime("%Y-%m-%d"),
                            "Notes": comp_day.notes,
                            "Status": comp_day.get_status_display(),
                            "Created At": comp_day.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "Updated At": comp_day.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        for comp_day in queryset
                    ],
                }
            ]
        }

        # Use parent's export functionality
        return self._sync_export(schema, delivery=request.query_params.get("delivery", "link"))
