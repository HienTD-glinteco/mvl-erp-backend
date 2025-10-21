from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentSourceFilterSet
from apps.hrm.api.serializers import RecruitmentSourceSerializer
from apps.hrm.models import RecruitmentSource
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment sources",
        description="Retrieve a list of all recruitment sources with support for filtering and search",
        tags=["Recruitment Source"],
    ),
    create=extend_schema(
        summary="Create a new recruitment source",
        description="Create a new recruitment source in the system",
        tags=["Recruitment Source"],
    ),
    retrieve=extend_schema(
        summary="Get recruitment source details",
        description="Retrieve detailed information about a specific recruitment source",
        tags=["Recruitment Source"],
    ),
    update=extend_schema(
        summary="Update recruitment source",
        description="Update recruitment source information",
        tags=["Recruitment Source"],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment source",
        description="Partially update recruitment source information",
        tags=["Recruitment Source"],
    ),
    destroy=extend_schema(
        summary="Delete recruitment source",
        description="Remove a recruitment source from the system",
        tags=["Recruitment Source"],
    ),
)
class RecruitmentSourceViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentSource model"""

    queryset = RecruitmentSource.objects.all()
    serializer_class = RecruitmentSourceSerializer
    filterset_class = RecruitmentSourceFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_source"
