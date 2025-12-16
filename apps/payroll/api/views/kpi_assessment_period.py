from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets

from apps.payroll.api.serializers import (
    KPIAssessmentPeriodListSerializer,
    KPIAssessmentPeriodSerializer,
)
from apps.payroll.models import KPIAssessmentPeriod
from libs.drf.filtersets.search import PhraseSearchFilter


class KPIAssessmentPeriodViewSet(viewsets.ModelViewSet):
    """ViewSet for KPIAssessmentPeriod model.

    Provides CRUD operations for KPI assessment periods.
    """

    queryset = KPIAssessmentPeriod.objects.all().order_by("-month")
    serializer_class = KPIAssessmentPeriodSerializer
    filter_backends = [PhraseSearchFilter]
    search_fields = ["note"]

    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == "list":
            return KPIAssessmentPeriodListSerializer
        return KPIAssessmentPeriodSerializer

    @extend_schema(
        summary="List KPI assessment periods",
        description="Retrieve a list of all KPI assessment periods with counts",
        tags=["KPI Assessment Periods"],
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
                                "month": "2025-12-01",
                                "finalized": False,
                                "employee_count": 50,
                                "department_count": 10,
                                "note": "",
                                "created_at": "2025-11-20T10:00:00Z",
                                "updated_at": "2025-11-20T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        """List all KPI assessment periods."""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Get KPI assessment period details",
        description="Retrieve details of a specific KPI assessment period",
        tags=["KPI Assessment Periods"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "month": "2025-12-01",
                        "kpi_config_snapshot": {
                            "name": "2025 KPI Config",
                            "grade_thresholds": [],
                            "unit_control": {},
                        },
                        "finalized": False,
                        "created_by": None,
                        "updated_by": None,
                        "note": "",
                        "created_at": "2025-11-20T10:00:00Z",
                        "updated_at": "2025-11-20T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a KPI assessment period."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Create KPI assessment period",
        description="Create a new KPI assessment period",
        tags=["KPI Assessment Periods"],
    )
    def create(self, request, *args, **kwargs):
        """Create a KPI assessment period."""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Update KPI assessment period",
        description="Update a KPI assessment period",
        tags=["KPI Assessment Periods"],
    )
    def update(self, request, *args, **kwargs):
        """Update a KPI assessment period."""
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update KPI assessment period",
        description="Partially update a KPI assessment period",
        tags=["KPI Assessment Periods"],
    )
    def partial_update(self, request, *args, **kwargs):
        """Partially update a KPI assessment period."""
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete KPI assessment period",
        description="Delete a KPI assessment period (use with caution)",
        tags=["KPI Assessment Periods"],
    )
    def destroy(self, request, *args, **kwargs):
        """Delete a KPI assessment period."""
        return super().destroy(request, *args, **kwargs)
