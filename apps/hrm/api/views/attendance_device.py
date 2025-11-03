from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import AttendanceDeviceFilterSet
from apps.hrm.api.serializers import AttendanceDeviceSerializer
from apps.hrm.models import AttendanceDevice
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all attendance devices",
        description="Retrieve a paginated list of all attendance devices with support for filtering by name, location, IP address, and connection status",
        tags=["Attendance Device"],
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
                                "name": "Main Entrance Device",
                                "location": "Building A - Main Entrance",
                                "ip_address": "192.168.1.100",
                                "port": 4370,
                                "is_enabled": True,
                                "is_connected": True,
                                "polling_synced_at": "2025-10-28T08:00:00Z",
                                "created_at": "2025-10-27T10:00:00Z",
                                "updated_at": "2025-10-28T08:00:00Z",
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
        summary="Create a new attendance device",
        description="Create a new attendance device in the system. The system will automatically test the connection, retrieve serial number and registration number from the device, and update the connection status.",
        tags=["Attendance Device"],
        examples=[
            OpenApiExample(
                "Create Request",
                value={
                    "name": "Main Entrance Device",
                    "block_id": 10,
                    "ip_address": "192.168.1.100",
                    "port": 4370,
                    "password": "admin123",
                    "is_enabled": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "Main Entrance Device",
                        "block_id": 10,
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "polling_synced_at": None,
                        "created_at": "2025-10-28T08:00:00Z",
                        "updated_at": "2025-10-28T08:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Connection Error",
                value={
                    "success": False,
                    "data": None,
                    "error": {"ip_address": ["Network connection error: Connection timeout"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get attendance device details",
        description="Retrieve detailed information about a specific attendance device",
        tags=["Attendance Device"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "Main Entrance Device",
                        "block": {},
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T08:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Update attendance device",
        description="Update attendance device information. Connection will be re-tested and device info updated.",
        tags=["Attendance Device"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "Main Entrance Device Updated",
                        "block_id": 1,
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T09:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update attendance device",
        description="Partially update attendance device information. If network details are changed, connection will be re-tested.",
        tags=["Attendance Device"],
    ),
    destroy=extend_schema(
        summary="Delete attendance device",
        description="Remove an attendance device from the system. All associated attendance records will also be deleted.",
        tags=["Attendance Device"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
                status_codes=["204"],
            ),
        ],
    ),
)
class AttendanceDeviceViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for AttendanceDevice model.

    Provides CRUD operations for attendance device management.
    Automatically tests connection and retrieves device information on create/update.
    """

    queryset = AttendanceDevice.objects.select_related(
        "block__branch__province", "block__branch__administrative_unit"
    ).all()
    serializer_class = AttendanceDeviceSerializer
    filterset_class = AttendanceDeviceFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "polling_synced_at"]
    ordering = ["name"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Attendance Device Management"
    permission_prefix = "attendance_device"
