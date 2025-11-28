from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import AttendanceGeolocationFilterSet
from apps.hrm.api.serializers import AttendanceGeolocationExportSerializer, AttendanceGeolocationSerializer
from apps.hrm.models import AttendanceGeolocation
from apps.hrm.utils.filters import DistanceOrderingFilterBackend
from libs import BaseModelViewSet
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all attendance geolocations",
        description="Retrieve a paginated list of all attendance geolocations with support for filtering and search. "
        "Pagination: 25 items per page by default (customizable via page_size parameter, e.g., ?page_size=20). "
        "Distance-based sorting: Provide user_latitude and user_longitude parameters with ordering=distance to sort by nearest location.",
        tags=["6.3: Attendance Geolocation"],
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
                                "code": "DV001",
                                "name": "Headquarters Geofence",
                                "project": {
                                    "id": 1,
                                    "code": "DA001",
                                    "name": "Main Office Project",
                                },
                                "address": "123 Main Street, District 1, Ho Chi Minh City",
                                "latitude": "10.7769000",
                                "longitude": "106.7009000",
                                "radius_m": 100,
                                "status": "active",
                                "notes": "Main office geofence area",
                                "created_by": {
                                    "id": 1,
                                    "username": "admin",
                                },
                                "updated_by": {
                                    "id": 1,
                                    "username": "admin",
                                },
                                "created_at": "2025-11-14T03:00:00Z",
                                "updated_at": "2025-11-14T03:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new attendance geolocation",
        description="Create a new attendance geolocation in the system. "
        "The code is auto-generated server-side with pattern DV###.",
        tags=["6.3: Attendance Geolocation"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Headquarters Geofence",
                    "project_id": 1,
                    "address": "123 Main Street, District 1, Ho Chi Minh City",
                    "latitude": "10.7769000",
                    "longitude": "106.7009000",
                    "radius_m": 100,
                    "status": "active",
                    "notes": "Main office geofence area",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DV001",
                        "name": "Headquarters Geofence",
                        "project": {
                            "id": 1,
                            "code": "DA001",
                            "name": "Main Office Project",
                        },
                        "address": "123 Main Street, District 1, Ho Chi Minh City",
                        "latitude": "10.7769000",
                        "longitude": "106.7009000",
                        "radius_m": 100,
                        "status": "active",
                        "notes": "Main office geofence area",
                        "created_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "updated_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "created_at": "2025-11-14T03:00:00Z",
                        "updated_at": "2025-11-14T03:00:00Z",
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
                        "radius_m": ["Radius must be at least 1 meter"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get attendance geolocation details",
        description="Retrieve detailed information about a specific attendance geolocation",
        tags=["6.3: Attendance Geolocation"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DV001",
                        "name": "Headquarters Geofence",
                        "project": {
                            "id": 1,
                            "code": "DA001",
                            "name": "Main Office Project",
                        },
                        "address": "123 Main Street, District 1, Ho Chi Minh City",
                        "latitude": "10.7769000",
                        "longitude": "106.7009000",
                        "radius_m": 100,
                        "status": "active",
                        "notes": "Main office geofence area",
                        "created_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "updated_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "created_at": "2025-11-14T03:00:00Z",
                        "updated_at": "2025-11-14T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update attendance geolocation",
        description="Update attendance geolocation information. Code cannot be changed.",
        tags=["6.3: Attendance Geolocation"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Headquarters Geofence Updated",
                    "project_id": 1,
                    "address": "123 Main Street, District 1, Ho Chi Minh City",
                    "latitude": "10.7769000",
                    "longitude": "106.7009000",
                    "radius_m": 150,
                    "status": "active",
                    "notes": "Updated geofence radius",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DV001",
                        "name": "Headquarters Geofence Updated",
                        "project": {
                            "id": 1,
                            "code": "DA001",
                            "name": "Main Office Project",
                        },
                        "address": "123 Main Street, District 1, Ho Chi Minh City",
                        "latitude": "10.7769000",
                        "longitude": "106.7009000",
                        "radius_m": 150,
                        "status": "active",
                        "notes": "Updated geofence radius",
                        "created_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "updated_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "created_at": "2025-11-14T03:00:00Z",
                        "updated_at": "2025-11-14T03:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update attendance geolocation",
        description="Partially update attendance geolocation information",
        tags=["6.3: Attendance Geolocation"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "radius_m": 200,
                    "notes": "Increased geofence radius",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DV001",
                        "name": "Headquarters Geofence",
                        "project": {
                            "id": 1,
                            "code": "DA001",
                            "name": "Main Office Project",
                        },
                        "address": "123 Main Street, District 1, Ho Chi Minh City",
                        "latitude": "10.7769000",
                        "longitude": "106.7009000",
                        "radius_m": 200,
                        "status": "active",
                        "notes": "Increased geofence radius",
                        "created_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "updated_by": {
                            "id": 1,
                            "username": "admin",
                        },
                        "created_at": "2025-11-14T03:00:00Z",
                        "updated_at": "2025-11-14T03:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete attendance geolocation",
        description="Soft-delete a attendance geolocation from the system. "
        "If the geolocation is referenced by other active resources (e.g., attendance rules), "
        "the deletion will be prevented.",
        tags=["6.3: Attendance Geolocation"],
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
                        "detail": "Cannot delete this Project Geolocation because it is referenced by: 3 Attendance Rules",
                        "protected_objects": [
                            {
                                "count": 3,
                                "name": "Attendance Rules",
                                "protected_object_ids": [1, 2, 3],
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
        tags=["6.3: Attendance Geolocation"],
    ),
)
class AttendanceGeolocationViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for AttendanceGeolocation model with distance-based sorting support"""

    queryset = AttendanceGeolocation.objects.filter(deleted=False).select_related(
        "project", "created_by", "updated_by"
    )
    serializer_class = AttendanceGeolocationSerializer
    filterset_class = AttendanceGeolocationFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter, DistanceOrderingFilterBackend]
    search_fields = ["code", "name"]
    ordering_fields = ["name", "created_at", "distance"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Project Geolocation Management"
    permission_prefix = "attendance_geolocation"

    def get_export_data(self, request):
        """Custom export data for AttendanceGeolocation.

        Exports the following fields:
        - code
        - name
        - project__name
        - address
        - latitude
        - longitude
        - radius_m
        - status
        - notes
        - created_at
        - updated_at
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = AttendanceGeolocationExportSerializer(queryset, many=True)
        data = serializer.data

        return {
            "sheets": [
                {
                    "name": "Attendance Geolocations",
                    "headers": [
                        "Code",
                        "Name",
                        "Project",
                        "Address",
                        "Latitude",
                        "Longitude",
                        "Radius (m)",
                        "Status",
                        "Notes",
                        "Created At",
                        "Updated At",
                    ],
                    "field_names": [
                        "code",
                        "name",
                        "project__name",
                        "address",
                        "latitude",
                        "longitude",
                        "radius_m",
                        "status",
                        "notes",
                        "created_at",
                        "updated_at",
                    ],
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
