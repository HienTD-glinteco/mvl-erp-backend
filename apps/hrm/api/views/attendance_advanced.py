"""Views for GPS and WiFi-based attendance recording."""

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.api.serializers.attendance_advanced import GPSAttendanceSerializer, WiFiAttendanceSerializer
from apps.hrm.api.serializers.attendance_record import AttendanceRecordSerializer
from apps.hrm.api.views.attendance_record import AttendanceRecordViewSet


class AttendanceAdvancedViewSet(AttendanceRecordViewSet):
    """Extended ViewSet for AttendanceRecord with GPS and WiFi attendance endpoints."""

    @extend_schema(
        summary="Record attendance by GPS",
        description="Record attendance using GPS coordinates. Validates location against geolocation radius and status.",
        tags=["Attendance Record"],
        request=GPSAttendanceSerializer,
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
                        "attendance_type": "gps",
                        "device": None,
                        "employee": {"id": 1, "code": "NV001", "fullname": "John Doe", "attendance_code": "531"},
                        "attendance_code": "531",
                        "timestamp": "2025-11-26T10:30:00Z",
                        "latitude": "10.7769000",
                        "longitude": "106.7009000",
                        "attendance_geolocation": {"id": 1, "code": "DV001", "name": "Main Office"},
                        "image": {
                            "id": 123,
                            "file_name": "attendance_photo.jpg",
                            "purpose": "attendance_photo",
                        },
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
            OpenApiExample(
                "Error - Inactive Geolocation",
                value={
                    "success": False,
                    "error": {"attendance_geolocation_id": ["Attendance geolocation is not active"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="gps-attendance")
    def gps_attendance(self, request):
        """Record attendance using GPS coordinates."""
        serializer = GPSAttendanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attendance_record = serializer.save()

        # Return the created attendance record
        record_serializer = AttendanceRecordSerializer(attendance_record)
        return Response(record_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Record attendance by WiFi",
        description="Record attendance using WiFi BSSID. Validates WiFi device status.",
        tags=["Attendance Record"],
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
                        "device": None,
                        "employee": {"id": 1, "code": "NV001", "fullname": "John Doe", "attendance_code": "531"},
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
            OpenApiExample(
                "Error - WiFi Not Found",
                value={
                    "success": False,
                    "error": {"bssid": ["WiFi device not found"]},
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
