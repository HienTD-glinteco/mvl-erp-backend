from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.payroll.api.serializers.employee_kpi_assessment import (
    ManagerAssessmentSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem
from apps.payroll.utils import recalculate_assessment_scores
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List manager's employee assessments",
        description="Retrieve a paginated list of employee KPI assessments for employees under the manager",
        tags=["8.7: Manager Assessment"],
        examples=[
            OpenApiExample(
                "Success - List of assessments",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "employee": 1,
                                "employee_username": "john.doe",
                                "employee_fullname": "John Doe",
                                "month": "2025-12-01",
                                "total_possible_score": "100.00",
                                "total_manager_score": "80.00",
                                "grade_manager": "B",
                                "plan_tasks": "Complete Q4 targets",
                                "extra_tasks": "Handle urgent requests",
                                "proposal": "Improve workflow",
                                "manager_assessment": "",
                                "finalized": False,
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
        summary="Get specific employee assessment for manager",
        description="Retrieve detailed assessment information for an employee that the manager is responsible for",
        tags=["8.7: Manager Assessment"],
        examples=[
            OpenApiExample(
                "Success - Assessment with items",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_username": "john.doe",
                        "employee_fullname": "John Doe",
                        "month": "2025-12-01",
                        "total_possible_score": "100.00",
                        "total_manager_score": "80.00",
                        "grade_manager": "B",
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent requests",
                        "proposal": "Improve workflow",
                        "manager_assessment": "",
                        "finalized": False,
                        "items": [
                            {
                                "id": 1,
                                "criterion": "Revenue Achievement",
                                "component_total_score": "70.00",
                                "employee_score": "60.00",
                                "manager_score": "58.00",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Update manager assessment",
        description="Batch update manager scores for items and manager_assessment field",
        tags=["8.7: Manager Assessment"],
        examples=[
            OpenApiExample(
                "Update Request - Batch update",
                value={
                    "manager_assessment": "Good performance overall, needs improvement in communication",
                    "items": {"1": "65.00", "2": "28.50"},
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_username": "john.doe",
                        "employee_fullname": "John Doe",
                        "month": "2025-12-01",
                        "total_possible_score": "100.00",
                        "total_manager_score": "93.50",
                        "grade_manager": "A",
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent requests",
                        "proposal": "Improve workflow",
                        "manager_assessment": "Good performance overall, needs improvement in communication",
                        "finalized": False,
                        "items": [],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
)
class ManagerAssessmentViewSet(BaseModelViewSet):
    """ViewSet for manager assessment of employees.

    Allows managers to:
    - View assessments for their direct reports (employees in their department)
    - Update manager scores for assessment items
    - Update manager_assessment field with feedback
    """

    serializer_class = ManagerAssessmentSerializer
    http_method_names = ["get", "patch"]
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["employee__username", "employee__fullname", "employee__code"]
    ordering_fields = ["period__month", "employee__username", "grade_manager", "total_manager_score"]
    ordering = ["-period__month"]

    # Permission attributes
    module = "Payroll"
    submodule = "Manager Assessment"
    operation = "Manager-Assessment"

    def get_queryset(self):
        """Filter assessments to only show assessments where current user is the manager."""
        user = self.request.user

        # Get employee record for current user
        try:
            from apps.hrm.models import Employee

            employee = Employee.objects.get(username=user.username)
        except Employee.DoesNotExist:
            return EmployeeKPIAssessment.objects.none()

        # Return assessments where this employee is the manager
        return (
            EmployeeKPIAssessment.objects.filter(manager=employee)
            .select_related(
                "period",
                "employee",
                "manager",
            )
            .prefetch_related("items")
            .order_by("-period__month")
        )

    def perform_update(self, serializer):
        """Save the updated assessment and handle batch item updates."""
        items_data = self.request.data.get("items", {})

        # Check finalized status before any updates
        assessment = self.get_object()
        if assessment.finalized:
            from django.utils.translation import gettext as _
            from rest_framework.exceptions import ValidationError

            raise ValidationError(_("Cannot update finalized assessment"))

        # Update assessment fields (manager_assessment)
        assessment = serializer.save()

        # Batch update items if provided
        if items_data:
            for item_id, score in items_data.items():
                try:
                    item = assessment.items.get(id=int(item_id))
                    item.manager_score = score
                    item.save()
                except (EmployeeKPIItem.DoesNotExist, ValueError):
                    continue

            # Refresh assessment to get updated items, then recalculate
            assessment.refresh_from_db()

        # Always recalculate totals after any update
        recalculate_assessment_scores(assessment)
