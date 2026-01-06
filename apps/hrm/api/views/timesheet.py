import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
)
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeTimesheetFilterSet
from apps.hrm.api.serializers import (
    EmployeeTimesheetSerializer,
    TimeSheetEntryDetailSerializer,
    TimeSheetEntryUpdateSerializer,
)
from apps.hrm.constants import EmployeeSalaryType, ProposalStatus, ProposalType
from apps.hrm.models import Employee, ProposalTimeSheetEntry
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry
from libs.drf.base_viewset import BaseGenericViewSet, BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List employee timesheets",
        description=(
            "Retrieve timesheet summaries for employees. Filters: employee, branch, block, "
            "department, position, employee_salary_type. Search by employee code or fullname."
        ),
        tags=["6.6: Timesheet"],
    ),
    retrieve=extend_schema(summary="Get employee timesheet details", tags=["6.6: Timesheet"]),
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

    module = _("HRM")
    submodule = _("Timesheet")
    permission_prefix = "timesheet"
    PERMISSION_REGISTERED_ACTIONS = {
        "list": {
            "name_template": _("List employee timesheets"),
            "description_template": _("List employee timesheets"),
        },
        "retrieve": {
            "name_template": _("Get employee timesheet details"),
            "description_template": _("Get employee timesheet details"),
        },
        "histories": {
            "name_template": _("History timesheets"),
            "description_template": _("View history of timesheets"),
        },
        "history_detail": {
            "name_template": _("History detail of timesheets"),
            "description_template": _("View history detail of timesheets"),
        },
        # "mine": {
        #     "name_template": _("List timesheets of current employee"),
        #     "description_template": _("List timesheets of current employee"),
        # },
    }

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
        all_entries_ids = []
        for e in all_entries:
            entries_by_employee[e.employee_id].append(e)
            all_entries_ids.append(e.id)

        # Identify which timesheet entries have complaints
        complaint_entry_ids = set(
            ProposalTimeSheetEntry.objects.filter(
                timesheet_entry_id__in=all_entries_ids,
                proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
                proposal__proposal_status=ProposalStatus.PENDING,
            )
            .values_list("timesheet_entry_id", flat=True)
            .distinct()
        )

        # Bulk fetch monthly timesheets for the given month_key and map to employees
        monthly_qs = EmployeeMonthlyTimesheet.objects.filter(employee_id__in=employee_ids, month_key=month_key)
        monthly_map = {m.employee_id: m for m in monthly_qs}

        for emp in employees:
            entries = entries_by_employee.get(emp.id, [])
            monthly = monthly_map.get(emp.id)
            payload = self._prepare_employee_data(
                emp, entries, monthly, first_day, last_day, complaint_entry_ids=complaint_entry_ids
            )
            results.append(payload)

        # Serialize the results to ensure Decimal fields are handled and types match
        context = self.get_serializer_context()
        context["complaint_entry_ids"] = complaint_entry_ids
        serialized = EmployeeTimesheetSerializer(results, many=True, context=context).data
        if page is not None:
            return self.get_paginated_response(serialized)

        return Response(serialized)

    # @extend_schema(
    #     summary="List timesheets of current employee",
    #     description=("Retrieve timesheet summaries for current employee."),
    #     tags=["6.6: Timesheet - For Mobile"],
    #     parameters=[
    #         OpenApiParameter(
    #             name="month",
    #             description="Month in MM/YYYY format, e.g. 03/2025",
    #             required=False,
    #             type=str,
    #         ),
    #     ],
    #     responses={
    #         200: EmployeeTimesheetSerializer,
    #     },
    # )
    # @action(detail=False, methods=["get"], url_path="mine", filterset_class=MineTimesheetFilterSet)
    # def mine(self, request, *args, **kwargs):
    #     employee = getattr(request.user, "employee", None)
    #     if not employee:
    #         return Response(
    #             {
    #                 "success": False,
    #                 "data": None,
    #                 "error": _("The current user is not associated with any employee."),
    #             },
    #             status=400,
    #         )

    #     # Determine month/year from filterset (fallback to current month)
    #     first_day, last_day, month_key, __ = self._get_timesheet_params(request)

    #     # Bulk fetch TimeSheetEntries for the set of employees to avoid N+1 queries
    #     all_entries = TimeSheetEntry.objects.filter(
    #         employee=employee,
    #         date__range=(first_day, last_day),
    #     ).order_by("employee_id", "date")

    #     entries_by_employee = defaultdict(list)
    #     all_entries_ids = []
    #     for e in all_entries:
    #         entries_by_employee[e.employee_id].append(e)
    #         all_entries_ids.append(e.id)

    #     # Identify which timesheet entries have complaints
    #     complaint_entry_ids = set(
    #         ProposalTimeSheetEntry.objects.filter(
    #             timesheet_entry_id__in=all_entries_ids,
    #             proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
    #             proposal__proposal_status=ProposalStatus.PENDING,
    #         )
    #         .values_list("timesheet_entry_id", flat=True)
    #         .distinct()
    #     )

    #     # Bulk fetch monthly timesheets for the given month_key and map to employees
    #     monthly_qs = EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key=month_key)
    #     monthly_map = {m.employee_id: m for m in monthly_qs}

    #     entries = entries_by_employee.get(employee.id, [])
    #     monthly = monthly_map.get(employee.id)
    #     payload = self._prepare_employee_data(
    #         employee, entries, monthly, first_day, last_day, complaint_entry_ids=complaint_entry_ids
    #     )

    #     # Serialize the results to ensure Decimal fields are handled and types match
    #     context = self.get_serializer_context()
    #     context["complaint_entry_ids"] = complaint_entry_ids
    #     serialized = EmployeeTimesheetSerializer(payload, context=context).data

    #     return Response(serialized)

    def _get_timesheet_params(self, request):
        # Determine month/year from filterset (fallback to current month)
        filterset = self.filterset_class(data=request.GET)
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
        complaint_entry_ids: set[int] | None = None,
    ) -> dict[str, Any]:
        if complaint_entry_ids is None:
            complaint_entry_ids = set()

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

            dates_list = []
            for i in range(total_days):
                current_date = first_day + timedelta(days=i)
                entry = entries_by_date.get(current_date)
                if entry:
                    dates_list.append(entry)
                else:
                    # Create dummy instance for missing date
                    dummy = TimeSheetEntry(date=current_date, employee=employee)
                    dates_list.append(dummy)

            payload["dates"] = dates_list
        else:
            # Fallback: keep current behaviour when no month range provided
            dates_list = []
            for entry in timesheet_entries:
                dates_list.append(entry)
            payload["dates"] = dates_list

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
    list=extend_schema(
        summary="List timesheet entries",
        tags=["6.6: Timesheet"],
    ),
    retrieve=extend_schema(
        summary="Get timesheet entry details",
        description="Retrieve detailed information for a specific timesheet entry",
        tags=["6.6: Timesheet"],
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
    update=extend_schema(
        summary="Update a timesheet entry",
        description=(
            "Update an existing timesheet entry. Only editable fields provided in the "
            "request will be updated. Returns the updated timesheet entry in the response."
        ),
        tags=["6.6: Timesheet"],
        request=TimeSheetEntryUpdateSerializer,
        responses={
            200: TimeSheetEntryDetailSerializer,
        },
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "NC000001",
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
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
            OpenApiExample(
                "Validation Error",
                value={"success": False, "data": None, "error": {"start_time": ["Invalid value"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class TimeSheetEntryViewSet(
    AuditLoggingMixin, ListModelMixin, RetrieveModelMixin, UpdateModelMixin, BaseGenericViewSet
):
    """ViewSet for TimeSheetEntry detail view."""

    http_method_names = ["get", "head", "put"]

    queryset = TimeSheetEntry.objects.select_related("employee").all()
    serializer_class = TimeSheetEntryDetailSerializer

    module = _("HRM")
    submodule = _("Timesheet")
    permission_prefix = "timesheet"
    PERMISSION_REGISTERED_ACTIONS = {
        "list": {
            "name_template": _("List employee timesheet entries"),
            "description_template": _("List employee timesheet entries"),
        },
        "retrieve": {
            "name_template": _("Get employee timesheet entry"),
            "description_template": _("Get employee timesheet entry"),
        },
        "update": {
            "name_template": _("Update an employee timesheet entry"),
            "description_template": _("Update an employee timesheet entry"),
        },
    }

    def get_serializer_class(self):
        if self.action == "update":
            return TimeSheetEntryUpdateSerializer
        return super().get_serializer_class()
