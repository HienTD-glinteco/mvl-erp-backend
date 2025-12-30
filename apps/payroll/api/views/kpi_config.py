from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.core.api.permissions import RoleBasedPermission
from apps.payroll.api.serializers import KPIConfigSerializer
from apps.payroll.models import KPIConfig
from libs.drf.base_api_view import PermissionedAPIView


class CurrentKPIConfigView(PermissionedAPIView):
    """API view to retrieve the current KPI configuration.

    This endpoint is read-only. Configuration editing is done through Django Admin.
    """

    permission_classes = [RoleBasedPermission]
    permission_prefix = "payroll"
    module = _("Payroll")
    submodule = _("KPI Configuration")
    permission_action_map = {"get": "kpi_config"}
    STANDARD_ACTIONS = {}
    PERMISSION_REGISTERED_ACTIONS = {
        "kpi_config": {
            "name_template": _("View KPI configuration"),
            "description_template": _("View KPI configuration"),
        }
    }

    @extend_schema(
        summary="Get current KPI configuration",
        description="Retrieve the current active KPI configuration including grade thresholds, unit control rules, and ambiguous assignment policy",
        tags=["8.1: KPI Configuration"],
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
                                "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"target": 0.50}, "D": {"min": 0}},
                                "B": {
                                    "A": {"max": 0.10},
                                    "B": {"max": 0.30},
                                    "C": {"target": 0.50},
                                    "D": {"min": 0.10},
                                },
                                "C": {
                                    "A": {"max": 0.05},
                                    "B": {"max": 0.20},
                                    "C": {"target": 0.60},
                                    "D": {"min": 0.15},
                                },
                                "D": {
                                    "A": {"max": 0.05},
                                    "B": {"max": 0.10},
                                    "C": {"target": 0.65},
                                    "D": {"min": 0.20},
                                },
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
    def get(self, request):
        return self.kpi_config(request)

    def kpi_config(self, request):
        """Get the current KPI configuration."""
        config = KPIConfig.objects.first()

        if not config:
            return Response({"detail": "No KPI configuration found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = KPIConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)
