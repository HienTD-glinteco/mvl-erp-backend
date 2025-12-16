"""API views for employee self-assessment."""

from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.payroll.api.serializers.employee_kpi_assessment import (
    EmployeeKPIItemSerializer,
    EmployeeSelfAssessmentSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem
from apps.payroll.utils import recalculate_assessment_scores
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="Get employee's current assessment",
        description="Retrieve the authenticated employee's current KPI assessment for the latest period",
        tags=["10.5: Employee Self-Assessment"],
        examples=[
            OpenApiExample(
                "Success - Current Assessment",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_username": "john.doe",
                        "employee_fullname": "John Doe",
                        "month": "2025-12-01",
                        "total_possible_score": "100.00",
                        "grade_manager": "B",
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent requests",
                        "proposal": "Improve workflow",
                        "finalized": False,
                        "items": [
                            {
                                "id": 1,
                                "criterion": "Revenue Achievement",
                                "component_total_score": "70.00",
                                "employee_score": "60.00",
                                "manager_score": None,
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get specific assessment",
        description="Retrieve a specific assessment that belongs to the authenticated employee",
        tags=["10.5: Employee Self-Assessment"],
    ),
    partial_update=extend_schema(
        summary="Update self-assessment",
        description="Update employee scores, plan_tasks, extra_tasks, and proposal",
        tags=["10.5: Employee Self-Assessment"],
        examples=[
            OpenApiExample(
                "Update Request",
                value={
                    "plan_tasks": "Updated plan tasks",
                    "extra_tasks": "Handled additional tasks",
                    "proposal": "My improvement suggestions",
                },
                request_only=True,
            )
        ],
    ),
)
class EmployeeSelfAssessmentViewSet(BaseModelViewSet):
    """ViewSet for employee self-assessment.

    Allows employees to:
    - View their current and past assessments
    - Update their own scores for assessment items
    - Update plan_tasks, extra_tasks, and proposal fields
    """

    serializer_class = EmployeeSelfAssessmentSerializer
    http_method_names = ["get", "patch"]  # Only allow GET and PATCH

    # Permission attributes
    module = "Payroll"
    submodule = "Employee Self-Assessment"
    operation = "Self-Assessment"

    def get_queryset(self):
        """Filter assessments to only show current employee's assessments."""
        user = self.request.user

        # Get employee record
        try:
            from apps.hrm.models import Employee

            employee = Employee.objects.get(username=user.username)
        except Employee.DoesNotExist:
            return EmployeeKPIAssessment.objects.none()

        return (
            EmployeeKPIAssessment.objects.filter(employee=employee)
            .select_related(
                "period",
                "employee",
            )
            .prefetch_related("items")
            .order_by("-period__month")
        )

    def list(self, request, *args, **kwargs):
        """Return only the latest assessment."""
        queryset = self.get_queryset()
        latest = queryset.first()

        if not latest:
            return Response(
                {"detail": "No assessment found for current period"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(latest)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """Prevent full update, only allow partial update."""
        return Response(
            {"detail": "Only partial updates are allowed. Use PATCH method."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_update(self, serializer):
        """Save the updated assessment."""
        serializer.save()

    @extend_schema(
        summary="Update employee score for an item",
        description="Update employee's self-score for a specific KPI item",
        tags=["10.5: Employee Self-Assessment"],
        request=EmployeeKPIItemSerializer,
        responses={200: EmployeeKPIItemSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="items/(?P<item_id>[^/.]+)/score")
    def update_item_score(self, request, pk=None, item_id=None):
        """Update employee score for a specific item."""
        assessment = self.get_object()

        if assessment.finalized:
            return Response(
                {"detail": "Cannot update finalized assessment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            item = assessment.items.get(id=item_id)
        except EmployeeKPIItem.DoesNotExist:
            return Response(
                {"detail": "Item not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only allow updating employee_score
        employee_score = request.data.get("employee_score")
        if employee_score is not None:
            item.employee_score = employee_score
            item.save()

            # Recalculate totals
            recalculate_assessment_scores(assessment)

        serializer = EmployeeKPIItemSerializer(item)
        return Response(serializer.data)
