from django.db.models import Count, Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceDailyReport, Block, Branch, Department, TimeSheetEntry
from apps.hrm.utils.functions import calculate_percentage
from apps.realestate.models import Project
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

    module = _("Report")
    submodule = _("Attendance")
    permission_prefix = "recruitment_reports"
    PERMISSION_REGISTERED_ACTIONS = {
        "by_method": {
            "name_template": _("Attendance Report By Method"),
            "description_template": _("Get attendance statistics report by method (device, wifi, geolocation, other)"),
        },
        "by_project": {
            "name_template": _("Attendance Report By Project"),
            "description_template": _("Get attendance statistics report grouped by projects"),
        },
        "by_project_organization": {
            "name_template": _("Attendance Report By Project Organization"),
            "description_template": _(
                "Get attendance statistics report for personnel working on projects grouped by organizational structure"
            ),
        },
    }

    @extend_schema(
        tags=["6.9: Attendance Reports"],
        operation_id="hrm_reports_attendance_by_method",
        summary="Attendance Report By Method",
        description="Get attendance statistics report by method (device, wifi, geolocation, other). "
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
                            "method_breakdown": {"device": 3, "wifi": 3, "geolocation": 1, "other": 0},
                        },
                        "percentage": {
                            "total_employee": 100,
                            "not_attendance": 30,
                            "has_attendance": 70,
                            "method_breakdown": {"device": 30, "wifi": 30, "geolocation": 10, "other": 0},
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
        params = AttendanceMethodReportParameterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.get_filters()

        # Get total employees from TimeSheetEntry
        # Assuming one entry per employee per day
        timesheet_filters = {"date": filters.get("report_date")}
        # Map report filters to timesheet filters if needed (e.g. branch, block, department)
        # TimeSheetEntry doesn't have branch/block/dept directly, it links to Employee.
        # So we filter by employee__branch_id etc.
        if "branch_id" in filters:
            timesheet_filters["employee__branch_id"] = filters["branch_id"]
        if "block_id" in filters:
            timesheet_filters["employee__block_id"] = filters["block_id"]
        if "department_id" in filters:
            timesheet_filters["employee__department_id"] = filters["department_id"]

        total_employee = TimeSheetEntry.objects.filter(**timesheet_filters).count()

        # Get attendance stats
        attendance_stats = AttendanceDailyReport.objects.filter(**filters).aggregate(
            device=Count("id", filter=Q(attendance_method=AttendanceType.BIOMETRIC_DEVICE)),
            wifi=Count("id", filter=Q(attendance_method=AttendanceType.WIFI)),
            geolocation=Count("id", filter=Q(attendance_method=AttendanceType.GEOLOCATION)),
            other=Count("id", filter=Q(attendance_method=AttendanceType.OTHER)),
            total=Count("id"),
        )

        has_attendance = attendance_stats["total"]
        not_attendance = max(0, total_employee - has_attendance)

        data = {
            "absolute": {
                "total_employee": total_employee,
                "not_attendance": not_attendance,
                "has_attendance": has_attendance,
                "method_breakdown": {
                    "device": attendance_stats["device"],
                    "wifi": attendance_stats["wifi"],
                    "geolocation": attendance_stats["geolocation"],
                    "other": attendance_stats["other"],
                },
            },
            "percentage": {
                "total_employee": 100 if total_employee > 0 else 0,
                "not_attendance": calculate_percentage(not_attendance, total_employee),
                "has_attendance": calculate_percentage(has_attendance, total_employee),
                "method_breakdown": {
                    "device": calculate_percentage(attendance_stats["device"], total_employee),
                    "wifi": calculate_percentage(attendance_stats["wifi"], total_employee),
                    "geolocation": calculate_percentage(attendance_stats["geolocation"], total_employee),
                    "other": calculate_percentage(attendance_stats["other"], total_employee),
                },
            },
        }
        serializer = AttendanceMethodReportSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        tags=["6.9: Attendance Reports"],
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
        params = AttendanceProjectReportParameterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.get_filters()
        filters["project__isnull"] = False

        # Aggregate by project
        project_stats = (
            AttendanceDailyReport.objects.filter(**filters)
            .values("project")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        project_ids = [item["project"] for item in project_stats]
        projects = Project.objects.in_bulk(project_ids)

        results = []
        total = 0
        for item in project_stats:
            project_id = item["project"]
            count = item["count"]
            if project_id in projects:
                results.append({"project": projects[project_id], "count": count})
                total += count

        data = {
            "projects": results,
            "total": total,
        }
        serializer = AttendanceProjectReportAggregrationSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        tags=["6.9: Attendance Reports"],
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
        params = AttendanceProjectOrgReportParameterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.get_filters()
        filters.update(
            {
                "branch__isnull": False,
                "block__isnull": False,
                "department__isnull": False,
            }
        )

        # Aggregate counts by org unit
        stats = (
            AttendanceDailyReport.objects.filter(**filters)
            .values("branch", "block", "department")
            .annotate(count=Count("id"))
        )

        # Fetch org units
        branch_ids = {item["branch"] for item in stats}
        block_ids = {item["block"] for item in stats}
        department_ids = {item["department"] for item in stats}

        branches = Branch.objects.in_bulk(branch_ids)
        blocks = Block.objects.in_bulk(block_ids)
        departments = Department.objects.in_bulk(department_ids)

        # Build tree
        tree = {}
        total = 0

        for item in stats:
            b_id = item["branch"]
            bl_id = item["block"]
            d_id = item["department"]
            count = item["count"]
            total += count

            if b_id not in branches or bl_id not in blocks or d_id not in departments:
                continue

            branch_node = tree.setdefault(
                b_id,
                {
                    "id": b_id,
                    "name": branches[b_id].name,
                    "type": "branch",
                    "count": 0,
                    "children": {},
                },
            )
            branch_node["count"] += count

            block_node = branch_node["children"].setdefault(
                bl_id,
                {
                    "id": bl_id,
                    "name": blocks[bl_id].name,
                    "type": "block",
                    "count": 0,
                    "children": {},
                },
            )
            block_node["count"] += count

            dept_node = block_node["children"].setdefault(
                d_id,
                {
                    "id": d_id,
                    "name": departments[d_id].name,
                    "type": "department",
                    "count": 0,
                },
            )
            dept_node["count"] += count

        # Convert dicts to lists
        result_children = []
        for b_val in tree.values():
            blocks_list = []
            for bl_val in b_val["children"].values():
                depts_list = list(bl_val["children"].values())
                bl_val["children"] = depts_list
                blocks_list.append(bl_val)
            b_val["children"] = blocks_list
            result_children.append(b_val)

        data = {
            "total": total,
            "children": result_children,
        }
        serializer = AttendanceProjectOrgReportAggregrationSerializer(data)
        return Response(serializer.data)
