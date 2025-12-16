from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import AttendanceRecordFilterSet
from apps.hrm.api.serializers import AttendanceRecordSerializer
from apps.hrm.api.serializers.geolocation_attendance import GeoLocationAttendanceSerializer
from apps.hrm.api.serializers.wifi_attendance import WiFiAttendanceSerializer
from apps.hrm.models import AttendanceRecord
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.drf.mixin.permission import PermissionRegistrationMixin
from libs.drf.mixin.protected_delete import ProtectedDeleteMixin


@extend_schema_view(
    list=extend_schema(
        summary="List attendance records",
        description="Retrieve a paginated list of attendance records with support for filtering by device, attendance code, date/time range.",
        tags=["6.11: Attendance Record"],
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
                                "device": {"id": 1, "name": "Main Entrance Device"},
                                "attendance_code": "531",
                                "timestamp": "2025-10-28T11:49:38Z",
                                "is_valid": True,
                                "notes": "",
                                "created_at": "2025-10-28T11:50:00Z",
                                "updated_at": "2025-10-28T11:50:00Z",
                            },
                            {
                                "id": 1,
                                "device": {"id": 1, "name": "Main Entrance Device"},
                                "attendance_code": "531",
                                "timestamp": "2025-10-28T08:30:15Z",
                                "is_valid": True,
                                "notes": "",
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
        tags=["6.11: Attendance Record"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "device": {"id": 1, "name": "Main Entrance Device"},
                        "attendance_code": "531",
                        "timestamp": "2025-10-28T08:30:15Z",
                        "is_valid": True,
                        "notes": "",
                        "created_at": "2025-10-28T08:31:00Z",
                        "updated_at": "2025-10-28T08:31:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Update attendance record",
        description="Update attendance record. Only timestamp, is_valid, and notes can be modified.",
        tags=["6.11: Attendance Record"],
    ),
    partial_update=extend_schema(
        summary="Partially update attendance record",
        description="Partially update attendance record. Only timestamp, is_valid, and notes can be modified.",
        tags=["6.11: Attendance Record"],
    ),
)
class AttendanceRecordViewSet(
    AuditLoggingMixin,
    PermissionRegistrationMixin,
    ProtectedDeleteMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    """ViewSet for AttendanceRecord model.

    Provides access to attendance records with editing capabilities.
    Only timestamp, is_valid status, and notes can be modified.
    Includes custom actions for GeoLocation and WiFi-based attendance recording.
    """

    queryset = AttendanceRecord.objects.select_related(
        "biometric_device", "employee", "attendance_geolocation", "attendance_wifi_device"
    ).all()
    serializer_class = AttendanceRecordSerializer
    filterset_class = AttendanceRecordFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["attendance_code"]
    ordering_fields = ["timestamp", "created_at"]
    ordering = ["-timestamp"]
    http_method_names = ["get", "put", "patch", "head", "options", "post"]

    # Permission registration attributes
    module = "HRM"
    submodule = _("Attendance Record Management")
    permission_prefix = "attendance_record"
    STANDARD_ACTIONS = {
        **PermissionRegistrationMixin.STANDARD_ACTIONS,
        "geolocation_attendance": {
            "name_template": _("Record attendance by GeoLocation"),
            "description_template": _("Record attendance using GeoLocation coordinates"),
        },
        "wifi_attendance": {
            "name_template": _("Record attendance by WiFi"),
            "description_template": _("Record attendance using WiFi BSSID"),
        },
    }

    @extend_schema(
        summary="Record attendance by GeoLocation",
        description="Record attendance using GeoLocation coordinates. Validates location against geolocation radius and status.",
        tags=["6.11: Attendance Record - For Mobile"],
        request=GeoLocationAttendanceSerializer,
        responses={201: AttendanceRecordSerializer},
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "latitude": "10.7769000",
                    "longitude": "106.7009000",
                    "attendance_geolocation_id": 1,
                    "image_id": 123,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DD001",
                        "attendance_type": "geolocation",
                        "biometric_device": None,
                        "employee": {"id": 1, "code": "NV001", "fullname": "John Doe"},
                        "attendance_code": "531",
                        "timestamp": "2025-11-26T10:30:00Z",
                        "latitude": "10.7769000",
                        "longitude": "106.7009000",
                        "attendance_geolocation": {"id": 1, "code": "DV001", "name": "Main Office"},
                        "image": {"id": 123, "file_name": "attendance_photo.jpg"},
                        "attendance_wifi_device": None,
                        "is_valid": True,
                        "notes": "",
                        "created_at": "2025-11-26T10:30:00Z",
                        "updated_at": "2025-11-26T10:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Outside Radius",
                value={
                    "success": False,
                    "error": {"location": ["Your location is outside the allowed radius (100m) of the geolocation"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="geolocation-attendance")
    def geolocation_attendance(self, request):
        """Record attendance using GeoLocation coordinates."""
        serializer = GeoLocationAttendanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attendance_record = serializer.save()

        # Return the created attendance record
        record_serializer = AttendanceRecordSerializer(attendance_record)
        return Response(record_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Record attendance by WiFi",
        description="Record attendance using WiFi BSSID. Validates WiFi device status.",
        tags=["6.11: Attendance Record - For Mobile"],
        request=WiFiAttendanceSerializer,
        responses={201: AttendanceRecordSerializer},
        examples=[
            OpenApiExample(
                "Request",
                value={"bssid": "00:11:22:33:44:55"},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 2,
                        "code": "DD002",
                        "attendance_type": "wifi",
                        "biometric_device": None,
                        "employee": {"id": 1, "code": "NV001", "fullname": "John Doe"},
                        "attendance_code": "531",
                        "timestamp": "2025-11-26T10:30:00Z",
                        "latitude": None,
                        "longitude": None,
                        "attendance_geolocation": None,
                        "image": None,
                        "attendance_wifi_device": {"id": 1, "code": "WF001", "name": "Office WiFi"},
                        "is_valid": True,
                        "notes": "",
                        "created_at": "2025-11-26T10:30:00Z",
                        "updated_at": "2025-11-26T10:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - WiFi Not In Use",
                value={
                    "success": False,
                    "error": {"bssid": ["WiFi device is not in use"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="wifi-attendance")
    def wifi_attendance(self, request):
        """Record attendance using WiFi BSSID."""
        serializer = WiFiAttendanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attendance_record = serializer.save()

        # Return the created attendance record
        record_serializer = AttendanceRecordSerializer(attendance_record)
        return Response(record_serializer.data, status=status.HTTP_201_CREATED)
