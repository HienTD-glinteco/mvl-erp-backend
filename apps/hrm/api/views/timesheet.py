import calendar
from collections import defaultdict
from datetime import date

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.timesheet import TimesheetFilterSet
from apps.hrm.api.serializers.timesheet import (
    EmployeeTimesheetSerializer,
)
from apps.hrm.models import Employee
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List employee timesheets",
        description=(
            "Retrieve timesheet summaries for employees. Filters: employee, branch, block, "
            "department, position, employee_salary_type. Search by employee code or fullname."
        ),
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
    search_fields = ["code", "fullname"]
    ordering_fields = ["code", "fullname"]
    ordering = "fullname"

    module = "HRM"
    submodule = "Timesheet"
    permission_prefix = "timesheet"

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(qs)
        employees = page if page is not None else qs

        results = []

        # Determine month/year from filterset (fallback to current month)
        first_day, last_day, month_key = self._get_first_last_days(request)

        # Bulk fetch TimeSheetEntries for the set of employees to avoid N+1 queries
        employee_ids = [e.id for e in employees]
        all_entries = TimeSheetEntry.objects.filter(
            employee_id__in=employee_ids, date__range=(first_day, last_day)
        ).order_by("employee_id", "date")
        entries_by_employee = defaultdict(list)
        for e in all_entries:
            entries_by_employee[e.employee_id].append(e)

        # Bulk fetch monthly timesheets for the given month_key and map to employees
        monthly_qs = EmployeeMonthlyTimesheet.objects.filter(employee_id__in=employee_ids, month_key=month_key)
        monthly_map = {m.employee_id: m for m in monthly_qs}

        for emp in employees:
            entries = entries_by_employee.get(emp.id, [])
            monthly = monthly_map.get(emp.id)
            payload = self._prepare_employee_data(emp, entries, monthly)
            results.append(payload)

        # Serialize the results to ensure Decimal fields are handled and types match
        serialized = EmployeeTimesheetSerializer(results, many=True).data
        if page is not None:
            return self.get_paginated_response(serialized)

        return Response(serialized)

    def retrieve(self, request, pk=None, *args, **kwargs):
        emp = self.get_object()

        first_day, last_day, month_key = self._get_first_last_days(request)

        # Fill dates from TimeSheetEntry
        entries = (
            TimeSheetEntry.objects.filter(employee_id=emp.id, date__range=(first_day, last_day)).order_by("date").all()
        )

        # Fill aggregates from monthly timesheet
        monthly = EmployeeMonthlyTimesheet.objects.filter(employee_id=emp.id, month_key=month_key).first()

        payload = self._prepare_employee_data(emp, entries, monthly)

        serializer = self.get_serializer(payload)
        return Response(serializer.data)

    def _get_first_last_days(self, request):
        # Determine month/year from filterset (fallback to current month)
        year, month = TimesheetFilterSet.extract_month_year(request.GET.get("month"))
        if not year or not month:
            today = date.today()
            year = today.year
            month = today.month

        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        month_key = f"{year:04d}{month:02d}"

        return first_day, last_day, month_key

    def _prepare_employee_data(self, employee, timesheet_entries: list, monthly_timesheet=None):
        payload = {
            "employee": employee,
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

        payload["dates"] = [
            {
                "date": entry,
                "status": entry.status,
                "start_time": entry.start_time,
                "end_time": entry.end_time,
                "complaint": None,  # TODO: add complaint after implementing complaint
            }
            for entry in timesheet_entries
        ]

        if monthly_timesheet:
            payload["probation_days"] = monthly_timesheet.probation_working_days
            payload["official_work_days"] = monthly_timesheet.official_working_days
            payload["total_work_days"] = monthly_timesheet.total_working_days
            payload["unexcused_absence_days"] = monthly_timesheet.unexcused_absence_days
            payload["holiday_days"] = monthly_timesheet.public_holiday_days
            payload["unpaid_leave_days"] = monthly_timesheet.unpaid_leave_days
            payload["maternity_leave_days"] = monthly_timesheet.maternity_leave_days
            payload["annual_leave_days"] = monthly_timesheet.paid_leave_days
            payload["initial_leave_balance"] = monthly_timesheet.opening_balance_leave_days
            payload["remaining_leave_balance"] = monthly_timesheet.remaining_leave_days

        return payload
