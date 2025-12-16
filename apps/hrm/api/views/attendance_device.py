from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import AttendanceDeviceFilterSet
from apps.hrm.api.serializers import AttendanceDeviceSerializer
from apps.hrm.models import AttendanceDevice
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all attendance devices",
        description="Retrieve a paginated list of all attendance devices with support for filtering by name, location, IP address, and connection status",
        tags=["6.1: Attendance Device"],
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
                                "code": "MC001",
                                "name": "Main Entrance Device",
                                "block": {
                                    "id": 1,
                                    "name": "Block A",
                                    "code": "BL001",
                                    "block_type": "production",
                                    "block_type_display": "Production",
                                    "branch": {
                                        "id": 1,
                                        "name": "Hanoi Branch",
                                        "code": "HN001",
                                        "address": "123 Main Street, Hanoi",
                                        "phone": "0123456789",
                                        "email": "hanoi@company.com",
                                        "province": {
                                            "id": 1,
                                            "code": "01",
                                            "name": "Hanoi",
                                            "english_name": "Ha Noi",
                                            "level": "province",
                                            "level_display": "Province",
                                        },
                                        "administrative_unit": {
                                            "id": 1,
                                            "code": "001",
                                            "name": "Hoan Kiem District",
                                            "english_name": "Hoan Kiem",
                                            "level": "district",
                                            "level_display": "District",
                                        },
                                        "is_active": True,
                                    },
                                    "is_active": True,
                                },
                                "ip_address": "192.168.1.100",
                                "port": 4370,
                                "serial_number": "SN123456789",
                                "registration_number": "REG001",
                                "is_enabled": True,
                                "is_connected": True,
                                "realtime_enabled": True,
                                "realtime_disabled_at": None,
                                "polling_synced_at": "2025-10-28T08:00:00Z",
                                "note": "Main entrance device for employee check-in",
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
        tags=["6.1: Attendance Device"],
        examples=[
            OpenApiExample(
                "Create Request",
                value={
                    "name": "Main Entrance Device",
                    "block_id": 1,
                    "ip_address": "192.168.1.100",
                    "port": 4370,
                    "password": "admin123",
                    "is_enabled": True,
                    "note": "Main entrance device for employee check-in",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                            "block_type": "production",
                            "block_type_display": "Production",
                            "branch": {
                                "id": 1,
                                "name": "Hanoi Branch",
                                "code": "HN001",
                                "address": "123 Main Street, Hanoi",
                                "phone": "0123456789",
                                "email": "hanoi@company.com",
                                "province": {
                                    "id": 1,
                                    "code": "01",
                                    "name": "Hanoi",
                                    "english_name": "Ha Noi",
                                },
                                "administrative_unit": {
                                    "id": 1,
                                    "code": "001",
                                    "name": "Hoan Kiem District",
                                    "english_name": "Hoan Kiem",
                                },
                                "is_active": True,
                            },
                            "is_active": True,
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": None,
                        "note": "Main entrance device for employee check-in",
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
        tags=["6.1: Attendance Device"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                            "block_type": "production",
                            "block_type_display": "Production",
                            "branch": {
                                "id": 1,
                                "name": "Hanoi Branch",
                                "code": "HN001",
                                "address": "123 Main Street, Hanoi",
                                "phone": "0123456789",
                                "email": "hanoi@company.com",
                                "province": {
                                    "id": 1,
                                    "code": "01",
                                    "name": "Hanoi",
                                    "english_name": "Ha Noi",
                                },
                                "administrative_unit": {
                                    "id": 1,
                                    "code": "001",
                                    "name": "Hoan Kiem District",
                                    "english_name": "Hoan Kiem",
                                },
                                "is_active": True,
                            },
                            "is_active": True,
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Main entrance device for employee check-in",
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
        tags=["6.1: Attendance Device"],
        examples=[
            OpenApiExample(
                "Update Request",
                value={
                    "name": "Main Entrance Device Updated",
                    "block_id": 1,
                    "ip_address": "192.168.1.100",
                    "port": 4370,
                    "password": "admin123",
                    "is_enabled": True,
                    "note": "Updated note for main entrance",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device Updated",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                            "block_type": "production",
                            "block_type_display": "Production",
                            "branch": {
                                "id": 1,
                                "name": "Hanoi Branch",
                                "code": "HN001",
                            },
                            "is_active": True,
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Updated note for main entrance",
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
        tags=["6.1: Attendance Device"],
        examples=[
            OpenApiExample(
                "Partial Update Request",
                value={
                    "name": "Main Entrance Device - Renamed",
                    "note": "Updated note only",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device - Renamed",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Updated note only",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T09:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete attendance device",
        description="Remove an attendance device from the system. All associated attendance records will also be deleted.",
        tags=["6.1: Attendance Device"],
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
    search_fields = ["code", "name"]
    ordering_fields = ["name", "created_at", "polling_synced_at"]
    ordering = ["name"]

    # Permission registration attributes
    module = "HRM"
    submodule = _("Attendance Device Management")
    permission_prefix = "attendance_device"

    @extend_schema(
        summary="Toggle device enabled status",
        description="Toggle the is_enabled status of an attendance device. When enabling a device, the system will verify the connection to ensure the device is reachable.",
        tags=["6.1: Attendance Device"],
        request=None,
        responses={200: AttendanceDeviceSerializer},
        examples=[
            OpenApiExample(
                "Success - Device Enabled",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Device successfully enabled",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Success - Device Disabled",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": False,
                        "is_connected": False,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Device disabled for maintenance",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T10:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Connection Failed",
                value={
                    "success": False,
                    "data": None,
                    "error": "Failed to connect to device: Connection timeout",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="toggle-enabled")
    def toggle_enabled(self, request, pk=None):
        """Toggle the is_enabled status of an attendance device.

        When enabling, checks the connection to ensure the device is reachable.
        When disabling, sets is_connected to False.
        """
        device = self.get_object()

        # Toggle the is_enabled status
        new_enabled_status = not device.is_enabled
        device.is_enabled = new_enabled_status

        if new_enabled_status:
            # When enabling, check connection
            is_connected, message = device.check_and_update_connection()
            if not is_connected:
                # Reset is_enabled back to False since connection failed
                device.is_enabled = False
                return Response(
                    {"detail": _("Failed to connect to device: %(message)s") % {"message": message}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Connection successful, save the is_enabled status
            device.save(update_fields=["is_enabled", "updated_at"])
        else:
            # When disabling, mark as disconnected
            device.is_connected = False
            device.save(update_fields=["is_enabled", "is_connected", "updated_at"])

        serializer = self.get_serializer(device)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Check device connection",
        description="Test the connection to an attendance device and update its connection status. This action verifies network connectivity and device availability.",
        tags=["6.1: Attendance Device"],
        request=None,
        responses={200: AttendanceDeviceSerializer},
        examples=[
            OpenApiExample(
                "Success - Connected",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": True,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Connection test successful",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T11:00:00Z",
                        "message": "Connection successful. Firmware: 6.60",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Success - Connection Failed",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "MC001",
                        "name": "Main Entrance Device",
                        "block": {
                            "id": 1,
                            "name": "Block A",
                            "code": "BL001",
                        },
                        "ip_address": "192.168.1.100",
                        "port": 4370,
                        "serial_number": "SN123456789",
                        "registration_number": "REG001",
                        "is_enabled": True,
                        "is_connected": False,
                        "realtime_enabled": True,
                        "realtime_disabled_at": None,
                        "polling_synced_at": "2025-10-28T08:00:00Z",
                        "note": "Device unreachable",
                        "created_at": "2025-10-27T10:00:00Z",
                        "updated_at": "2025-10-28T11:00:00Z",
                        "message": "Network connection error: Connection timeout",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="check-connection")
    def check_connection(self, request, pk=None):
        """Check connection to an attendance device and update its status.

        Tests network connectivity and device availability.
        Updates is_connected status and device information if successful.
        """
        device = self.get_object()

        # Check connection and update device info
        _, message = device.check_and_update_connection()

        # Return device data with connection status
        serializer = self.get_serializer(device)
        data = serializer.data
        data["message"] = message

        return Response(data, status=status.HTTP_200_OK)
