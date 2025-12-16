from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import BankFilterSet
from apps.hrm.api.serializers import BankSerializer
from apps.hrm.models import Bank
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all banks",
        description="Retrieve a paginated list of all banks with support for filtering by name and code",
        tags=["5.7: Bank - Bank Accounts"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "name": "Vietcombank",
                                "code": "VCB",
                                "created_at": "2024-01-01T00:00:00Z",
                                "updated_at": "2024-01-01T00:00:00Z",
                            },
                            {
                                "id": 2,
                                "name": "BIDV",
                                "code": "BIDV",
                                "created_at": "2024-01-01T00:00:00Z",
                                "updated_at": "2024-01-01T00:00:00Z",
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Authentication credentials were not provided."},
                },
                response_only=True,
                status_codes=["401"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get bank details",
        description="Retrieve detailed information about a specific bank",
        tags=["5.7: Bank - Bank Accounts"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "name": "Vietcombank",
                        "code": "VCB",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Not Found",
                value={"success": False, "data": None, "error": {"detail": "Not found."}},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
)
class BankViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """ViewSet for Bank model (read-only operations only)"""

    queryset = Bank.objects.all()
    serializer_class = BankSerializer
    filterset_class = BankFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["id"]

    # Permission registration attributes
    module = _("HRM")
    submodule = _("Bank Management")
    permission_prefix = "bank"
