from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeFilterSet
from apps.hrm.api.serializers import EmployeeSerializer
from apps.hrm.models import Employee
from libs import BaseModelViewSet, CustomPageNumberPagination


@extend_schema_view(
    list=extend_schema(
        summary="List all employees",
        description="Retrieve a paginated list of all employees with support for filtering by code and name",
        tags=["Employee"],
    ),
    create=extend_schema(
        summary="Create a new employee",
        description="Create a new employee in the system",
        tags=["Employee"],
    ),
    retrieve=extend_schema(
        summary="Get employee details",
        description="Retrieve detailed information about a specific employee",
        tags=["Employee"],
    ),
    update=extend_schema(
        summary="Update employee",
        description="Update employee information",
        tags=["Employee"],
    ),
    partial_update=extend_schema(
        summary="Partially update employee",
        description="Partially update employee information",
        tags=["Employee"],
    ),
    destroy=extend_schema(
        summary="Delete employee",
        description="Remove an employee from the system",
        tags=["Employee"],
    ),
)
class EmployeeViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Employee model"""

    queryset = Employee.objects.select_related("user").all()
    serializer_class = EmployeeSerializer
    filterset_class = EmployeeFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]
    pagination_class = CustomPageNumberPagination

    # Permission registration attributes
    module = "HRM"
    submodule = "Employee Management"
    permission_prefix = "employee"
