from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.core.api.permissions import RoleBasedPermission
from apps.payroll.api.serializers import SalaryConfigSerializer
from apps.payroll.models import SalaryConfig
from libs.drf.base_api_view import PermissionedAPIView


class CurrentSalaryConfigView(PermissionedAPIView):
    """API view to retrieve the current salary configuration.

    This endpoint is read-only. Configuration editing is done through Django Admin.
    """

    permission_classes = [RoleBasedPermission]
    permission_prefix = "payroll"
    module = _("Payroll")
    submodule = _("Configuration")
    permission_action_map = {"get": "view_salary_config"}
    STANDARD_ACTIONS = {}
    PERMISSION_REGISTERED_ACTIONS = {
        "view_salary_config": {
            "name_template": _("View salary configuration"),
            "description_template": _("View salary configuration"),
        }
    }

    @extend_schema(
        summary="Get current salary configuration",
        description="Retrieve the current active salary configuration including insurance rates, tax levels, KPI grades, and business progressive salary levels",
        tags=["10.1: Payroll Configuration"],
        responses={200: SalaryConfigSerializer},
        examples=[
            OpenApiExample(
                "Success - Current Config",
                description="Example response with current salary configuration",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "version": 1,
                        "updated_at": "2025-12-04T10:00:00Z",
                        "created_at": "2025-12-04T10:00:00Z",
                        "config": {
                            "insurance_contributions": {
                                "social_insurance": {
                                    "employee_rate": 0.08,
                                    "employer_rate": 0.17,
                                    "salary_ceiling": 46800000,
                                },
                                "health_insurance": {
                                    "employee_rate": 0.015,
                                    "employer_rate": 0.03,
                                    "salary_ceiling": 46800000,
                                },
                                "unemployment_insurance": {
                                    "employee_rate": 0.01,
                                    "employer_rate": 0.01,
                                    "salary_ceiling": 46800000,
                                },
                                "union_fee": {
                                    "employee_rate": 0.01,
                                    "employer_rate": 0.01,
                                    "salary_ceiling": 46800000,
                                },
                                "accident_occupational_insurance": {
                                    "employee_rate": 0.0,
                                    "employer_rate": 0.005,
                                    "salary_ceiling": 46800000,
                                },
                            },
                            "personal_income_tax": {
                                "standard_deduction": 11000000,
                                "dependent_deduction": 4400000,
                                "progressive_levels": [
                                    {"up_to": 5000000, "rate": 0.05},
                                    {"up_to": 10000000, "rate": 0.10},
                                    {"up_to": 18000000, "rate": 0.15},
                                    {"up_to": 32000000, "rate": 0.20},
                                    {"up_to": 52000000, "rate": 0.25},
                                    {"up_to": 80000000, "rate": 0.30},
                                    {"up_to": None, "rate": 0.35},
                                ],
                            },
                            "kpi_salary": {
                                "apply_on": "base_salary",
                                "tiers": [
                                    {"code": "A", "percentage": 0.10, "description": "Excellent"},
                                    {"code": "B", "percentage": 0.05, "description": "Good"},
                                    {"code": "C", "percentage": 0.00, "description": "Average"},
                                    {"code": "D", "percentage": -0.05, "description": "Below Average"},
                                ],
                            },
                            "business_progressive_salary": {
                                "apply_on": "base_salary",
                                "tiers": [
                                    {"code": "M0", "amount": 0, "criteria": []},
                                    {
                                        "code": "M1",
                                        "amount": 7000000,
                                        "criteria": [
                                            {"name": "transaction_count", "min": 50},
                                            {"name": "revenue", "min": 100000000},
                                        ],
                                    },
                                    {
                                        "code": "M2",
                                        "amount": 9000000,
                                        "criteria": [
                                            {"name": "transaction_count", "min": 80},
                                            {"name": "revenue", "min": 150000000},
                                        ],
                                    },
                                ],
                            },
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
                value={"success": False, "data": None, "error": {"detail": "No salary configuration found"}},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def get(self, request):
        return self.view_salary_config(request)

    def view_salary_config(self, request):
        """Get the current salary configuration."""
        config = SalaryConfig.objects.first()

        if not config:
            return Response({"detail": "No salary configuration found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SalaryConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)
