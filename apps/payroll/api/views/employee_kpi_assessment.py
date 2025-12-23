from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import EmployeeKPIAssessmentFilterSet
from apps.payroll.api.serializers import (
    EmployeeKPIAssessmentListSerializer,
    EmployeeKPIAssessmentSerializer,
    EmployeeKPIAssessmentUpdateSerializer,
    EmployeeKPIItemSerializer,
    EmployeeSelfAssessmentSerializer,
    EmployeeSelfAssessmentUpdateRequestSerializer,
    ManagerAssessmentSerializer,
    ManagerAssessmentUpdateRequestSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem
from apps.payroll.utils import recalculate_assessment_scores
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List employee KPI assessments",
        description="Retrieve a paginated list of employee KPI assessments with support for filtering",
        tags=["8.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Success - List of assessments",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "period": {"id": 3, "month": "12/2025", "finalized": False},
                                "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                                "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                                "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                                "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                                "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                                "kpi_config_snapshot": {},
                                "total_possible_score": "100.00",
                                "total_employee_score": "100.00",
                                "total_manager_score": "80.00",
                                "grade_manager": "B",
                                "grade_manager_overridden": None,
                                "plan_tasks": "Complete Q4 targets",
                                "extra_tasks": "Handle urgent client requests",
                                "proposal": "Suggest new workflow improvement",
                                "grade_hrm": "A",
                                "finalized": False,
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-01T00:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get employee KPI assessment details",
        description="Retrieve detailed information about a specific employee KPI assessment including all items",
        tags=["8.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Success - Assessment with items",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "period": {"id": 3, "month": "12/2025", "finalized": False},
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "kpi_config_snapshot": {},
                        "total_possible_score": "100.00",
                        "total_employee_score": "100.00",
                        "total_manager_score": "80.00",
                        "grade_manager": "B",
                        "grade_manager_overridden": None,
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent client requests",
                        "proposal": "Suggest new workflow improvement",
                        "grade_hrm": "A",
                        "finalized": False,
                        "department_assignment_source": None,
                        "created_by": 1,
                        "updated_by": None,
                        "created_at": "2025-12-01T00:00:00Z",
                        "updated_at": "2025-12-01T00:00:00Z",
                        "note": "",
                        "items": [
                            {
                                "id": 1,
                                "assessment": 1,
                                "criterion_id": 1,
                                "target": "sales",
                                "criterion": "Revenue Achievement",
                                "evaluation_type": "work_performance",
                                "description": "Monthly revenue target",
                                "component_total_score": "70.00",
                                "order": 1,
                                "employee_score": "90.00",
                                "manager_score": "85.00",
                                "note": "",
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-01T00:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Update employee KPI assessment",
        description="Update specific fields of an employee KPI assessment (HRM grade and note only)",
        tags=["8.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Request - Update HRM grade",
                value={"grade_hrm": "A", "note": "Exceptional performance this month"},
                request_only=True,
            )
        ],
    ),
)
class EmployeeKPIAssessmentViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for EmployeeKPIAssessment model.

    Provides CRUD operations and custom actions for:
    - Generating assessments
    - Updating item scores
    - Resyncing with current criteria
    - Finalizing assessments with unit control validation
    """

    queryset = EmployeeKPIAssessment.objects.select_related(
        "period",
        "employee",
        "department_assignment_source",
        "created_by",
        "updated_by",
    ).prefetch_related("items")
    filterset_class = EmployeeKPIAssessmentFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["employee__username", "employee__fullname", "employee__code"]
    ordering_fields = ["period__month", "employee__username", "grade_manager", "total_manager_score", "created_at"]
    ordering = ["-period__month", "-created_at"]
    http_method_names = ["get", "patch"]  # Only allow GET and PATCH

    # Permission registration attributes
    module = "Payroll"
    submodule = "KPI Management"
    permission_prefix = "employee_kpi_assessment"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return EmployeeKPIAssessmentListSerializer
        elif self.action in ["partial_update"]:
            return EmployeeKPIAssessmentUpdateSerializer
        return EmployeeKPIAssessmentSerializer

    def perform_update(self, serializer):
        """Set updated_by when updating."""
        serializer.save(updated_by=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="Get employee's current assessment",
        description="Retrieve the authenticated employee's current KPI assessment for the latest period",
        tags=["8.5: Employee Self-Assessment"],
        examples=[
            OpenApiExample(
                "Success - Current Assessment",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "period": {"id": 3, "month": "12/2025", "finalized": False},
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "total_possible_score": "100.00",
                        "grade_manager": "B",
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent requests",
                        "proposal": "Improve workflow",
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
                                "manager_score": None,
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
    retrieve=extend_schema(
        summary="Get specific assessment",
        description="Retrieve a specific assessment that belongs to the authenticated employee",
        tags=["8.5: Employee Self-Assessment"],
    ),
    partial_update=extend_schema(
        summary="Update self-assessment",
        description="""Batch update employee scores for items, plan_tasks, extra_tasks, and proposal.

        **Request Body Format:**
        - `plan_tasks` (string, optional): Planned tasks for the assessment period
        - `extra_tasks` (string, optional): Extra tasks handled during the period
        - `proposal` (string, optional): Employee's proposals or suggestions
        - `items` (array, optional): List of item updates with structure:
          - `item_id` (integer): ID of the KPI item to update
          - `score` (decimal): Employee score for that item

        **Example:**
        ```json
        {
            "plan_tasks": "Complete quarterly targets",
            "items": [
                {"item_id": 1, "score": "65.00"},
                {"item_id": 2, "score": "28.50"},
                {"item_id": 3, "score": "90.00"}
            ]
        }
        ```
        """,
        tags=["8.5: Employee Self-Assessment"],
        request=EmployeeSelfAssessmentUpdateRequestSerializer,
        examples=[
            OpenApiExample(
                "Update Request - Batch update items",
                value={
                    "plan_tasks": "Updated plan tasks",
                    "extra_tasks": "Handled additional tasks",
                    "proposal": "My improvement suggestions",
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
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "total_possible_score": "100.00",
                        "grade_manager": "B",
                        "plan_tasks": "Updated plan tasks",
                        "extra_tasks": "Handled additional tasks",
                        "proposal": "My improvement suggestions",
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
                                "employee_score": "65.00",
                                "manager_score": None,
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
                                "employee_score": "28.50",
                                "manager_score": None,
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
    permission_prefix = "employee_self_assessment"
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

    def perform_update(self, serializer):
        """Save the updated assessment and handle batch item updates using serializer validation."""
        assessment = self.get_object()

        # Create request serializer with assessment context for validation
        request_serializer = EmployeeSelfAssessmentUpdateRequestSerializer(
            data=self.request.data, context={"assessment": assessment}
        )
        request_serializer.is_valid(raise_exception=True)

        # Update assessment fields (plan_tasks, extra_tasks, proposal)
        assessment = serializer.save()

        # Update items using serializer method
        request_serializer.update_items(assessment, request_serializer.validated_data)

        # Refresh assessment to get updated items, then recalculate
        assessment.refresh_from_db()
        recalculate_assessment_scores(assessment)

    @extend_schema(
        summary="Get current unfinalized assessment",
        description="Get the latest unfinalized assessment for the authenticated employee",
        tags=["8.5: Employee Self-Assessment"],
        responses={200: EmployeeSelfAssessmentSerializer, 404: None},
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current_assessment(self, request):
        """Get current unfinalized assessment for the employee."""
        user = request.user

        # Get employee record
        try:
            from apps.hrm.models import Employee

            employee = Employee.objects.get(username=user.username)
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest unfinalized assessment
        assessment = (
            EmployeeKPIAssessment.objects.filter(employee=employee, finalized=False)
            .select_related("period", "employee")
            .prefetch_related("items")
            .order_by("-period__month")
            .first()
        )

        if not assessment:
            return Response(
                {"detail": "No current unfinalized assessment found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(assessment)
        return Response(serializer.data)

    @extend_schema(
        summary="Update employee score for an item",
        description="Update employee's self-score for a specific KPI item",
        tags=["8.5: Employee Self-Assessment"],
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
                                "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                                "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                                "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                                "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
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
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
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
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
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
    permission_prefix = "employee_manager_assessment"
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

    @extend_schema(
        summary="Get current unfinalized assessments for department employees",
        description="Get the latest unfinalized assessments for all employees in manager's department",
        tags=["8.7: Manager Assessment"],
        responses={200: ManagerAssessmentSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current_assessments(self, request):
        """Get current unfinalized assessments for department employees."""
        user = request.user

        # Get employee record for current user
        try:
            from apps.hrm.models import Employee

            employee = Employee.objects.get(username=user.username)
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest unfinalized assessments for all department employees
        assessments = (
            EmployeeKPIAssessment.objects.filter(manager=employee, finalized=False)
            .select_related("period", "employee", "manager")
            .prefetch_related("items")
            .order_by("-period__month")
        )

        # Group by employee and get only the latest for each
        from collections import OrderedDict

        latest_assessments = OrderedDict()
        for assessment in assessments:
            employee_id = assessment.employee.id
            if employee_id not in latest_assessments:
                latest_assessments[employee_id] = assessment

        serializer = self.get_serializer(list(latest_assessments.values()), many=True)
        return Response(serializer.data)
