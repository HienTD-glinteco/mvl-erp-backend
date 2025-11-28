from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentChannelFilterSet
from apps.hrm.api.serializers import RecruitmentChannelSerializer
from apps.hrm.models import RecruitmentChannel
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment channels",
        description="Retrieve a list of all recruitment channels with support for filtering and search",
        tags=["4.1 Recruitment Channel"],
    ),
    create=extend_schema(
        summary="Create a new recruitment channel",
        description="Create a new recruitment channel in the system",
        tags=["4.1 Recruitment Channel"],
    ),
    retrieve=extend_schema(
        summary="Get recruitment channel details",
        description="Retrieve detailed information about a specific recruitment channel",
        tags=["4.1 Recruitment Channel"],
    ),
    update=extend_schema(
        summary="Update recruitment channel",
        description="Update recruitment channel information",
        tags=["4.1 Recruitment Channel"],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment channel",
        description="Partially update recruitment channel information",
        tags=["4.1 Recruitment Channel"],
    ),
    destroy=extend_schema(
        summary="Delete recruitment channel",
        description="Remove a recruitment channel from the system",
        tags=["4.1 Recruitment Channel"],
    ),
)
class RecruitmentChannelViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentChannel model"""

    queryset = RecruitmentChannel.objects.all()
    serializer_class = RecruitmentChannelSerializer
    filterset_class = RecruitmentChannelFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_channel"
