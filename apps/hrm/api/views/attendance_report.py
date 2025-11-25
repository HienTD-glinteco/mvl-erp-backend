from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from libs.drf.base_viewset import BaseGenericViewSet

from ..serializers import (
    AttendanceMethodReportParameterSerializer,
    AttendanceMethodReportSerializer,
    AttendanceProjectOrgReportAggregrationSerializer,
    AttendanceProjectOrgReportParameterSerializer,
    AttendanceProjectReportAggregrationSerializer,
    AttendanceProjectReportParameterSerializer,
)


class AttendanceReportViewSet(BaseGenericViewSet):
    pagination_class = None

    module = "Report"
    submodule = "Attendance"
    permission_prefix = "recruitment_reports"

    @extend_schema(
        tags=["6.9.1: Attendance Report By Method"],
        operation_id="hrm_reports_attendance_by_method",
        summary="Attendance Report By Method",
        description="Get attendance statistics report by method (device, wifi, geolocation). "
        "This report shows the breakdown of employee attendance methods within a specified time period and organizational structure. "
        "The report includes both absolute numbers and percentages for total employees, attendance status, and method breakdown. "
        "Filters can be applied for specific date, branch, block, and department."
        "\n\nFigma: https://www.figma.com/design/qtYtyAU3l18u5iTUztart7/-MVL-NE----HRM?node-id=8298-1741653&t=efRZiByZkS0RqntX-0",
        parameters=[AttendanceMethodReportParameterSerializer],
        responses={200: AttendanceMethodReportSerializer()},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "absolute": {
                            "total_employee": 10,
                            "not_attendance": 3,
                            "has_attendance": 7,
                            "method_breakdown": {"device": 3, "wifi": 3, "geolocation": 1},
                        },
                        "percentage": {
                            "total_employee": 100,
                            "not_attendance": 30,
                            "has_attendance": 70,
                            "method_breakdown": {"device": 30, "wifi": 30, "geolocation": 10},
                        },
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid Date Format",
                value={
                    "success": False,
                    "data": None,
                    "error": {"attendance_date": ["Invalid date format. Use YYYY-MM-DD format."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="by-method")
    def by_method(self, request):
        # Mock data for now
        data = {
            "absolute": {
                "total_employee": 10,
                "not_attendance": 3,
                "has_attendance": 7,
                "method_breakdown": {"device": 3, "wifi": 3, "geolocation": 1},
            },
            "percentage": {
                "total_employee": 100,
                "not_attendance": 30,
                "has_attendance": 70,
                "method_breakdown": {"device": 30, "wifi": 30, "geolocation": 10},
            },
        }
        serializer = AttendanceMethodReportSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        tags=["6.9.3: Attendance Report By Project"],
        operation_id="hrm_reports_attendance_by_project",
        summary="Attendance Report By Project",
        description="Get attendance statistics report grouped by projects. "
        "This report shows the number of employees who have attendance records for each project within the specified filters. "
        "The report aggregates attendance data by project, showing which projects have the most attendance activity. "
        "Filters can be applied for specific date, branch, block, department, and block type."
        "\n\nFigma: https://www.figma.com/design/qtYtyAU3l18u5iTUztart7/-MVL-NE----HRM?node-id=8298-1741654&t=efRZiByZkS0RqntX-0",
        parameters=[AttendanceProjectReportParameterSerializer],
        responses={200: AttendanceProjectReportAggregrationSerializer()},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "projects": [
                            {"project": {"id": 1, "name": "Sunrise Apartment Complex", "code": "SAP001"}, "count": 25},
                            {"project": {"id": 2, "name": "Metro Shopping Center", "code": "MSC002"}, "count": 18},
                            {"project": {"id": 3, "name": "Riverside Office Tower", "code": "ROT003"}, "count": 12},
                        ],
                        "total": 55,
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid Block Type",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "block_type": ["Invalid choice. Valid choices are: 'branch', 'department', 'position'."]
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="by-project")
    def by_project(self, request):
        # Mock data for now
        data = {
            "projects": [
                {"project": {"id": 1, "name": "Sunrise Apartment Complex", "code": "SAP001"}, "count": 25},
                {"project": {"id": 2, "name": "Metro Shopping Center", "code": "MSC002"}, "count": 18},
                {"project": {"id": 3, "name": "Riverside Office Tower", "code": "ROT003"}, "count": 12},
            ],
            "total": 55,
        }
        serializer = AttendanceProjectReportAggregrationSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        tags=["6.9.5: Attendance Report By Project Organization"],
        operation_id="hrm_reports_attendance_by_project_organization",
        summary="Attendance Report By Project Organization",
        description="Get attendance statistics report for personnel working on projects grouped by organizational structure. "
        "This report shows the hierarchical breakdown of employee attendance on projects by branch, block, and department. "
        "The report displays the organizational structure with attendance counts at each level, helping to understand "
        "which organizational units have the most project attendance activity. "
        "An optional project filter can be applied to focus on a specific project."
        "\n\nFigma: https://www.figma.com/design/qtYtyAU3l18u5iTUztart7/-MVL-NE----HRM?node-id=8298-1741655&t=efRZiByZkS0RqntX-0",
        parameters=[AttendanceProjectOrgReportParameterSerializer],
        responses={200: AttendanceProjectOrgReportAggregrationSerializer()},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "total": 45,
                        "children": [
                            {
                                "id": 1,
                                "name": "Ho Chi Minh City Branch",
                                "type": "branch",
                                "count": 25,
                                "children": [
                                    {
                                        "id": 1,
                                        "name": "IT Block",
                                        "type": "block",
                                        "count": 15,
                                        "children": [
                                            {
                                                "id": 1,
                                                "name": "Development Department",
                                                "type": "department",
                                                "count": 10,
                                            },
                                            {"id": 2, "name": "QA Department", "type": "department", "count": 5},
                                        ],
                                    },
                                    {
                                        "id": 2,
                                        "name": "HR Block",
                                        "type": "block",
                                        "count": 10,
                                        "children": [
                                            {
                                                "id": 3,
                                                "name": "Recruitment Department",
                                                "type": "department",
                                                "count": 10,
                                            }
                                        ],
                                    },
                                ],
                            },
                            {
                                "id": 2,
                                "name": "Ha Noi Branch",
                                "type": "branch",
                                "count": 20,
                                "children": [
                                    {
                                        "id": 3,
                                        "name": "Operations Block",
                                        "type": "block",
                                        "count": 20,
                                        "children": [
                                            {
                                                "id": 4,
                                                "name": "Project Management Department",
                                                "type": "department",
                                                "count": 20,
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Project Not Found",
                value={"success": False, "data": None, "error": {"project": ["Project with this ID does not exist."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="by-project-organization")
    def by_project_organization(self, request):
        # Mock data for now
        data = {
            "total": 45,
            "children": [
                {
                    "id": 1,
                    "name": "Ho Chi Minh City Branch",
                    "type": "branch",
                    "count": 25,
                    "children": [
                        {
                            "id": 1,
                            "name": "IT Block",
                            "type": "block",
                            "count": 15,
                            "children": [
                                {"id": 1, "name": "Development Department", "type": "department", "count": 10},
                                {"id": 2, "name": "QA Department", "type": "department", "count": 5},
                            ],
                        },
                        {
                            "id": 2,
                            "name": "HR Block",
                            "type": "block",
                            "count": 10,
                            "children": [
                                {"id": 3, "name": "Recruitment Department", "type": "department", "count": 10}
                            ],
                        },
                    ],
                },
                {
                    "id": 2,
                    "name": "Ha Noi Branch",
                    "type": "branch",
                    "count": 20,
                    "children": [
                        {
                            "id": 3,
                            "name": "Operations Block",
                            "type": "block",
                            "count": 20,
                            "children": [
                                {"id": 4, "name": "Project Management Department", "type": "department", "count": 20}
                            ],
                        }
                    ],
                },
            ],
        }
        serializer = AttendanceProjectOrgReportAggregrationSerializer(data)
        return Response(serializer.data)
