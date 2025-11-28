from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets

from apps.hrm.api.serializers import WorkScheduleSerializer
from apps.hrm.models import WorkSchedule


@extend_schema_view(
    list=extend_schema(
        summary="List all work schedules",
        description="Retrieve a list of all work schedules with working hours for each day of the week",
        tags=["6.4 Work Schedule"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "weekday": 2,
                            "morning_time": "08:00-12:00",
                            "noon_time": "12:00-13:30",
                            "afternoon_time": "13:30-17:30",
                            "allowed_late_minutes": 5,
                            "note": "Standard work schedule",
                            "created_at": "2025-11-14T07:30:00Z",
                            "updated_at": "2025-11-14T07:30:00Z",
                        }
                    ],
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "data": None, "error": "Error message"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class WorkScheduleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """ViewSet for WorkSchedule model (list-only)."""

    queryset = WorkSchedule.objects.all()
    serializer_class = WorkScheduleSerializer
    pagination_class = None
