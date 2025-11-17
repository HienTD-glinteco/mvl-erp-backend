from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.timesheet import TimesheetFilterSet
from apps.hrm.api.serializers.timesheet import (
    EmployeeSerializer,
    EmployeeTimesheetSerializer,
)
from apps.hrm.models import Employee
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List employee timesheets",
        description="Retrieve timesheet summaries for employees. Filters: employee, branch, block, department, position, employee_type. Search by employee code or fullname.",
        tags=["Timesheet"],
    ),
    retrieve=extend_schema(summary="Get employee timesheet details", tags=["Timesheet"]),
)
class EmployeeTimesheetViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """Read-only ViewSet returning employee timesheet summaries."""

    queryset = Employee.objects.select_related("branch", "block", "department", "position")
    serializer_class = EmployeeTimesheetSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TimesheetFilterSet
    # Search by employee code OR fullname
    search_fields = ["employee__code", "employee__fullname"]
    ordering_fields = ["employee__code", "employee__fullname"]
    ordering = "employee__fullname"

    module = "HRM"
    submodule = "Timesheet"
    permission_prefix = "timesheet"

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(qs)
        results = []

        iterable = page if page is not None else qs
        for emp in iterable:
            emp_data = EmployeeSerializer(emp).data
            item = {
                "employee": emp_data,
                "dates": [],
                "probation_days": 0,
                "official_work_days": 0,
                "total_work_days": 0,
                "unexcused_absence_days": 0,
                "holiday_days": 0,
                "unpaid_leave_days": 0,
                "maternity_leave_days": 0,
                "annual_leave_days": 0,
                "initial_leave_balance": 0,
                "remaining_leave_balance": 0,
            }
            results.append(item)

        if page is not None:
            return self.get_paginated_response(results)

        return Response(results)

    def retrieve(self, request, pk=None, *args, **kwargs):
        emp = self.get_object()
        emp_data = EmployeeSerializer(emp).data
        payload = {
            "employee": emp_data,
            "dates": [],
            "probation_days": 0,
            "official_work_days": 0,
            "total_work_days": 0,
            "unexcused_absence_days": 0,
            "holiday_days": 0,
            "unpaid_leave_days": 0,
            "maternity_leave_days": 0,
            "annual_leave_days": 0,
            "initial_leave_balance": 0,
            "remaining_leave_balance": 0,
        }

        serializer = self.get_serializer(payload)
        return Response(serializer.data)
