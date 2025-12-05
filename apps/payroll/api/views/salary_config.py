from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payroll.api.serializers import SalaryConfigSerializer
from apps.payroll.models import SalaryConfig


class CurrentSalaryConfigView(APIView):
    """API view to retrieve the current salary configuration.

    This endpoint is read-only. Configuration editing is done through Django Admin.
    """

    @extend_schema(
        summary="Get current salary configuration",
        description="Retrieve the current active salary configuration including insurance rates, tax levels, KPI grades, and business progressive salary levels",
        tags=["Payroll"],
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
                            "kpi_salary": {"grades": {"A": 0.10, "B": 0.05, "C": 0.00, "D": -0.05}},
                            "business_progressive_salary": {
                                "levels": {
                                    "M0": "base_salary",
                                    "M1": 7000000,
                                    "M2": 9000000,
                                    "M3": 11000000,
                                    "M4": 13000000,
                                }
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
        """Get the current salary configuration."""
        config = SalaryConfig.objects.first()

        if not config:
            return Response({"detail": "No salary configuration found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SalaryConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)
