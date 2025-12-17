from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import HolidayFilterSet
from apps.hrm.api.serializers import (
    CompensatoryWorkdaySerializer,
    HolidayDetailSerializer,
    HolidayExportXLSXSerializer,
    HolidaySerializer,
)
from apps.hrm.models import CompensatoryWorkday, Holiday
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all holidays",
        description="Retrieve a paginated list of all holidays with support for filtering by name, date range, and status",
        tags=["6.5: Holiday - Compensatory Workdays"],
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
        tags=["6.5: Holiday - Compensatory Workdays"],
        examples=[
            OpenApiExample(
                "Request with compensatory dates",
                value={
                    "name": "Lunar New Year 2026",
                    "start_date": "2026-02-05",
                    "end_date": "2026-02-06",
                    "notes": "Vietnamese New Year holiday",
                    "status": "active",
                    "compensatory_dates": [
                        {"date": "2026-02-07", "session": "afternoon", "notes": "notes"},
                        {"date": "2026-02-08", "session": "full_day", "notes": "notes"},
                    ],
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
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    update=extend_schema(
        summary="Update holiday",
        description="Update holiday information",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    partial_update=extend_schema(
        summary="Partially update holiday",
        description="Partially update holiday information",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    destroy=extend_schema(
        summary="Delete holiday",
        description="Soft delete a holiday from the system",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    export=extend_schema(
        description="Export list Holidays",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
)
class HolidayViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Holiday model."""

    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    filterset_class = HolidayFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "start_date", "end_date", "created_at"]
    ordering = ["-start_date"]

    # Permission registration attributes
    module = "HRM"
    submodule = _("Holiday Management")
    permission_prefix = "holiday"

    xlsx_template_name = "apps/hrm/fixtures/export_templates/holiday_export_template.xlsx"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "retrieve":
            return HolidayDetailSerializer
        if self.action == "export":
            return HolidayExportXLSXSerializer
        return HolidaySerializer

    def get_export_data(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        headers = [str(field.label) for field in serializer.child.fields.values()]
        data = serializer.data
        field_names = list(serializer.child.fields.keys())
        if self.xlsx_template_name:
            headers = [_(self.xlsx_template_index_column_key), *headers]
            field_names = [self.xlsx_template_index_column_key, *field_names]
            for index, row in enumerate(data, start=1):
                row.update({self.xlsx_template_index_column_key: index})

        data = {
            "sheets": [
                {
                    "name": str(Holiday._meta.verbose_name),
                    "headers": headers,
                    "field_names": field_names,
                    "data": data,
                }
            ]
        }
        return data


@extend_schema_view(
    list=extend_schema(
        summary="List compensatory workdays for a holiday",
        description="Retrieve all compensatory workdays associated with a specific holiday",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    create=extend_schema(
        summary="Create compensatory workday",
        description="Create a single compensatory workday for a holiday",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    retrieve=extend_schema(
        summary="Get compensatory workday details",
        description="Retrieve details of a specific compensatory workday",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    update=extend_schema(
        summary="Update compensatory workday",
        description="Update a compensatory workday",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    partial_update=extend_schema(
        summary="Partially update compensatory workday",
        description="Partially update a compensatory workday",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
    destroy=extend_schema(
        summary="Delete compensatory workday",
        description="Soft delete a compensatory workday",
        tags=["6.5: Holiday - Compensatory Workdays"],
    ),
)
class CompensatoryWorkdayViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for CompensatoryWorkday model (nested under Holiday)."""

    serializer_class = CompensatoryWorkdaySerializer

    # Permission registration attributes
    module = _("HRM")
    submodule = _("Holiday Management")
    permission_prefix = "holiday"  # Use same permission as holiday since it's nested

    def get_queryset(self):
        """Get queryset filtered by holiday from URL."""
        holiday_id = self.kwargs.get("holiday_pk")
        return CompensatoryWorkday.objects.filter(holiday_id=holiday_id).order_by("date")

    def get_holiday(self):
        """Get the parent holiday from URL kwargs."""
        holiday_id = self.kwargs.get("holiday_pk")
        try:
            return Holiday.objects.get(id=holiday_id)
        except Holiday.DoesNotExist:
            return None

    def list(self, request, *args, **kwargs):
        """List compensatory days with optional filtering."""
        queryset = self.get_queryset()

        # Apply filters if provided
        date_filter = request.query_params.get("date")
        if date_filter:
            queryset = queryset.filter(date=date_filter)

        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create a single compensatory day."""
        holiday = self.get_holiday()
        if not holiday:
            return Response({"error": _("Holiday not found")}, status=status.HTTP_404_NOT_FOUND)

        # Set the holiday in the serializer context for validation
        serializer = self.get_serializer(
            data=request.data, context={**self.get_serializer_context(), "holiday": holiday}
        )
        serializer.is_valid(raise_exception=True)

        # Create the item
        serializer.save(
            holiday=holiday,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
