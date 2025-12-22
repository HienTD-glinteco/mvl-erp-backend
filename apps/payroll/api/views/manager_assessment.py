from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.payroll.api.serializers.employee_kpi_assessment import (
    ManagerAssessmentSerializer,
    ManagerAssessmentUpdateRequestSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment
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
                                "period": {"id": 3, "month": "12/2025", "finalized": False},
                                "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                                "total_possible_score": "100.00",
                                "total_employee_score": "88.50",
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
                        "period": {"id": 3, "month": "12/2025", "finalized": False},
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "total_possible_score": "100.00",
                        "total_employee_score": "88.50",
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
                                "assessment": 1,
                                "criterion_id": "KPI-001",
                                "target": None,
                                "criterion": "Revenue Achievement",
                                "sub_criterion": "Monthly Sales Target",
                                "evaluation_type": "quantitative",
                                "description": "Achieve monthly revenue target",
                                "component_total_score": "70.00",
                                "group_number": 1,
                                "order": 1,
                                "employee_score": "60.00",
                                "manager_score": "58.00",
                                "note": None,
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-01T00:00:00Z",
                            },
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
        description="""Batch update manager scores for items and manager_assessment field.

        **Request Body Format:**
        - `manager_assessment` (string, optional): Manager's assessment comments and feedback
        - `items` (array, optional): List of item updates with structure:
          - `item_id` (integer): ID of the KPI item to update
          - `score` (decimal): Manager score for that item

        **Example:**
        ```json
        {
            "manager_assessment": "Good performance, needs improvement in communication",
            "items": [
                {"item_id": 1, "score": "65.00"},
                {"item_id": 2, "score": "28.50"},
                {"item_id": 3, "score": "90.00"}
            ]
        }
        ```
        """,
        tags=["8.7: Manager Assessment"],
        request=ManagerAssessmentUpdateRequestSerializer,
        examples=[
            OpenApiExample(
                "Update Request - Batch update",
                value={
                    "manager_assessment": "Good performance overall, needs improvement in communication",
                    "items": [
                        {"item_id": 1, "score": "65.00"},
                        {"item_id": 2, "score": "28.50"},
                    ],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "period": {"id": 3, "month": "12/2025", "finalized": False},
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "total_possible_score": "100.00",
                        "total_employee_score": "93.50",
                        "total_manager_score": "93.50",
                        "grade_manager": "A",
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent requests",
                        "proposal": "Improve workflow",
                        "manager_assessment": "Good performance overall, needs improvement in communication",
                        "finalized": False,
                        "items": [
                            {
                                "id": 1,
                                "assessment": 1,
                                "criterion_id": "KPI-001",
                                "target": None,
                                "criterion": "Revenue Achievement",
                                "sub_criterion": "Monthly Sales Target",
                                "evaluation_type": "quantitative",
                                "description": "Achieve monthly revenue target",
                                "component_total_score": "70.00",
                                "group_number": 1,
                                "order": 1,
                                "employee_score": "60.00",
                                "manager_score": "65.00",
                                "note": None,
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-22T05:00:00Z",
                            },
                            {
                                "id": 2,
                                "assessment": 1,
                                "criterion_id": "KPI-002",
                                "target": None,
                                "criterion": "Customer Satisfaction",
                                "sub_criterion": "Survey Rating",
                                "evaluation_type": "quantitative",
                                "description": "Maintain high customer satisfaction",
                                "component_total_score": "30.00",
                                "group_number": 1,
                                "order": 2,
                                "employee_score": "30.00",
                                "manager_score": "28.50",
                                "note": None,
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-22T05:00:00Z",
                            },
                        ],
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
        """Save the updated assessment and handle batch item updates using serializer validation."""
        assessment = self.get_object()

        # Create request serializer with assessment context for validation
        request_serializer = ManagerAssessmentUpdateRequestSerializer(
            data=self.request.data, context={"assessment": assessment}
        )
        request_serializer.is_valid(raise_exception=True)

        # Update assessment fields (manager_assessment)
        assessment = serializer.save()

        # Update items using serializer method
        request_serializer.update_items(assessment, request_serializer.validated_data)

        # Refresh assessment to get updated items, then recalculate
        assessment.refresh_from_db()
        recalculate_assessment_scores(assessment)
