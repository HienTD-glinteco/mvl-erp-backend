from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import BankFilterSet
from apps.hrm.api.serializers import BankSerializer
from apps.hrm.models import Bank
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all banks",
        description="Retrieve a paginated list of all banks with support for filtering by name and code",
        tags=["Bank"],
    ),
    retrieve=extend_schema(
        summary="Get bank details",
        description="Retrieve detailed information about a specific bank",
        tags=["Bank"],
    ),
)
class BankViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """ViewSet for Bank model (read-only operations only)"""

    queryset = Bank.objects.all()
    serializer_class = BankSerializer
    filterset_class = BankFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Bank Management"
    permission_prefix = "bank"
