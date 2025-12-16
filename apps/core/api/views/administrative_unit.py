from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.core.api.filtersets.administrative_unit import AdministrativeUnitFilterSet
from apps.core.api.serializers.administrative_unit import AdministrativeUnitSerializer
from apps.core.models import AdministrativeUnit
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List administrative units",
        description="Retrieve a paginated list of all administrative units (districts, wards, communes, etc.)",
        tags=["0.8: Geographic"],
        examples=[
            OpenApiExample(
                "List administrative units success",
                description="Example response when listing administrative units",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "001",
                                "name": "Quận Ba Đình",
                                "parent_province": 1,
                                "province_code": "01",
                                "province_name": "Thành phố Hà Nội",
                                "level": "district",
                                "level_display": "District",
                                "enabled": True,
                                "created_at": "2025-01-10T10:00:00Z",
                                "updated_at": "2025-01-10T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "002",
                                "name": "Quận Hoàn Kiếm",
                                "parent_province": 1,
                                "province_code": "01",
                                "province_name": "Thành phố Hà Nội",
                                "level": "district",
                                "level_display": "District",
                                "enabled": True,
                                "created_at": "2025-01-10T10:00:00Z",
                                "updated_at": "2025-01-10T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve an administrative unit",
        description="Retrieve detailed information about a specific administrative unit.",
        tags=["0.8: Geographic"],
        examples=[
            OpenApiExample(
                "Get administrative unit success",
                description="Example response when retrieving an administrative unit",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "001",
                        "name": "Quận Ba Đình",
                        "parent_province": 1,
                        "province_code": "01",
                        "province_name": "Thành phố Hà Nội",
                        "level": "district",
                        "level_display": "District",
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
class AdministrativeUnitViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for AdministrativeUnit model - read-only with pagination"""

    queryset = AdministrativeUnit.objects.select_related("parent_province").all()
    serializer_class = AdministrativeUnitSerializer
    filterset_class = AdministrativeUnitFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "name", "parent_province__code", "created_at"]
    ordering = ["parent_province__code", "code"]

    # Permission registration attributes
    module = _("Core")
    submodule = _("Geographic Data")
    permission_prefix = "administrative_unit"
