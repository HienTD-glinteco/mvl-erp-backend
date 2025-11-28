from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import AttendanceExemptionFilterSet
from apps.hrm.api.serializers import AttendanceExemptionExportSerializer, AttendanceExemptionSerializer
from apps.hrm.models import AttendanceExemption
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List attendance exemptions",
        description="Retrieve a paginated list of employees exempt from attendance tracking",
        tags=["6.7 Attendance Exemption"],
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
                                "employee": {
                                    "id": 123,
                                    "code": "EMP001",
                                    "fullname": "John Doe",
                                    "email": "john.doe@example.com",
                                    "position": {
                                        "id": 5,
                                        "code": "MGR",
                                        "name": "Manager",
                                    },
                                    "branch": {
                                        "id": 1,
                                        "code": "HQ",
                                        "name": "Head Office",
                                    },
                                    "block": {
                                        "id": 2,
                                        "code": "TECH",
                                        "name": "Technology",
                                    },
                                    "department": {
                                        "id": 10,
                                        "code": "IT",
                                        "name": "Information Technology",
                                    },
                                },
                                "effective_date": "2025-01-01",
                                "notes": "Exempt from attendance tracking",
                                "created_at": "2025-11-01T08:00:00Z",
                                "updated_at": "2025-11-01T08:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create attendance exemption",
        description="Create a new attendance exemption for an employee",
        tags=["6.7 Attendance Exemption"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee_id": 123,
                    "effective_date": "2025-01-01",
                    "notes": "Management decision",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {
                            "id": 123,
                            "code": "EMP001",
                            "fullname": "John Doe",
                            "email": "john.doe@example.com",
                            "position": {
                                "id": 5,
                                "code": "MGR",
                                "name": "Manager",
                            },
                            "branch": None,
                            "block": None,
                            "department": None,
                        },
                        "effective_date": "2025-01-01",
                        "notes": "Management decision",
                        "created_at": "2025-11-17T08:00:00Z",
                        "updated_at": "2025-11-17T08:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Duplicate",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "employee_id": ["Employee already has an active exemption."],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get exemption details",
        description="Retrieve detailed information about a specific attendance exemption",
        tags=["6.7 Attendance Exemption"],
    ),
    update=extend_schema(
        summary="Update exemption",
        description="Update attendance exemption information",
        tags=["6.7 Attendance Exemption"],
    ),
    partial_update=extend_schema(
        summary="Partially update exemption",
        description="Partially update attendance exemption information",
        tags=["6.7 Attendance Exemption"],
    ),
    destroy=extend_schema(
        summary="Delete exemption",
        description="Permanently remove an attendance exemption from the system",
        tags=["6.7 Attendance Exemption"],
    ),
    export=extend_schema(
        tags=["6.7 Attendance Exemption"],
    ),
)
class AttendanceExemptionViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for AttendanceExemption model."""

    queryset = AttendanceExemption.objects.select_related(
        "employee",
        "employee__branch",
        "employee__block",
        "employee__department",
        "employee__position",
    ).all()
    serializer_class = AttendanceExemptionSerializer
    filterset_class = AttendanceExemptionFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["employee__code", "employee__fullname"]
    ordering_fields = ["employee__code", "effective_date", "created_at"]
    ordering = ["-employee__code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Attendance Management"
    permission_prefix = "attendance_exemption"

    def get_export_data(self, request):
        """Custom export data for AttendanceExemption.

        Exports the following fields:
        - employee__code
        - employee__fullname
        - employee__position__name
        - effective_date
        - notes
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = AttendanceExemptionExportSerializer(queryset, many=True)
        data = serializer.data

        return {
            "sheets": [
                {
                    "name": "Attendance Exemption",
                    "headers": [
                        "Employee Code",
                        "Employee Name",
                        "Position",
                        "Effective Date",
                        "Notes",
                    ],
                    "field_names": [
                        "employee__code",
                        "employee__fullname",
                        "employee__position__name",
                        "effective_date",
                        "notes",
                    ],
                    "data": data,
                }
            ]
        }
