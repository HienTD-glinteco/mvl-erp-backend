from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import BankAccountFilterSet
from apps.hrm.api.serializers import BankAccountSerializer
from apps.hrm.models import BankAccount
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all bank accounts",
        description=(
            "Retrieve a paginated list of all bank accounts with support for "
            "filtering by employee, bank, and account details"
        ),
        tags=["Bank Account"],
    ),
    create=extend_schema(
        summary="Create a new bank account",
        description="Create a new bank account for an employee",
        tags=["Bank Account"],
    ),
    retrieve=extend_schema(
        summary="Get bank account details",
        description="Retrieve detailed information about a specific bank account",
        tags=["Bank Account"],
    ),
    update=extend_schema(
        summary="Update bank account",
        description="Update bank account information",
        tags=["Bank Account"],
    ),
    partial_update=extend_schema(
        summary="Partially update bank account",
        description="Partially update bank account information",
        tags=["Bank Account"],
    ),
    destroy=extend_schema(
        summary="Delete bank account",
        description="Remove a bank account from the system",
        tags=["Bank Account"],
    ),
)
class BankAccountViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for BankAccount model with full CRUD operations"""

    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    filterset_class = BankAccountFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["account_number", "account_name", "employee__fullname", "bank__name"]
    ordering_fields = ["created_at", "is_primary", "employee__fullname", "bank__name"]
    ordering = ["-is_primary", "-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Bank Account Management"
    permission_prefix = "bank_account"
