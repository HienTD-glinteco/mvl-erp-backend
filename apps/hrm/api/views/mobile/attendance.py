from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.hrm.api.filtersets import AttendanceRecordFilterSet
from apps.hrm.api.serializers import AttendanceRecordSerializer
from apps.hrm.api.serializers.geolocation_attendance import GeoLocationAttendanceSerializer
from apps.hrm.api.serializers.other_attendance import OtherAttendanceSerializer
from apps.hrm.api.serializers.wifi_attendance import WiFiAttendanceSerializer
from apps.hrm.models import AttendanceRecord
from apps.hrm.utils.attendance_validation import validate_attendance_device
from libs.drf.base_viewset import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List my attendance records",
        description="Retrieve attendance records for the current user",
        tags=["6.11: Attendance Record"],
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
                                "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                                "date": "2025-01-15",
                                "check_in_time": "08:00:00",
                                "check_out_time": "17:00:00",
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
        summary="Get my attendance record details",
        description="Retrieve detailed information for a specific attendance record",
        tags=["6.11: Attendance Record"],
    ),
)
class MyAttendanceRecordViewSet(BaseReadOnlyModelViewSet):
    """Mobile ViewSet for viewing current user's attendance records."""

    queryset = AttendanceRecord.objects.none()
    serializer_class = AttendanceRecordSerializer
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = AttendanceRecordFilterSet
    ordering_fields = ["timestamp", "created_at"]
    ordering = ["-timestamp"]

    module = _("HRM - Mobile")
    submodule = _("My Attendance")
    permission_prefix = "my_attendance_record"
    PERMISSION_REGISTERED_ACTIONS = {
        "geolocation_attendance": {
            "name_template": _("Record attendance by GeoLocation"),
            "description_template": _("Record attendance using GeoLocation coordinates"),
        },
        "wifi_attendance": {
            "name_template": _("Record attendance by WiFi"),
            "description_template": _("Record attendance using WiFi BSSID"),
        },
        "other_attendance": {
            "name_template": _("Record attendance by Other"),
            "description_template": _("Record attendance manually or by other means"),
        },
        "other_bulk_approve": {
            "name_template": _("Bulk approve for Other attendance records"),
            "description_template": _("Approve or reject multiple Other attendance records"),
        },
    }

    def get_queryset(self):
        """Filter to current user's attendance records."""
        if getattr(self, "swagger_fake_view", False):
            return AttendanceRecord.objects.none()
        return AttendanceRecord.objects.filter(employee=self.request.user.employee).select_related("employee")

    @extend_schema(
        summary="Record attendance by GeoLocation",
        description="Record attendance using GeoLocation coordinates. Validates location against geolocation radius and status.",
        tags=["6.11: Attendance Record"],
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
        validate_attendance_device(request)
        serializer = GeoLocationAttendanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attendance_record = serializer.save()

        # Return the created attendance record
        record_serializer = AttendanceRecordSerializer(attendance_record)
        return Response(record_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Record attendance by WiFi",
        description="Record attendance using WiFi BSSID. Validates WiFi device status.",
        tags=["6.11: Attendance Record"],
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
        validate_attendance_device(request)
        serializer = WiFiAttendanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attendance_record = serializer.save()

        # Return the created attendance record
        record_serializer = AttendanceRecordSerializer(attendance_record)
        return Response(record_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Record attendance by Other",
        description="Record attendance manually or by other means. Pending approval.",
        tags=["6.11: Attendance Record"],
        request=OtherAttendanceSerializer,
        responses={201: AttendanceRecordSerializer},
    )
    @action(detail=False, methods=["post"], url_path="other-attendance")
    def other_attendance(self, request):
        """Record attendance manually or by other means."""
        validate_attendance_device(request)
        serializer = OtherAttendanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attendance_record = serializer.save()

        record_serializer = AttendanceRecordSerializer(attendance_record)
        return Response(record_serializer.data, status=status.HTTP_201_CREATED)
