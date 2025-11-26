import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from django.utils import timezone
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
)
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.timesheet import EmployeeTimesheetFilterSet
from apps.hrm.api.serializers.timesheet import (
    EmployeeTimesheetSerializer,
    TimeSheetEntryDetailSerializer,
)
from apps.hrm.constants import EmployeeSalaryType
from apps.hrm.models import Employee
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


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
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = EmployeeTimesheetFilterSet
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
        first_day, last_day, month_key, employee_salary_type = self._get_timesheet_params(request)

        # Bulk fetch TimeSheetEntries for the set of employees to avoid N+1 queries
        employee_ids = [e.id for e in employees]
        all_entries = TimeSheetEntry.objects.filter(
            employee_id__in=employee_ids,
            date__range=(first_day, last_day),
        ).order_by("employee_id", "date")
        if employee_salary_type:
            all_entries = all_entries.filter(count_for_payroll=employee_salary_type == EmployeeSalaryType.SALARIED)

        entries_by_employee = defaultdict(list)
        for e in all_entries:
            entries_by_employee[e.employee_id].append(e)

        # Bulk fetch monthly timesheets for the given month_key and map to employees
        monthly_qs = EmployeeMonthlyTimesheet.objects.filter(employee_id__in=employee_ids, month_key=month_key)
        monthly_map = {m.employee_id: m for m in monthly_qs}

        for emp in employees:
            entries = entries_by_employee.get(emp.id, [])
            monthly = monthly_map.get(emp.id)
            payload = self._prepare_employee_data(emp, entries, monthly, first_day, last_day)
            results.append(payload)

        # Serialize the results to ensure Decimal fields are handled and types match
        serialized = EmployeeTimesheetSerializer(results, many=True).data
        if page is not None:
            return self.get_paginated_response(serialized)

        return Response(serialized)

    def _get_timesheet_params(self, request):
        # Determine month/year from filterset (fallback to current month)
        filterset = EmployeeTimesheetFilterSet(data=request.GET)
        if filterset.is_valid():
            cleaned_params = filterset.form.cleaned_data
        else:
            cleaned_params = {}

        year_month = filterset.extract_month_year(cleaned_params.get("month"))
        if year_month is None:
            today = timezone.localdate()
            year = today.year
            month = today.month
        else:
            month, year = year_month
        # Disallow selecting months in the future
        today = timezone.localdate()
        if (year, month) > (today.year, today.month):
            raise ValidationError({"month": _("Month filter cannot be in the future.")})
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        employee_salary_type = cleaned_params.get("employee_salary_type")

        month_key = f"{year:04d}{month:02d}"

        return first_day, last_day, month_key, employee_salary_type

    def _prepare_employee_data(
        self,
        employee: Employee,
        timesheet_entries: Iterable[TimeSheetEntry],
        monthly_timesheet: EmployeeMonthlyTimesheet | None = None,
        first_day: date | None = None,
        last_day: date | None = None,
    ) -> dict[str, Any]:
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

        # Build a full list of dates for the month. If first_day/last_day are not provided,
        # use the dates present in the timesheet_entries only.
        if first_day is not None and last_day is not None:
            total_days = (last_day - first_day).days + 1
            # Map existing entries by date for quick lookup
            entries_by_date = {e.date: e for e in timesheet_entries}

            dates_list: list[dict[str, Any]] = []
            for i in range(total_days):
                current_date = first_day + timedelta(days=i)
                entry = entries_by_date.get(current_date)
                if entry:
                    dates_list.append(
                        {
                            "id": entry.id,
                            "date": entry.date,
                            "status": entry.status,
                            "start_time": entry.start_time,
                            "end_time": entry.end_time,
                            "has_complaint": None,  # TODO: implement complaints
                        }
                    )
                else:
                    dates_list.append(
                        {
                            "date": current_date,
                            "status": None,
                            "start_time": None,
                            "end_time": None,
                            "has_complaint": None,
                        }
                    )

            payload["dates"] = dates_list
        else:
            # Fallback: keep current behaviour when no month range provided
            payload["dates"] = [
                {
                    "date": entry.date,
                    "status": entry.status,
                    "start_time": entry.start_time,
                    "end_time": entry.end_time,
                    "has_complaint": None,  # TODO: correct this field after implementing timesheet complaint feature
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


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get timesheet entry details",
        description="Retrieve detailed information for a specific timesheet entry",
        tags=["Timesheet"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "NC000001",
                        "employee": {
                            "id": 1,
                            "code": "EMP001",
                            "fullname": "John Doe",
                        },
                        "date": "2025-01-15",
                        "start_time": "2025-01-15T08:00:00Z",
                        "end_time": "2025-01-15T17:00:00Z",
                        "morning_hours": "4.00",
                        "afternoon_hours": "4.00",
                        "official_hours": "8.00",
                        "overtime_hours": "0.00",
                        "total_worked_hours": "8.00",
                        "status": "on_time",
                        "absent_reason": None,
                        "is_full_salary": True,
                        "count_for_payroll": True,
                        "note": "",
                        "created_at": "2025-01-15T00:00:00Z",
                        "updated_at": "2025-01-15T00:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
)
class TimeSheetEntryViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """Read-only ViewSet for TimeSheetEntry detail view."""

    queryset = TimeSheetEntry.objects.select_related("employee").all()
    serializer_class = TimeSheetEntryDetailSerializer

    module = "HRM"
    submodule = "Timesheet"
    permission_prefix = "timesheet"
