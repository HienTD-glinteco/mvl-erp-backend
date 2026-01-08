from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import AttendanceWifiDeviceFilterSet
from apps.hrm.api.serializers import AttendanceWifiDeviceExportSerializer, AttendanceWifiDeviceSerializer
from apps.hrm.models import AttendanceWifiDevice
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all WiFi attendance devices",
        description="Retrieve a paginated list of all WiFi attendance devices with support for filtering and search. "
        "Pagination: 25 items per page by default (customizable via page_size parameter, e.g., ?page_size=20)",
        tags=["6.2: Attendance WiFiDevice"],
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
                                "code": "WF001",
                                "name": "Office WiFi Main",
                                "branch": {
                                    "id": 1,
                                    "name": "Ho Chi Minh Branch",
                                    "code": "CN001",
                                },
                                "block": {
                                    "id": 1,
                                    "name": "Business Block 1",
                                    "code": "KH001",
                                },
                                "bssid": "00:11:22:33:44:55",
                                "state": "in_use",
                                "notes": "Main office WiFi network",
                                "created_at": "2025-11-17T08:00:00Z",
                                "updated_at": "2025-11-17T08:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new WiFi attendance device",
        description="Create a new WiFi attendance device configuration in the system. "
        "The code is auto-generated server-side with pattern WF###. "
        "BSSID must be in MAC address format (XX:XX:XX:XX:XX:XX).",
        tags=["6.2: Attendance WiFiDevice"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Office WiFi Main",
                    "branch_id": 1,
                    "block_id": 1,
                    "bssid": "00:11:22:33:44:55",
                    "state": "in_use",
                    "notes": "Main office WiFi network",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "WF001",
                        "name": "Office WiFi Main",
                        "branch": {
                            "id": 1,
                            "name": "Ho Chi Minh Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block 1",
                            "code": "KH001",
                        },
                        "bssid": "00:11:22:33:44:55",
                        "state": "in_use",
                        "notes": "Main office WiFi network",
                        "created_at": "2025-11-17T08:00:00Z",
                        "updated_at": "2025-11-17T08:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Validation",
                value={
                    "success": False,
                    "error": {
                        "name": ["This field is required."],
                        "bssid": ["BSSID must be in MAC address format (XX:XX:XX:XX:XX:XX)"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get WiFi attendance device details",
        description="Retrieve detailed information about a specific WiFi attendance device configuration",
        tags=["6.2: Attendance WiFiDevice"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "WF001",
                        "name": "Office WiFi Main",
                        "branch": {
                            "id": 1,
                            "name": "Ho Chi Minh Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block 1",
                            "code": "KH001",
                        },
                        "bssid": "00:11:22:33:44:55",
                        "state": "in_use",
                        "notes": "Main office WiFi network",
                        "created_at": "2025-11-17T08:00:00Z",
                        "updated_at": "2025-11-17T08:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update WiFi attendance device",
        description="Update WiFi attendance device configuration. Code cannot be changed.",
        tags=["6.2: Attendance WiFiDevice"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Office WiFi Main Updated",
                    "branch_id": 1,
                    "block_id": 1,
                    "bssid": "00:11:22:33:44:55",
                    "state": "not_in_use",
                    "notes": "Temporarily disabled for maintenance",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "WF001",
                        "name": "Office WiFi Main Updated",
                        "branch": {
                            "id": 1,
                            "name": "Ho Chi Minh Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block 1",
                            "code": "KH001",
                        },
                        "bssid": "00:11:22:33:44:55",
                        "state": "not_in_use",
                        "notes": "Temporarily disabled for maintenance",
                        "created_at": "2025-11-17T08:00:00Z",
                        "updated_at": "2025-11-17T08:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update WiFi attendance device",
        description="Partially update WiFi attendance device configuration",
        tags=["6.2: Attendance WiFiDevice"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "state": "in_use",
                    "notes": "Re-enabled after maintenance",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "WF001",
                        "name": "Office WiFi Main",
                        "branch": {
                            "id": 1,
                            "name": "Ho Chi Minh Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block 1",
                            "code": "KH001",
                        },
                        "bssid": "00:11:22:33:44:55",
                        "state": "in_use",
                        "notes": "Re-enabled after maintenance",
                        "created_at": "2025-11-17T08:00:00Z",
                        "updated_at": "2025-11-17T08:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete WiFi attendance device",
        description="Delete a WiFi attendance device configuration from the system. "
        "If the device is referenced by other active resources (e.g., attendance records), "
        "the deletion will be prevented.",
        tags=["6.2: Attendance WiFiDevice"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
            OpenApiExample(
                "Error - Protected",
                value={
                    "success": False,
                    "error": {
                        "detail": "Cannot delete this Attendance WiFiDevice because it is referenced by: 5 Attendance Records",
                        "protected_objects": [
                            {
                                "count": 5,
                                "name": "Attendance Records",
                                "protected_object_ids": [1, 2, 3, 4, 5],
                            }
                        ],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    export=extend_schema(
        tags=["6.2: Attendance WiFiDevice"],
    ),
)
class AttendanceWifiDeviceViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for AttendanceWifiDevice model"""

    queryset = AttendanceWifiDevice.objects.select_related("branch", "block")
    serializer_class = AttendanceWifiDeviceSerializer
    filterset_class = AttendanceWifiDeviceFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "name", "bssid"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = _("HRM")
    submodule = _("Attendance WiFiDevice Management")
    permission_prefix = "wifi_attendance_device"

    xlsx_template_name = "apps/hrm/fixtures/export_templates/attendance_wifi_device_export_template.xlsx"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "export":
            return AttendanceWifiDeviceExportSerializer
        return AttendanceWifiDeviceSerializer

    def get_export_data(self, request):
        """Custom export data for AttendanceWifiDevice with template support.

        Exports the following fields:
        - STT (index)
        - code (WiFi Attendance Code)
        - name (WiFi Attendance Name)
        - branch_name (Branch)
        - block_name (Block)
        - bssid (BSSID)
        - state_display (Usage State)
        - notes (Notes)
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        headers = [str(field.label) for field in serializer.child.fields.values()]
        data = serializer.data
        field_names = list(serializer.child.fields.keys())
        if self.xlsx_template_name:
            headers = [_(self.xlsx_template_index_column_key), *headers]
            field_names = [self.xlsx_template_index_column_key, *field_names]
            for index, row in enumerate(data, start=1):
                row.update({self.xlsx_template_index_column_key: index})

        return {
            "sheets": [
                {
                    "name": str(AttendanceWifiDevice._meta.verbose_name),
                    "headers": headers,
                    "field_names": field_names,
                    "data": data,
                }
            ]
        }

    def destroy(self, request, *args, **kwargs):
        """
        Delete an object with validation for protected relationships.

        Performs soft delete and catches ProtectedError if the object
        has protected related objects.
        """
        from django.db.models import ProtectedError
        from rest_framework import status
        from rest_framework.response import Response

        instance = self.get_object()

        try:
            self.perform_destroy(instance)
        except ProtectedError as e:
            # Build a user-friendly error message
            error_detail = self._format_protected_error(instance, e)
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _format_protected_error(self, instance, error):
        """Format a ProtectedError into a user-friendly error message."""
        from django.utils.translation import gettext as _

        # Get the model name for the instance being deleted
        model_name = instance._meta.verbose_name

        # Extract protected objects from the error
        protected_objects = error.protected_objects

        # Group protected objects by model type
        objects_by_model = {}
        for obj in protected_objects:
            model_class = obj.__class__
            model_verbose_name = model_class._meta.verbose_name_plural

            if model_verbose_name not in objects_by_model:
                objects_by_model[model_verbose_name] = {
                    "count": 0,
                    "name": str(model_verbose_name),
                    "protected_object_ids": [],
                }
            objects_by_model[model_verbose_name]["count"] += 1
            objects_by_model[model_verbose_name]["protected_object_ids"].append(obj.pk)

        # Build the main error message
        protected_list = objects_by_model.values()
        if protected_list:
            # Create a human-readable list of protected relationships
            relationship_descriptions = []
            for protected_info in protected_list:
                count = protected_info["count"]
                name = protected_info["name"]
                relationship_descriptions.append(f"{count} {name}")

            relationships_text = ", ".join(relationship_descriptions)
            detail_message = _("Cannot delete this {model_name} because it is referenced by: {relationships}").format(
                model_name=model_name, relationships=relationships_text
            )
        else:
            detail_message = _("Cannot delete this {model_name} because it has protected relationships").format(
                model_name=model_name
            )

        return {"detail": detail_message, "protected_objects": list(protected_list)}

    def perform_destroy(self, instance):
        """Perform soft delete instead of hard delete"""
        instance.delete()
