from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.hrm.api.filtersets import AttendanceRecordFilterSet
from apps.hrm.api.serializers import AttendanceRecordSerializer
from apps.hrm.models import AttendanceRecord


@extend_schema_view(
    list=extend_schema(
        summary="List attendance records",
        description="Retrieve a paginated list of attendance records with support for filtering by device, attendance code, date/time range. Attendance records are read-only and created automatically via device polling.",
        tags=["Attendance Record"],
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
                                "id": 2,
                                "device": {"id": 1, "name": "Main Entrance Device", "location": "Building A - Main Entrance"},
                                "attendance_code": "531",
                                "timestamp": "2025-10-28T11:49:38Z",
                                "raw_data": {
                                    "uid": 3525,
                                    "user_id": "531",
                                    "timestamp": "2025-10-28T11:49:38",
                                    "status": 1,
                                    "punch": 0,
                                },
                                "created_at": "2025-10-28T11:50:00Z",
                                "updated_at": "2025-10-28T11:50:00Z",
                            },
                            {
                                "id": 1,
                                "device": {"id": 1, "name": "Main Entrance Device", "location": "Building A - Main Entrance"},
                                "attendance_code": "531",
                                "timestamp": "2025-10-28T08:30:15Z",
                                "raw_data": {
                                    "uid": 3525,
                                    "user_id": "531",
                                    "timestamp": "2025-10-28T08:30:15",
                                    "status": 1,
                                    "punch": 0,
                                },
                                "created_at": "2025-10-28T08:31:00Z",
                                "updated_at": "2025-10-28T08:31:00Z",
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get attendance record details",
        description="Retrieve detailed information about a specific attendance record",
        tags=["Attendance Record"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "device": {"id": 1, "name": "Main Entrance Device", "location": "Building A - Main Entrance"},
                        "attendance_code": "531",
                        "timestamp": "2025-10-28T08:30:15Z",
                        "raw_data": {
                            "uid": 3525,
                            "user_id": "531",
                            "timestamp": "2025-10-28T08:30:15",
                            "status": 1,
                            "punch": 0,
                        },
                        "created_at": "2025-10-28T08:31:00Z",
                        "updated_at": "2025-10-28T08:31:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
)
class AttendanceRecordViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ViewSet for AttendanceRecord model.

    Provides read-only access to attendance records.
    Attendance records are created automatically via device polling and
    should not be manually created or modified through the API.
    """

    queryset = AttendanceRecord.objects.select_related("device").all()
    serializer_class = AttendanceRecordSerializer
    filterset_class = AttendanceRecordFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["attendance_code"]
    ordering_fields = ["timestamp", "created_at"]
    ordering = ["-timestamp"]
