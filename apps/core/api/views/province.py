from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.core.api.filtersets.province import ProvinceFilterSet
from apps.core.api.serializers.province import ProvinceSerializer
from apps.core.models import Province
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List provinces",
        description="Retrieve a list of all provinces/cities in the system",
        tags=["Geographic"],
        examples=[
            OpenApiExample(
                "List provinces success",
                description="Example response when listing provinces",
                value={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "code": "01",
                            "name": "Thành phố Hà Nội",
                            "english_name": "Ha Noi",
                            "level": "central_city",
                            "level_display": "Central City",
                            "decree": "Nghị quyết 15/2019/NQ-CP",
                            "enabled": True,
                            "created_at": "2025-01-10T10:00:00Z",
                            "updated_at": "2025-01-10T10:00:00Z",
                        },
                        {
                            "id": 2,
                            "code": "48",
                            "name": "Thành phố Đà Nẵng",
                            "english_name": "Da Nang",
                            "level": "central_city",
                            "level_display": "Central City",
                            "decree": "Nghị quyết 120/2019/NQ-CP",
                            "enabled": True,
                            "created_at": "2025-01-10T10:00:00Z",
                            "updated_at": "2025-01-10T10:00:00Z",
                        },
                    ],
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a province",
        description="Retrieve detailed information about a specific province.",
        tags=["Geographic"],
        examples=[
            OpenApiExample(
                "Get province success",
                description="Example response when retrieving a province",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "01",
                        "name": "Thành phố Hà Nội",
                        "english_name": "Ha Noi",
                        "level": "central_city",
                        "level_display": "Central City",
                        "decree": "Nghị quyết 15/2019/NQ-CP",
                        "enabled": True,
                        "created_at": "2025-01-10T10:00:00Z",
                        "updated_at": "2025-01-10T10:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
)
class ProvinceViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Province model - read-only with no pagination"""

    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer
    filterset_class = ProvinceFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "english_name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]
    pagination_class = None  # Disable pagination for provinces

    # Permission registration attributes
    module = "Core"
    submodule = "Geographic Data"
    permission_prefix = "province"
