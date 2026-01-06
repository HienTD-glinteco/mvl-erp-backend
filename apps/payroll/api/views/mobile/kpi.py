from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.payroll.api.filtersets import ManagerAssessmentFilterSet
from apps.payroll.api.serializers import (
    EmployeeSelfAssessmentSerializer,
    EmployeeSelfAssessmentUpdateRequestSerializer,
    ManagerAssessmentSerializer,
    ManagerAssessmentUpdateRequestSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment
from apps.payroll.utils import recalculate_assessment_scores
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List my KPI assessments",
        description="Retrieve all KPI assessments for the current user",
        tags=["8.5: My KPI"],
        examples=[
            OpenApiExample(
                "Success",
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
                                "total_possible_score": "100.00",
                                "total_employee_score": "90.00",
                                "total_manager_score": "85.00",
                                "grade_manager": "B",
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
        summary="Get my KPI assessment details",
        description="Retrieve detailed information for a specific KPI assessment",
        tags=["8.5: My KPI"],
    ),
    partial_update=extend_schema(
        summary="Update my self-assessment",
        description="Update employee scores, plan tasks, extra tasks, and proposals",
        tags=["8.5: My KPI"],
        request=EmployeeSelfAssessmentUpdateRequestSerializer,
    ),
)
class MyKPIAssessmentViewSet(BaseModelViewSet):
    """Mobile ViewSet for employee self-assessment."""

    queryset = EmployeeKPIAssessment.objects.none()
    serializer_class = EmployeeSelfAssessmentSerializer
    http_method_names = ["get", "patch"]

    module = _("Payroll - Mobile")
    submodule = _("My KPI")
    permission_prefix = "my_kpi_assessment"
    PERMISSION_REGISTERED_ACTIONS = {
        "current": {
            "name_template": _("View my KPI assessments"),
            "description_template": _("View KPI assessments for myself"),
        },
    }

    def get_queryset(self):
        """Filter to current user's assessments."""
        if getattr(self, "swagger_fake_view", False):
            return EmployeeKPIAssessment.objects.none()
        try:
            employee = self.request.user.employee
        except AttributeError:
            return EmployeeKPIAssessment.objects.none()

        return (
            EmployeeKPIAssessment.objects.filter(employee=employee)
            .select_related("period", "employee")
            .prefetch_related("items")
            .order_by("-period__month")
        )

    def perform_update(self, serializer):
        """Save the updated assessment and handle batch item updates."""
        assessment = self.get_object()

        request_serializer = EmployeeSelfAssessmentUpdateRequestSerializer(
            data=self.request.data, context={"assessment": assessment}
        )
        request_serializer.is_valid(raise_exception=True)

        assessment = serializer.save()
        request_serializer.update_items(assessment, request_serializer.validated_data)

        assessment.refresh_from_db()
        recalculate_assessment_scores(assessment)

    @extend_schema(
        summary="Get current KPI assessment",
        description="Get the latest unfinalized KPI assessment for the current user",
        tags=["8.5: My KPI"],
        responses={200: EmployeeSelfAssessmentSerializer, 404: None},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "period": {"id": 3, "month": "12/2025", "finalized": False},
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "total_possible_score": "100.00",
                        "total_employee_score": "90.00",
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent requests",
                        "proposal": "Improve workflow",
                        "items": [],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """Get current unfinalized assessment for the employee."""
        try:
            employee = request.user.employee
        except AttributeError:
            return Response(
                {"success": False, "data": None, "error": {"detail": "Employee record not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        assessment = (
            EmployeeKPIAssessment.objects.filter(employee=employee, finalized=False)
            .select_related("period", "employee")
            .prefetch_related("items")
            .order_by("-period__month")
            .first()
        )

        if not assessment:
            return Response(
                {"success": False, "data": None, "error": {"detail": "No current unfinalized assessment found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(assessment)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List team KPI assessments",
        description="Retrieve KPI assessments for team members managed by the current user",
        tags=["8.7: Team KPI"],
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
                                "period": {"id": 3, "month": "12/2025", "finalized": False},
                                "employee": {"id": 2, "code": "EMP002", "fullname": "Jane Smith"},
                                "total_possible_score": "100.00",
                                "total_employee_score": "88.00",
                                "total_manager_score": "82.00",
                                "grade_manager": "B",
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
        summary="Get team member KPI assessment details",
        description="Retrieve detailed KPI assessment for a team member",
        tags=["8.7: Team KPI"],
    ),
    partial_update=extend_schema(
        summary="Update team member assessment",
        description="Update manager scores and feedback for team member assessment",
        tags=["8.7: Team KPI"],
        request=ManagerAssessmentUpdateRequestSerializer,
    ),
)
class MyTeamKPIAssessmentViewSet(BaseModelViewSet):
    """Mobile ViewSet for manager assessment of team members."""

    queryset = EmployeeKPIAssessment.objects.none()
    serializer_class = ManagerAssessmentSerializer
    filterset_class = ManagerAssessmentFilterSet
    http_method_names = ["get", "patch"]
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["employee__username", "employee__fullname", "employee__code"]
    ordering_fields = ["period__month", "employee__username", "grade_manager", "total_manager_score"]
    ordering = ["-period__month"]

    module = _("Payroll - Mobile")
    submodule = _("Team KPI")
    permission_prefix = "my_team_kpi_assessment"

    def get_queryset(self):
        """Filter to assessments where current user is the manager."""
        if getattr(self, "swagger_fake_view", False):
            return EmployeeKPIAssessment.objects.none()
        try:
            employee = self.request.user.employee
        except AttributeError:
            return EmployeeKPIAssessment.objects.none()

        return (
            EmployeeKPIAssessment.objects.filter(manager=employee)
            .select_related("period", "employee", "manager")
            .prefetch_related("items")
            .order_by("-period__month")
        )

    def perform_update(self, serializer):
        """Save the updated assessment and handle batch item updates."""
        from django.utils import timezone

        assessment = self.get_object()

        request_serializer = ManagerAssessmentUpdateRequestSerializer(
            data=self.request.data, context={"assessment": assessment}
        )
        request_serializer.is_valid(raise_exception=True)

        validated_request_data = request_serializer.validated_data

        if "grade" in validated_request_data or validated_request_data.get("items"):
            serializer.validated_data["manager_assessment_date"] = timezone.now()

        assessment = serializer.save()
        request_serializer.update_items(assessment, validated_request_data)

        assessment.refresh_from_db()
        recalculate_assessment_scores(assessment)

    @extend_schema(
        summary="Get current team assessments",
        description="Get latest unfinalized assessments for team members",
        tags=["8.7: Team KPI"],
        responses={200: ManagerAssessmentSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "period": {"id": 3, "month": "12/2025", "finalized": False},
                            "employee": {"id": 2, "code": "EMP002", "fullname": "Jane Smith"},
                            "total_possible_score": "100.00",
                            "total_employee_score": "88.00",
                            "total_manager_score": "82.00",
                            "grade_manager": "B",
                            "items": [],
                        }
                    ],
                    "error": None,
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """Get current unfinalized assessments for team members."""
        try:
            employee = request.user.employee
        except AttributeError:
            return Response(
                {"success": False, "data": None, "error": {"detail": "Employee record not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        assessments = (
            EmployeeKPIAssessment.objects.filter(manager=employee, finalized=False)
            .select_related("period", "employee", "manager")
            .prefetch_related("items")
            .order_by("-period__month")
        )

        from collections import OrderedDict

        latest_assessments = OrderedDict()
        for assessment in assessments:
            employee_id = assessment.employee.id
            if employee_id not in latest_assessments:
                latest_assessments[employee_id] = assessment

        serializer = self.get_serializer(list(latest_assessments.values()), many=True)
        return Response(serializer.data)
