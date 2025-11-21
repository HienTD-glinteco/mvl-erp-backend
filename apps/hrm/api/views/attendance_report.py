from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from libs.drf.base_viewset import BaseGenericViewSet

from ..serializers import AttendanceMethodReportParameterSerializer, AttendanceMethodReportSerializer


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
