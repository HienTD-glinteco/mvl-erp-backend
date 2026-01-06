import calendar
from datetime import date

from django.utils import timezone
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response

from apps.hrm.api.filtersets import MineTimesheetFilterSet
from apps.hrm.api.serializers import EmployeeTimesheetSerializer, TimeSheetEntryDetailSerializer
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Employee, ProposalTimeSheetEntry
from apps.hrm.models.monthly_timesheet import EmployeeMonthlyTimesheet
from apps.hrm.models.timesheet import TimeSheetEntry
from libs.drf.base_viewset import BaseGenericViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List my timesheets",
        description="Retrieve timesheet summaries for the current user. Filter by month using ?month=MM/YYYY",
        tags=["6.6: My Timesheet"],
        parameters=[
            OpenApiParameter(
                name="month",
                description="Month in MM/YYYY format, e.g. 01/2026. Defaults to current month if not provided.",
                required=False,
                type=str,
            ),
        ],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "employee": {
                            "id": 1,
                            "code": "EMP001",
                            "fullname": "John Doe",
                        },
                        "dates": [],
                        "probation_days": "0.00",
                        "official_work_days": "20.00",
                        "total_work_days": "20.00",
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get my timesheet",
        description="Retrieve timesheet for the current user for a specific month",
        tags=["6.6: My Timesheet"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "EMP001",
                        "fullname": "John Doe",
                        "timesheet_summary": {
                            "total_days": 22,
                            "worked_days": 20,
                            "absent_days": 2,
                        },
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
)
class MyTimesheetViewSet(ListModelMixin, RetrieveModelMixin, BaseGenericViewSet):
    """Mobile ViewSet for viewing current user's timesheet."""

    queryset = Employee.objects.none()
    serializer_class = EmployeeTimesheetSerializer
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = MineTimesheetFilterSet

    module = _("HRM - Mobile")
    submodule = _("My Timesheet")
    permission_prefix = "my_timesheet"

    def get_queryset(self):
        """Return current user's employee."""
        if getattr(self, "swagger_fake_view", False):
            return Employee.objects.none()
        return Employee.objects.filter(id=self.request.user.employee.id)

    def list(self, request, *args, **kwargs):
        """List timesheet for current user for specified month."""
        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response(
                {
                    "success": False,
                    "data": None,
                    "error": _("The current user is not associated with any employee."),
                },
                status=400,
            )

        first_day, last_day, month_key = self._get_timesheet_params(request)

        all_entries = TimeSheetEntry.objects.filter(
            employee=employee,
            date__range=(first_day, last_day),
        ).order_by("date")

        entries_list = list(all_entries)
        all_entries_ids = [e.id for e in entries_list]

        complaint_entry_ids = set(
            ProposalTimeSheetEntry.objects.filter(
                timesheet_entry_id__in=all_entries_ids,
                proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
                proposal__proposal_status=ProposalStatus.PENDING,
            )
            .values_list("timesheet_entry_id", flat=True)
            .distinct()
        )

        monthly = EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key=month_key).first()

        payload = self._prepare_employee_data(
            employee, entries_list, monthly, first_day, last_day, complaint_entry_ids=complaint_entry_ids
        )

        context = self.get_serializer_context()
        context["complaint_entry_ids"] = complaint_entry_ids
        serialized = EmployeeTimesheetSerializer(payload, context=context).data

        return Response(serialized)

    def retrieve(self, request, *args, **kwargs):
        """Get timesheet for current user for specified month."""
        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response(
                {
                    "success": False,
                    "data": None,
                    "error": _("The current user is not associated with any employee."),
                },
                status=400,
            )

        first_day, last_day, month_key = self._get_timesheet_params(request)

        all_entries = TimeSheetEntry.objects.filter(
            employee=employee,
            date__range=(first_day, last_day),
        ).order_by("date")

        entries_list = list(all_entries)
        all_entries_ids = [e.id for e in entries_list]

        complaint_entry_ids = set(
            ProposalTimeSheetEntry.objects.filter(
                timesheet_entry_id__in=all_entries_ids,
                proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
                proposal__proposal_status=ProposalStatus.PENDING,
            )
            .values_list("timesheet_entry_id", flat=True)
            .distinct()
        )

        monthly = EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key=month_key).first()

        payload = self._prepare_employee_data(
            employee, entries_list, monthly, first_day, last_day, complaint_entry_ids=complaint_entry_ids
        )

        context = self.get_serializer_context()
        context["complaint_entry_ids"] = complaint_entry_ids
        serialized = EmployeeTimesheetSerializer(payload, context=context).data

        return Response(serialized)

    def _get_timesheet_params(self, request):
        """Extract and validate month parameters."""
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

        today = timezone.localdate()
        if (year, month) > (today.year, today.month):
            raise ValidationError({"month": _("Month filter cannot be in the future.")})

        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        month_key = f"{year:04d}{month:02d}"

        return first_day, last_day, month_key

    def _prepare_employee_data(
        self,
        employee: Employee,
        timesheet_entries,
        monthly_timesheet: EmployeeMonthlyTimesheet | None = None,
        first_day: date | None = None,
        last_day: date | None = None,
        complaint_entry_ids: set[int] | None = None,
    ):
        """Prepare employee timesheet data."""
        from apps.hrm.api.views.timesheet import EmployeeTimesheetViewSet

        viewset = EmployeeTimesheetViewSet()
        return viewset._prepare_employee_data(
            employee, timesheet_entries, monthly_timesheet, first_day, last_day, complaint_entry_ids
        )


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get my timesheet entry details",
        description="Retrieve detailed information for a specific timesheet entry of the current user",
        tags=["6.6: My Timesheet"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {
                            "id": 1,
                            "code": "EMP001",
                            "fullname": "John Doe",
                        },
                        "date": "2026-01-15",
                        "start_time": "2026-01-15T08:00:00Z",
                        "end_time": "2026-01-15T17:00:00Z",
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
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
)
class MyTimesheetEntryViewSet(RetrieveModelMixin, BaseGenericViewSet):
    """Mobile ViewSet for viewing current user's timesheet entries."""

    serializer_class = TimeSheetEntryDetailSerializer

    module = _("HRM - Mobile")
    submodule = _("My Timesheet Entry")
    permission_prefix = "my_timesheet_entry"

    def get_queryset(self):
        """Return timesheet entries for current user's employee only."""
        if getattr(self, "swagger_fake_view", False):
            return TimeSheetEntry.objects.none()

        employee = getattr(self.request.user, "employee", None)
        if not employee:
            return TimeSheetEntry.objects.none()

        return TimeSheetEntry.objects.filter(employee=employee).select_related("employee", "manually_corrected_by")

    def retrieve(self, request, *args, **kwargs):
        """Get timesheet entry details for current user."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
