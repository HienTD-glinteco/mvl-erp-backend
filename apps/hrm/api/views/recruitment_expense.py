from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentExpenseFilterSet
from apps.hrm.api.serializers import RecruitmentExpenseSerializer
from apps.hrm.models import RecruitmentExpense
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment expenses",
        description="Retrieve a list of all recruitment expenses with support for filtering and search. "
        "Pagination: 25 items per page by default (customizable via page_size parameter, e.g., ?page_size=20)",
        tags=["Recruitment Expense"],
    ),
    create=extend_schema(
        summary="Create a new recruitment expense",
        description="Create a new recruitment expense in the system",
        tags=["Recruitment Expense"],
    ),
    retrieve=extend_schema(
        summary="Get recruitment expense details",
        description="Retrieve detailed information about a specific recruitment expense",
        tags=["Recruitment Expense"],
    ),
    update=extend_schema(
        summary="Update recruitment expense",
        description="Update recruitment expense information",
        tags=["Recruitment Expense"],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment expense",
        description="Partially update recruitment expense information",
        tags=["Recruitment Expense"],
    ),
    destroy=extend_schema(
        summary="Delete recruitment expense",
        description="Remove a recruitment expense from the system",
        tags=["Recruitment Expense"],
    ),
)
class RecruitmentExpenseViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentExpense model"""

    queryset = RecruitmentExpense.objects.all()
    serializer_class = RecruitmentExpenseSerializer
    filterset_class = RecruitmentExpenseFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "activity", "note"]
    ordering_fields = ["date", "total_cost", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_expense"
