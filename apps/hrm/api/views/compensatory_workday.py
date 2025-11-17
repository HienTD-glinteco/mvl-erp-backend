from django.db import transaction
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.serializers import CompensatoryWorkdaySerializer
from apps.hrm.models import CompensatoryWorkday
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List compensatory workdays for a holiday",
        description="Retrieve all compensatory workdays associated with a specific holiday",
        tags=["Holiday - Compensatory Workdays"],
    ),
    create=extend_schema(
        summary="Create compensatory workday(s)",
        description="Create one or more compensatory workdays for a holiday. Supports bulk creation.",
        tags=["Holiday - Compensatory Workdays"],
    ),
    retrieve=extend_schema(
        summary="Get compensatory workday details",
        description="Retrieve details of a specific compensatory workday",
        tags=["Holiday - Compensatory Workdays"],
    ),
    update=extend_schema(
        summary="Update compensatory workday",
        description="Update a compensatory workday",
        tags=["Holiday - Compensatory Workdays"],
    ),
    partial_update=extend_schema(
        summary="Partially update compensatory workday",
        description="Partially update a compensatory workday",
        tags=["Holiday - Compensatory Workdays"],
    ),
    destroy=extend_schema(
        summary="Delete compensatory workday",
        description="Soft delete a compensatory workday",
        tags=["Holiday - Compensatory Workdays"],
    ),
)
class CompensatoryWorkdayViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for CompensatoryWorkday model (nested under Holiday)."""

    serializer_class = CompensatoryWorkdaySerializer

    # Permission registration attributes
    module = "HRM"
    submodule = "Holiday Management"
    permission_prefix = "holiday"  # Use same permission as holiday since it's nested

    def get_queryset(self):
        """Get queryset filtered by holiday from URL."""
        holiday_id = self.kwargs.get("holiday_pk")
        return CompensatoryWorkday.objects.filter(
            holiday_id=holiday_id,
            deleted=False
        ).order_by("date")

    def get_holiday(self):
        """Get the parent holiday from URL kwargs."""
        from apps.hrm.models import Holiday
        holiday_id = self.kwargs.get("holiday_pk")
        try:
            return Holiday.objects.get(id=holiday_id, deleted=False)
        except Holiday.DoesNotExist:
            return None

    def list(self, request, *args, **kwargs):
        """List compensatory days with optional filtering."""
        queryset = self.get_queryset()
        
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
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create compensatory day(s) - supports both single and bulk creation."""
        holiday = self.get_holiday()
        if not holiday:
            return Response(
                {"error": _("Holiday not found")},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Support both single object and array for bulk create
        is_bulk = isinstance(request.data, list)
        data_list = request.data if is_bulk else [request.data]
        
        # Validate all items first
        serializers = []
        for data in data_list:
            # Set the holiday for each item
            item_data = data.copy() if isinstance(data, dict) else data
            item_data["holiday"] = holiday.id
            
            serializer = self.get_serializer(data=item_data)
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
        result_serializer = self.get_serializer(created_items, many=True)
        if is_bulk:
            return Response(result_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(result_serializer.data[0], status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Set updated_by when updating a compensatory workday."""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Soft delete the compensatory workday."""
        instance.delete()
