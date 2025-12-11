from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils.permissions import register_permission
from apps.payroll.api.serializers import KPIConfigSerializer
from apps.payroll.models import KPIConfig


class CurrentKPIConfigView(APIView):
    """API view to retrieve the current KPI configuration.

    This endpoint is read-only. Configuration editing is done through Django Admin.
    """

    permission_classes = [RoleBasedPermission]

    @extend_schema(
        summary="Get current KPI configuration",
        description="Retrieve the current active KPI configuration including grade thresholds, unit control rules, and ambiguous assignment policy",
        tags=["10.1: Payroll Configuration"],
        responses={200: KPIConfigSerializer},
        examples=[
            OpenApiExample(
                "Success - Current Config",
                description="Example response with current KPI configuration",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "version": 1,
                        "updated_at": "2025-12-10T10:00:00Z",
                        "created_at": "2025-12-10T10:00:00Z",
                        "config": {
                            "name": "Default KPI Config",
                            "description": "Standard grading scale and unit control",
                            "ambiguous_assignment": "manual",
                            "grade_thresholds": [
                                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                                {
                                    "min": 60,
                                    "max": 70,
                                    "possible_codes": ["C", "D"],
                                    "default_code": "C",
                                    "label": "Average or Poor",
                                },
                                {
                                    "min": 70,
                                    "max": 90,
                                    "possible_codes": ["B", "C"],
                                    "default_code": "B",
                                    "label": "Good or Average",
                                },
                                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
                            ],
                            "unit_control": {
                                "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None},
                                "B": {"max_pct_A": 0.10, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": 0.10},
                                "C": {"max_pct_A": 0.05, "max_pct_B": 0.20, "max_pct_C": 0.60, "min_pct_D": 0.15},
                                "D": {"max_pct_A": 0.05, "max_pct_B": 0.10, "max_pct_C": 0.65, "min_pct_D": 0.20},
                            },
                            "meta": {},
                        },
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - No Config Found",
                description="Example response when no configuration exists",
                value={"success": False, "data": None, "error": {"detail": "No KPI configuration found"}},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    @register_permission(
        "payroll.view_kpi_config",
        _("View KPI configuration"),
        "Payroll",
        "Configuration",
        _("Payroll View KPI Configuration"),
    )
    def get(self, request):
        """Get the current KPI configuration."""
        config = KPIConfig.objects.first()

        if not config:
            return Response({"detail": "No KPI configuration found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = KPIConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)
