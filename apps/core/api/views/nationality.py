from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.core.api.filtersets.nationality import NationalityFilterSet
from apps.core.api.serializers.nationality import NationalitySerializer
from apps.core.models import Nationality
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List nationalities",
        description="Retrieve a list of all nationalities in the system",
        tags=["0.8 Geographic"],
        examples=[
            OpenApiExample(
                "List nationalities success",
                description="Example response when listing nationalities",
                value={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "name": "Vietnamese",
                            "created_at": "2025-01-10T10:00:00Z",
                            "updated_at": "2025-01-10T10:00:00Z",
                        },
                        {
                            "id": 2,
                            "name": "American",
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
        summary="Retrieve a nationality",
        description="Retrieve detailed information about a specific nationality.",
        tags=["0.8 Geographic"],
        examples=[
            OpenApiExample(
                "Get nationality success",
                description="Example response when retrieving a nationality",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "Vietnamese",
                        "created_at": "2025-01-10T10:00:00Z",
                        "updated_at": "2025-01-10T10:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
)
class NationalityViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Nationality model - read-only with no pagination"""

    queryset = Nationality.objects.all()
    serializer_class = NationalitySerializer
    filterset_class = NationalityFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    pagination_class = None  # Disable pagination for nationalities

    # Permission registration attributes
    module = "Core"
    submodule = "Geographic Data"
    permission_prefix = "nationality"
